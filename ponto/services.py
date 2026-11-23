"""Regras, consultas e preparação dos dados de negócio do registro de ponto."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from io import BytesIO
from uuid import uuid4
from zipfile import BadZipFile

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from PIL import Image, ImageOps

from .constants import (
    COLUNAS_RELATORIO,
    DIAS_ABREVIADOS,
    DIAS_UTEIS,
    FACIAL_LIMIAR,
    FATOR_DOMINGO,
    FATOR_DOMINGO_COM_FOLGA,
    FERIADOS_NACIONAIS,
    HORARIO_DE_TRABALHO,
    INTERVALO_MINIMO_MINUTOS,
    JORNADA_DIARIA,
    MOTIVO_COMPENSACAO_IMPORTADA,
    MOTIVO_FOLGA_IMPORTADA,
    MOTIVOS_FOLGA_IMPORTADA_POR_DATA,
    PLANILHA_ABA_RESUMO,
    PLANILHA_CELULA_CPF,
    PLANILHA_COLUNA_DATA,
    PLANILHA_COLUNA_FOLGA,
    PLANILHA_PRIMEIRA_LINHA,
    ROTULOS_CURTOS,
    TOLERANCIA_SALDO,
)
from .exceptions import CadastroFacialAusente, ErroBatida, ErroFacial, ErroImportacao
from .facial import extrair_vetor, identificar
from .models import (
    CadastroFacial,
    Feriado,
    Folga,
    HistoricoAlteracaoPonto,
    Jornada,
    Perfil,
    RegistroPonto,
    VinculoJornada,
)
from .permissoes import funcionarios_visiveis
from .utils import formatar_timedelta, hhmm, hhmm_com_sinal


def proximo_tipo(registros, tipos=None):
    """O primeiro tipo da ordem do dia ainda sem batida, ou None quando o dia está completo."""
    feitos = {r.tipo for r in registros}
    for tipo in tipos if tipos is not None else RegistroPonto.ORDEM_TIPOS:
        if tipo not in feitos:
            return tipo
    return None


def linha_do_dia(registros, marcar_proxima=True, usuario=None, data=None):
    """As 6 batidas na ordem do dia, cada uma com o registro (ou None) e se é a próxima.

    Para um dia que já passou, marcar_proxima=False deixa as batidas que faltaram só como pendentes.
    """
    por_tipo = {r.tipo: r for r in registros}
    tipos = tipos_da_jornada(usuario, data or timezone.localdate()) if usuario else RegistroPonto.ORDEM_TIPOS
    proximo = proximo_tipo(registros, tipos) if marcar_proxima else None
    nomes = dict(RegistroPonto.TIPO_CHOICES)
    return [
        {
            'tipo': tipo,
            'rotulo': ROTULOS_CURTOS[tipo],
            'nome': nomes[tipo],
            'registro': por_tipo.get(tipo),
            'proxima': tipo == proximo,
        }
        for tipo in tipos
    ]


def situacao(registros):
    """Situação de alguém no dia, a partir da última batida: (rótulo, classe do selo)."""
    if not registros:
        return 'Sem entrada', 'neutro'
    ultima = max(registros, key=lambda r: r.data_hora).tipo
    if ultima == RegistroPonto.SAIDA:
        return 'Jornada encerrada', 'sucesso'
    if ultima == RegistroPonto.SAIDA_ALMOCO:
        return 'No almoço', 'atencao'
    if ultima == RegistroPonto.SAIDA_CAFE:
        return 'No café', 'atencao'
    return 'Em jornada', 'info'


def preparar_cartao_ponto(item, data_inicio, data_fim):
    """Linhas e totais do cartão ponto em PDF para um item de montar_relatorio.

    NORMAIS e EXTRAS seguem a regra de calcular_resumo. FALTAS soma o saldo devedor dos dias completos e a
    jornada inteira dos dias úteis já passados sem nenhuma batida; dias futuros ficam em branco. Dias com batidas,
    mas sem entrada ou saída, saem como incompletos, sem horas calculadas.
    """
    hoje = timezone.localdate()
    registros = RegistroPonto.objects.filter(
        funcionario=item['funcionario'], data_hora__date__range=(data_inicio, data_fim), ativo=True
    )
    manuais = {(timezone.localtime(r.data_hora).date(), r.tipo) for r in registros if r.registrado_manualmente}

    totais = {'normais': timedelta(), 'faltas': timedelta(), 'extras': timedelta(), 'carga': timedelta()}
    compensacoes = timedelta()
    linhas = []
    for dia in item['relatorio']:
        data, horarios = dia['data'], dia['horarios']
        configuracao = configuracao_jornada(item['funcionario'], data)
        util = configuracao['util'] and not configuracao['feriado'] and not configuracao['folga']
        normais = faltas = extras = carga = None
        observacao = ''

        if dia['status'] == 'Completo':
            carga = dia['esperado']
            diferenca = dia['diferenca']
            if diferenca >= timedelta():
                normais = dia['esperado']
                extras = diferenca or None
            else:
                normais = dia['tempo_trabalhado']
                faltas = -diferenca
        elif horarios:
            carga = configuracao['carga'] if util else None
            observacao = 'Incompleto'
        elif util and data < hoje:
            carga = faltas = configuracao['carga']
            observacao = 'Falta'

        folga = configuracao['folga']
        if folga and folga.tipo == Folga.COMPENSACAO and folga.horas_abatidas:
            compensacoes += folga.horas_abatidas
        if folga or configuracao['feriado']:
            if folga:
                observacao = 'Folga comp.' if folga.tipo == Folga.COMPENSACAO else 'Folga'
            else:
                observacao = 'Feriado'
            if horarios and dia['status'] != 'Completo':
                observacao += ' · Incompleto'
        if dia.get('fator', 1) != 1:
            # Domingo: a coluna EXTRAS já traz as horas com o adicional.
            observacao = f'Dom. +{round((dia["fator"] - 1) * 100)}%'

        for chave, valor in (('normais', normais), ('faltas', faltas), ('extras', extras), ('carga', carga)):
            if valor:
                totais[chave] += valor

        linhas.append(
            {
                'dia': f'{data:%d/%m/%y} - {DIAS_ABREVIADOS[data.weekday()]}',
                'fim_de_semana': not util,
                'batidas': [
                    {
                        'hora': timezone.localtime(horarios[tipo]).strftime('%H:%M') if tipo in horarios else '',
                        'manual': (data, tipo) in manuais,
                    }
                    for tipo in RegistroPonto.ORDEM_TIPOS
                ],
                'normais': hhmm(normais),
                'faltas': hhmm(faltas),
                'extras': hhmm(extras),
                'carga': hhmm(carga),
                'observacao': observacao,
            }
        )

    configuracao = configuracao_jornada(item['funcionario'], data_fim)
    vinculo = jornada_vigente(item['funcionario'], data_fim)
    item['horario'] = []
    for indice, nome in enumerate(DIAS_ABREVIADOS):
        horas = vinculo.semana.get(str(indice), []) if configuracao['personalizado'] else []
        pares = []
        if horas and horas[0]:
            preenchidas = [h for h in horas if h]
            pares = list(zip(preenchidas[::2], preenchidas[1::2], strict=True))
        elif not configuracao['personalizado'] and indice in DIAS_UTEIS:
            pares = HORARIO_DE_TRABALHO
        if pares:
            pares = list(pares) + [('', '')] * (3 - len(pares))
        item['horario'].append({'nome': nome.upper(), 'pares': pares})
    item['jornada_nome'] = configuracao['nome']
    # Mesma regra do banco de horas: extras menos faltas menos as folgas de compensação do período.
    saldo_periodo = totais['extras'] - totais['faltas'] - compensacoes
    data_saldo = min(data_fim, hoje)
    item['cartao'] = {
        'linhas': linhas,
        'totais': {chave: hhmm(valor) or '00:00' for chave, valor in totais.items()},
        'tem_manual': bool(manuais),
        'banco': {
            'extras': hhmm(totais['extras']) or '00:00',
            'faltas': hhmm(totais['faltas']) or '00:00',
            'compensacoes': hhmm(compensacoes) or '00:00',
            'saldo_periodo': hhmm_com_sinal(saldo_periodo),
            'saldo_acumulado': hhmm_com_sinal(saldo_banco_horas(item['funcionario'], ate=data_saldo)),
            'data_saldo': data_saldo,
        },
    }
    return item


def proximo_tipo_ponto(funcionario):
    hoje = timezone.localdate()
    registros = RegistroPonto.objects.filter(funcionario=funcionario, data_hora__date=hoje, ativo=True)
    batidas_registradas = registros.values_list('tipo', flat=True)

    for tipo in tipos_da_jornada(funcionario, hoje):
        if tipo not in batidas_registradas:
            return tipo


@transaction.atomic
def registrar_batida(usuario):
    # Serializa batidas da mesma pessoa, inclusive entre o terminal e o botão comum.
    User.objects.select_for_update().get(pk=usuario.pk)
    agora = timezone.now()
    limite = agora - timedelta(minutes=INTERVALO_MINIMO_MINUTOS)
    if RegistroPonto.objects.filter(
        funcionario=usuario,
        data_hora__gte=limite,
        data_hora__lte=agora,
        ativo=True,
    ).exists():
        raise ErroBatida(f'Você só pode bater ponto a cada {INTERVALO_MINIMO_MINUTOS} minutos.')
    tipo = proximo_tipo_ponto(usuario)
    if not tipo:
        raise ErroBatida('Todos os pontos do dia foram batidos.')
    return RegistroPonto.objects.create(funcionario=usuario, tipo=tipo, data_hora=agora)


def tem_cadastro_facial(usuario):
    return CadastroFacial.objects.filter(funcionario=usuario).exists()


def pessoas_para_cadastro_facial(usuario):
    cadastros = CadastroFacial.objects.filter(funcionario_id=OuterRef('pk'))
    return _pessoas(usuario).annotate(rosto_cadastrado=Exists(cadastros)).order_by('first_name', 'username')


def estado_cadastro_facial(pessoa):
    return {'funcionario_id': pessoa.pk, 'cadastrado': tem_cadastro_facial(pessoa)}


def salvar_cadastro_facial(pessoa, foto, responsavel):
    vetor = extrair_vetor(foto)
    outros = CadastroFacial.objects.exclude(funcionario=pessoa).select_related('funcionario')
    if any(sum(a * b for a, b in zip(vetor, outro.vetor, strict=True)) >= FACIAL_LIMIAR for outro in outros):
        raise ErroFacial('Este rosto já possui cadastro. Peça a revisão ao administrador.')
    CadastroFacial.objects.update_or_create(
        funcionario=pessoa,
        defaults={'vetor': vetor, 'cadastrado_por': responsavel},
    )
    return {
        'funcionario_id': pessoa.pk,
        'cadastrado': True,
        'mensagem': f'Rosto cadastrado para {pessoa.get_full_name() or pessoa.username}.',
    }


def remover_cadastro_facial(pessoa):
    CadastroFacial.objects.filter(funcionario=pessoa).delete()
    return {'funcionario_id': pessoa.pk, 'cadastrado': False, 'mensagem': 'Cadastro facial removido.'}


def registrar_ponto_facial(usuario, foto, *, compartilhado=False, presenca_anterior=None):
    """Reconhece e registra sem depender de requisição, sessão ou resposta HTTP.

    No modo compartilhado, o usuário é o gestor responsável. A presença anterior contém
    apenas pessoa_id, registrado e mensagem, para não repetir a batida de quem permanece na câmera.
    """
    if compartilhado:
        cadastros = CadastroFacial.objects.filter(funcionario__in=_pessoas(usuario))
        sem_cadastro = 'Nenhum rosto cadastrado. Peça ao gestor para preparar os cadastros.'
    else:
        cadastros = CadastroFacial.objects.filter(funcionario=usuario)
        sem_cadastro = 'Peça ao gestor para cadastrar seu rosto antes de usar a câmera.'
    cadastros = cadastros.select_related('funcionario')
    if not cadastros.exists():
        raise CadastroFacialAusente(sem_cadastro)

    pessoa = identificar(extrair_vetor(foto), cadastros)
    repetido = bool(compartilhado and presenca_anterior and presenca_anterior['pessoa_id'] == pessoa.pk)
    if repetido:
        if not presenca_anterior['registrado']:
            return presenca_anterior
    else:
        try:
            registrar_batida(pessoa)
        except ErroBatida as exc:
            return {'pessoa_id': pessoa.pk, 'registrado': False, 'mensagem': str(exc)}

    primeiro_nome = (pessoa.first_name.strip() or pessoa.username).split()[0].upper()
    return {
        'pessoa_id': pessoa.pk,
        'registrado': True,
        'mensagem': f'PONTO REGISTRADO - {primeiro_nome}',
        'nome_completo': pessoa.get_full_name() or pessoa.username,
        'tem_foto': bool(pessoa.perfil.foto),
        'repetido': repetido,
    }


@transaction.atomic
def salvar_foto_perfil(usuario, arquivo=None, *, remover=False):
    perfil = usuario.perfil
    antiga = perfil.foto.name
    storage = perfil.foto.storage
    if remover:
        perfil.foto = ''
    else:
        arquivo.seek(0)
        with Image.open(arquivo) as original:
            original.draft('RGB', (1024, 1024))
            imagem = ImageOps.fit(ImageOps.exif_transpose(original).convert('RGB'), (512, 512))
            conteudo = BytesIO()
            imagem.save(conteudo, 'WEBP', quality=85, method=6)
        perfil.foto.save(f'{uuid4().hex}.webp', ContentFile(conteudo.getvalue()), save=False)
    perfil.save(update_fields=['foto'])
    if antiga and antiga != perfil.foto.name:
        transaction.on_commit(lambda: storage.delete(antiga))


def obter_foto_perfil(usuario, usuario_id):
    perfil = Perfil.objects.filter(user_id=usuario_id, user__in=_pessoas(usuario)).first()
    return perfil.foto if perfil and perfil.foto else None


def pessoas_para_relatorio(usuario):
    """Administrador vê todos; gestor, seus subordinados; colaborador, somente a si."""
    eh_colaborador = usuario.perfil.papel == Perfil.PAPEL_FUNCIONARIO
    pessoas = User.objects.filter(pk=usuario.pk) if eh_colaborador else funcionarios_visiveis(usuario)
    return pessoas.order_by('first_name', 'last_name', 'username'), eh_colaborador


def _gestor(usuario):
    return (
        usuario.is_authenticated
        and usuario.is_active
        and usuario.perfil.papel
        in (
            Perfil.PAPEL_GESTOR,
            Perfil.PAPEL_ADMIN,
        )
    )


def _pessoas(usuario):
    return (funcionarios_visiveis(usuario) | User.objects.filter(pk=usuario.pk)).filter(is_active=True)


def sincronizar_feriados_nacionais(ano):
    criados = 0
    with transaction.atomic():
        for mes, dia, nome in FERIADOS_NACIONAIS:
            if (mes, dia) == (11, 20) and ano < 2024:
                continue
            _, criado = Feriado.objects.get_or_create(
                data=date(ano, mes, dia),
                defaults={'nome': nome, 'nacional': True},
            )
            criados += criado
    return criados


def duracao_jornada(horarios):
    if not horarios or not horarios[0]:
        return timedelta()

    def instante(hora):
        return datetime.combine(date(2000, 1, 1), datetime.strptime(hora, '%H:%M').time())

    total = instante(horarios[5]) - instante(horarios[0])
    if horarios[1] and horarios[2]:
        total -= instante(horarios[2]) - instante(horarios[1])
    # O café é remunerado, como na regra original do sistema.
    return total


def jornada_vigente(usuario, data):
    return usuario.perfil.jornadas.filter(inicio__lte=data).first()


def configuracao_jornada(usuario, data, vinculos=None, feriados=None, folgas=None):
    """Carga e situação de um dia para a pessoa.

    vinculos (ordenados do mais recente), feriados e folgas ({data: objeto}) podem vir pré-carregados para
    cálculos de muitos dias, como o banco de horas; sem eles, cada um é consultado no banco.
    """
    if vinculos is None:
        vinculo = jornada_vigente(usuario, data)
    else:
        vinculo = next((v for v in vinculos if v.inicio <= data), None)
    if feriados is None:
        feriado = Feriado.objects.filter(data=data, dispensa_expediente=True).first()
    else:
        feriado = feriados.get(data)
    if folgas is None:
        folga = Folga.objects.filter(funcionario=usuario, data=data, ativa=True).select_related('lancada_por').first()
    else:
        folga = folgas.get(data)

    personalizado = bool(vinculo and vinculo.jornada_id)
    horarios = vinculo.semana.get(str(data.weekday()), []) if personalizado else []
    util = bool(horarios and horarios[0]) if personalizado else data.weekday() in DIAS_UTEIS
    # Fora dos dias úteis a carga é zero: o que for trabalhado conta como hora extra.
    jornada_do_dia = (duracao_jornada(horarios) if personalizado else JORNADA_DIARIA) if util else timedelta()
    # Sem a folga: é o que uma compensação nesta data abate do banco de horas.
    carga_sem_folga = timedelta() if feriado else jornada_do_dia
    return {
        'carga': timedelta() if folga else carga_sem_folga,
        'carga_sem_folga': carga_sem_folga,
        'horarios': horarios,
        'personalizado': personalizado,
        'nome': vinculo.nome if personalizado else 'Regra anterior (7h45min)',
        'util': util,
        'feriado': feriado,
        'folga': folga,
    }


def tempo_trabalhado(horarios):
    """Da entrada à saída, sem o almoço. O café é remunerado, como na regra original do sistema."""
    total = horarios[RegistroPonto.SAIDA] - horarios[RegistroPonto.ENTRADA]
    if RegistroPonto.SAIDA_ALMOCO in horarios and RegistroPonto.VOLTA_ALMOCO in horarios:
        total -= horarios[RegistroPonto.VOLTA_ALMOCO] - horarios[RegistroPonto.SAIDA_ALMOCO]
    return total


def saldo_do_dia(trabalhado, carga):
    diferenca = trabalhado - carga
    return timedelta() if abs(diferenca) <= TOLERANCIA_SALDO else diferenca


def fator_do_dia(funcionario, data, configuracao, dias_com_batida=None, vinculos=None, feriados=None, folgas=None):
    """Quanto vale cada hora trabalhada no dia: 1, ou o adicional de domingo sem expediente previsto.

    No domingo a hora vale o dobro; se a semana seguinte (segunda a sábado) tiver folga, feriado ou dia sem
    expediente que não foi trabalhado, vale 40% a mais. dias_com_batida (datas), vinculos, feriados e folgas podem
    vir pré-carregados, como em configuracao_jornada.
    """
    if data.weekday() != 6 or configuracao['util']:
        return 1
    semana = [data + timedelta(days=dias) for dias in range(1, 7)]
    if dias_com_batida is None:
        momentos = RegistroPonto.objects.filter(
            funcionario=funcionario, ativo=True, data_hora__date__range=(semana[0], semana[-1])
        ).values_list('data_hora', flat=True)
        dias_com_batida = {timezone.localtime(momento).date() for momento in momentos}
    for dia in semana:
        configuracao_do_dia = configuracao_jornada(funcionario, dia, vinculos, feriados, folgas)
        sem_expediente = not configuracao_do_dia['util'] and dia not in dias_com_batida
        if configuracao_do_dia['folga'] or configuracao_do_dia['feriado'] or sem_expediente:
            return FATOR_DOMINGO_COM_FOLGA
    return FATOR_DOMINGO


def saldo_banco_horas(funcionario, ate=None):
    """Banco de horas acumulado desde a primeira batida, como nos sistemas de RH.

    Cada dia completo soma a diferença entre o trabalhado e a carga (com a tolerância); dia de carga prevista
    já passado sem nenhuma batida desconta a carga inteira. Feriados e folgas têm carga zero, então o trabalho
    nesses dias vira crédito. Folgas de compensação abatem as horas registradas no lançamento, inclusive as
    agendadas. Dias com batidas, mas sem entrada ou saída, ficam fora até o ajuste.

    Com `ate` anterior a hoje, o saldo para nesse dia: só contam os dias e as compensações até ele.
    """
    hoje = timezone.localdate()
    limite = min(ate, hoje) if ate else hoje
    # O domingo olha a semana seguinte: batidas e feriados vão até 6 dias depois do limite.
    ate_a_semana = limite + timedelta(days=6)
    por_dia = defaultdict(dict)
    registros = RegistroPonto.objects.filter(funcionario=funcionario, ativo=True, data_hora__date__lte=ate_a_semana)
    for registro in registros.only('tipo', 'data_hora'):
        por_dia[timezone.localtime(registro.data_hora).date()][registro.tipo] = registro.data_hora

    folgas_ativas = list(Folga.objects.filter(funcionario=funcionario, ativa=True))
    abatidas = [f for f in folgas_ativas if not ate or ate >= hoje or f.data <= ate]
    saldo = -sum((f.horas_abatidas or timedelta() for f in abatidas), timedelta())
    if not por_dia:
        return saldo

    inicio = min(por_dia)
    vinculos = list(funcionario.perfil.jornadas.all())
    feriados = {
        f.data: f for f in Feriado.objects.filter(dispensa_expediente=True, data__range=(inicio, ate_a_semana))
    }
    folgas = {f.data: f for f in folgas_ativas}
    dias_com_batida = set(por_dia)
    dia = inicio
    while dia <= limite:
        configuracao = configuracao_jornada(funcionario, dia, vinculos, feriados, folgas)
        carga = configuracao['carga']
        horarios = por_dia.get(dia, {})
        if RegistroPonto.ENTRADA in horarios and RegistroPonto.SAIDA in horarios:
            fator = fator_do_dia(funcionario, dia, configuracao, dias_com_batida, vinculos, feriados, folgas)
            saldo += saldo_do_dia(tempo_trabalhado(horarios) * fator, carga)
        elif not horarios and dia < hoje:
            saldo -= carga
        dia += timedelta(days=1)
    return saldo


def aviso_do_dia(usuario, data, configuracao=None):
    """Aviso do painel para um dia sem expediente previsto (folga, feriado ou folga semanal), ou None."""
    configuracao = configuracao or configuracao_jornada(usuario, data)
    folga, feriado = configuracao['folga'], configuracao['feriado']
    if folga:
        quem = folga.lancada_por.get_full_name() if folga.lancada_por else 'sua gestão'
        if folga.tipo == Folga.COMPENSACAO:
            abatidas = formatar_timedelta(folga.horas_abatidas or timedelta())
            return {
                'classe': 'compensacao', 'selo': 'Compensação', 'classe_selo': 'atencao',
                'titulo': f'Folga compensatória lançada por {quem}',
                'texto': f'Abate {abatidas} do seu banco de horas, que fica em '
                         f'{formatar_timedelta(saldo_banco_horas(usuario))}. Motivo: {folga.motivo}',
                'subtitulo': 'Folga compensatória: a jornada de hoje é abatida do seu banco de horas.',
                'jornada': f'Folga · abate {abatidas}',
            }
        return {
            'classe': 'folga', 'selo': 'Folga', 'classe_selo': 'sucesso',
            'titulo': f'Folga lançada por {quem}',
            'texto': f'Dia livre, sem desconto no banco de horas. Motivo: {folga.motivo}',
            'subtitulo': 'Hoje não há expediente previsto.',
            'jornada': 'Folga',
        }
    if feriado:
        return {
            'classe': 'feriado', 'selo': 'Feriado', 'classe_selo': 'info',
            'titulo': f'Feriado: {feriado.nome}',
            'texto': 'Sem expediente previsto. Se você trabalhar, as horas entram como hora extra.',
            'subtitulo': 'Hoje não há expediente previsto.',
            'jornada': 'Sem expediente',
        }
    if not configuracao['util']:
        if configuracao['personalizado']:
            texto = f'Sua jornada {configuracao["nome"]} não prevê trabalho neste dia.'
        else:
            texto = 'Não há expediente previsto aos sábados e domingos.'
        return {
            'classe': 'folga', 'selo': 'Folga', 'classe_selo': 'sucesso',
            'titulo': 'Folga semanal',
            'texto': f'{texto} Se você trabalhar, as horas entram como hora extra.',
            'subtitulo': 'Hoje não há expediente previsto na sua jornada.',
            'jornada': 'Folga',
        }
    return None


def motivo_sem_expediente(configuracao, data):
    """Por que o dia não tem expediente previsto, em texto curto, ou None se tiver."""
    if configuracao['carga_sem_folga']:
        return None
    if configuracao['feriado']:
        return f'feriado ({configuracao["feriado"].nome})'
    if configuracao['personalizado']:
        return f'folga semanal da jornada {configuracao["nome"]}'
    return 'sábado' if data.weekday() == 5 else 'domingo'


def situacao_sem_batida(configuracao):
    """Selo de quem não bateu ponto no dia: Feriado ou Folga quando não há expediente previsto."""
    if configuracao['feriado'] and not configuracao['folga']:
        return 'Feriado', 'info'
    if configuracao['folga'] or not configuracao['util']:
        return 'Folga', 'sucesso'
    return 'Sem entrada', 'neutro'


@transaction.atomic
def lancar_folgas(funcionarios, data, tipo, motivo, responsavel):
    folgas = []
    for funcionario in funcionarios:
        configuracao = configuracao_jornada(funcionario, data)
        folgas.append(Folga.objects.create(
            funcionario=funcionario,
            data=data,
            tipo=tipo,
            horas_abatidas=configuracao['carga_sem_folga'] if tipo == Folga.COMPENSACAO else None,
            motivo=motivo,
            lancada_por=responsavel,
        ))
    return folgas


def cancelar_folga(folga, responsavel):
    folga.ativa = False
    folga.cancelada_por = responsavel
    folga.cancelada_em = timezone.now()
    folga.save(update_fields=['ativa', 'cancelada_por', 'cancelada_em'])


@transaction.atomic
def vincular_jornada(perfil, jornada, inicio):
    Perfil.objects.select_for_update().get(pk=perfil.pk)
    VinculoJornada.objects.update_or_create(
        perfil=perfil,
        inicio=inicio,
        defaults={
            'jornada': jornada,
            'nome': jornada.nome if jornada else '',
            'semana': jornada.semana if jornada else {},
        },
    )


def jornadas_para_listagem():
    jornadas = list(Jornada.objects.all())
    for jornada in jornadas:
        jornada.carga_semanal = sum((duracao_jornada(h) for h in jornada.semana.values()), timedelta())
    return jornadas


def tipos_da_jornada(usuario, data):
    vinculo = jornada_vigente(usuario, data)
    if not vinculo or not vinculo.jornada_id:
        return RegistroPonto.ORDEM_TIPOS
    horarios = vinculo.semana.get(str(data.weekday())) or next(iter(vinculo.semana.values()), [])
    return [tipo for tipo, hora in zip(RegistroPonto.ORDEM_TIPOS, horarios, strict=True) if hora]


def saldos_do_banco(funcionarios):
    """Saldo do banco de horas de cada pessoa, já formatado: {pk: texto}."""
    return {pessoa.pk: formatar_timedelta(saldo_banco_horas(pessoa)) for pessoa in funcionarios}


def efeito_da_folga(funcionarios, dados):
    """Saldo do banco de horas antes e depois da folga, para cada colaborador escolhido no formulário.

    dados é o GET ou POST do lançamento: pessoas (entre as visíveis em funcionarios), data e tipo.
    """
    try:
        data = date.fromisoformat(dados.get('data') or '')
    except ValueError:
        data = None
    escolhidos = funcionarios.filter(pk__in=[i for i in dados.getlist('funcionarios') if i.isdigit()])
    compensacao = dados.get('tipo') == Folga.COMPENSACAO
    linhas = []
    for pessoa in escolhidos:
        saldo = saldo_banco_horas(pessoa)
        abatidas = configuracao_jornada(pessoa, data)['carga_sem_folga'] if data and compensacao else timedelta()
        depois = saldo - abatidas
        linhas.append({
            'pessoa': pessoa,
            'antes': formatar_timedelta(saldo),
            'depois': formatar_timedelta(depois),
            'abatidas': formatar_timedelta(abatidas),
            'negativo': depois < timedelta(),
        })
    return {
        'efeito': linhas,
        'efeito_data': data,
        'efeito_compensacao': compensacao,
        'efeito_insuficiente': [linha['pessoa'].get_full_name() for linha in linhas if linha['negativo']],
    }


def _hora_da_celula(valor):
    """Horário de uma célula da planilha, ou None se estiver vazia. ValueError se não for um horário."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, datetime):
        return valor.time().replace(second=0, microsecond=0)
    if isinstance(valor, time):
        return valor.replace(second=0, microsecond=0)
    if isinstance(valor, timedelta) and timedelta() <= valor < timedelta(days=1):
        return (datetime.min + valor).time().replace(second=0, microsecond=0)
    if isinstance(valor, str):
        return datetime.strptime(valor.strip(), '%H:%M').time()
    raise ValueError(valor)


def _ler_dia_da_planilha(dia, linha, batidas, folgas, avisos):
    marcado = str(linha[PLANILHA_COLUNA_FOLGA - 1] or '').strip().upper() == 'S'
    horas = {}
    for coluna, tipo in COLUNAS_RELATORIO.items():
        valor = linha[coluna - 1] if len(linha) >= coluna else None
        try:
            hora = _hora_da_celula(valor)
        except ValueError:
            avisos.append(f'{dia:%d/%m/%Y}: horário "{valor}" não reconhecido. O dia não foi importado.')
            return
        if hora is not None:
            horas[tipo] = hora

    meia_noite = time(0, 0)
    if marcado:
        if any(hora != meia_noite for hora in horas.values()):
            avisos.append(f'{dia:%d/%m/%Y}: marcado como feriado ou folga; os horários do dia foram ignorados.')
        motivo = MOTIVOS_FOLGA_IMPORTADA_POR_DATA.get(dia, MOTIVO_FOLGA_IMPORTADA)
        folgas.append({'data': dia, 'tipo': Folga.DISPENSA, 'motivo': motivo})
        return
    if not horas:
        return
    # O café fica de fora: nos dias de folga a planilha mantém 16:15 e 16:30 e zera o resto.
    cafe = (RegistroPonto.SAIDA_CAFE, RegistroPonto.VOLTA_CAFE)
    principais = [hora for tipo, hora in horas.items() if tipo not in cafe]
    if principais and all(hora == meia_noite for hora in principais):
        folgas.append({'data': dia, 'tipo': Folga.COMPENSACAO, 'motivo': MOTIVO_COMPENSACAO_IMPORTADA})
        return
    ordenadas = [horas[tipo] for tipo in RegistroPonto.ORDEM_TIPOS if tipo in horas]
    if any(antes >= depois for antes, depois in zip(ordenadas, ordenadas[1:], strict=False)):
        avisos.append(f'{dia:%d/%m/%Y}: os horários estão fora de ordem. O dia não foi importado.')
        return
    batidas.extend((dia, tipo, hora) for tipo, hora in horas.items())


def ler_planilha_ponto(arquivo):
    """Lê a planilha de banco de horas: o CPF da aba Resumo e, nas abas de mês, batidas e folgas.

    Devolve (cpf, batidas, folgas, avisos): batidas como (data, tipo, hora), folgas como dicionários com
    data, tipo e motivo, e avisos dos dias que não puderam ser lidos.
    """
    try:
        livro = load_workbook(arquivo, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError) as exc:
        raise ErroImportacao('Não foi possível abrir o arquivo. Envie a planilha no formato .xlsx.') from exc
    if PLANILHA_ABA_RESUMO not in livro.sheetnames:
        raise ErroImportacao(f'A planilha não tem a aba {PLANILHA_ABA_RESUMO}.')

    linha_cpf, coluna_cpf = PLANILHA_CELULA_CPF
    bruto = livro[PLANILHA_ABA_RESUMO].cell(row=linha_cpf, column=coluna_cpf).value
    if bruto is None:
        raise ErroImportacao('CPF não encontrado na aba Resumo, célula B3.')
    if isinstance(bruto, float) and bruto.is_integer():
        bruto = int(bruto)
    # Digitado como número no Excel, o CPF perde os zeros da frente.
    cpf = ''.join(letra for letra in str(bruto) if letra.isdigit()).zfill(11)
    if len(cpf) != 11:
        raise ErroImportacao('CPF inválido na aba Resumo. Ele deve ter 11 dígitos.')

    batidas, folgas, avisos = [], [], []
    for aba in livro.worksheets:
        if aba.title == PLANILHA_ABA_RESUMO:
            continue
        for linha in aba.iter_rows(min_row=PLANILHA_PRIMEIRA_LINHA, values_only=True):
            dia = linha[PLANILHA_COLUNA_DATA - 1] if linha else None
            if isinstance(dia, datetime):
                dia = dia.date()
            if isinstance(dia, date):
                _ler_dia_da_planilha(dia, linha, batidas, folgas, avisos)
    return cpf, batidas, folgas, avisos


@transaction.atomic
def importar_planilha_ponto(arquivo, responsavel):
    """Grava as batidas e folgas da planilha. Nos dias importados, o que já existia no sistema é substituído.

    Batidas substituídas ficam inativas e entram no histórico; folgas substituídas são canceladas. Dias com
    "S" que já são feriado no sistema ficam como estão.
    """
    cpf, batidas, folgas, avisos = ler_planilha_ponto(arquivo)
    perfil = Perfil.objects.select_related('user').filter(cpf=cpf).first()
    if perfil is None:
        raise ErroImportacao(f'Nenhum colaborador cadastrado com o CPF {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}.')
    pessoa = perfil.user

    hoje = timezone.localdate()
    futuras = sorted({dia for dia, _, _ in batidas if dia > hoje})
    if futuras:
        datas = ', '.join(f'{dia:%d/%m/%Y}' for dia in futuras)
        avisos.append(f'Batidas em datas futuras não foram importadas: {datas}.')
        batidas = [batida for batida in batidas if batida[0] <= hoje]
    dispensas = [folga['data'] for folga in folgas if folga['tipo'] == Folga.DISPENSA]
    feriados = set(Feriado.objects.filter(data__in=dispensas, dispensa_expediente=True).values_list('data', flat=True))
    folgas = [folga for folga in folgas if folga['data'] not in feriados]
    dias = {dia for dia, _, _ in batidas} | {folga['data'] for folga in folgas}

    nome = getattr(arquivo, 'name', '') or 'de ponto'
    motivo = f'Importação da planilha {nome}.'
    substituidas = list(RegistroPonto.objects.filter(funcionario=pessoa, ativo=True, data_hora__date__in=dias))
    HistoricoAlteracaoPonto.objects.bulk_create(
        HistoricoAlteracaoPonto(
            registro=registro,
            tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO,
            realizado_por=responsavel,
            motivo=f'Substituída pela importação da planilha {nome}.',
        )
        for registro in substituidas
    )
    RegistroPonto.objects.filter(pk__in=[registro.pk for registro in substituidas]).update(ativo=False)
    folgas_canceladas = list(Folga.objects.filter(funcionario=pessoa, ativa=True, data__in=dias))
    for folga in folgas_canceladas:
        cancelar_folga(folga, responsavel)

    for dia, tipo, hora in sorted(batidas):
        registro = RegistroPonto.objects.create(
            funcionario=pessoa,
            tipo=tipo,
            data_hora=timezone.make_aware(datetime.combine(dia, hora)),
            registrado_manualmente=True,
            observacao=motivo,
        )
        HistoricoAlteracaoPonto.objects.create(
            registro=registro,
            tipo_acao=HistoricoAlteracaoPonto.CRIACAO_MANUAL,
            realizado_por=responsavel,
            motivo=motivo,
        )
    for folga in sorted(folgas, key=lambda item: item['data']):
        lancar_folgas([pessoa], folga['data'], folga['tipo'], folga['motivo'], responsavel)

    return {
        'pessoa': pessoa,
        'batidas': len(batidas),
        'folgas': len(folgas),
        'batidas_substituidas': len(substituidas),
        'folgas_substituidas': len(folgas_canceladas),
        'avisos': avisos,
    }
