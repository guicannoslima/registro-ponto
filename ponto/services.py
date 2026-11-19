"""Regras, consultas e preparação dos dados de negócio do registro de ponto."""

from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from PIL import Image, ImageOps

from .constants import (
    DIAS_ABREVIADOS,
    DIAS_UTEIS,
    FACIAL_LIMIAR,
    INTERVALO_MINIMO_MINUTOS,
    JORNADA_DIARIA,
    ROTULOS_CURTOS,
)
from .exceptions import CadastroFacialAusente, ErroBatida, ErroFacial
from .facial import extrair_vetor, identificar
from .models import CadastroFacial, Perfil, RegistroPonto
from .permissoes import funcionarios_visiveis
from .utils import hhmm


def proximo_tipo(registros):
    """O primeiro tipo da ordem do dia ainda sem batida, ou None quando o dia está completo."""
    feitos = {r.tipo for r in registros}
    for tipo in RegistroPonto.ORDEM_TIPOS:
        if tipo not in feitos:
            return tipo
    return None


def linha_do_dia(registros, marcar_proxima=True):
    """As 6 batidas na ordem do dia, cada uma com o registro (ou None) e se é a próxima.

    Para um dia que já passou, marcar_proxima=False deixa as batidas que faltaram só como pendentes.
    """
    por_tipo = {r.tipo: r for r in registros}
    proximo = proximo_tipo(registros) if marcar_proxima else None
    nomes = dict(RegistroPonto.TIPO_CHOICES)
    return [
        {
            'tipo': tipo,
            'rotulo': ROTULOS_CURTOS[tipo],
            'nome': nomes[tipo],
            'registro': por_tipo.get(tipo),
            'proxima': tipo == proximo,
        }
        for tipo in RegistroPonto.ORDEM_TIPOS
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
    linhas = []
    for dia in item['relatorio']:
        data, horarios = dia['data'], dia['horarios']
        util = data.weekday() in DIAS_UTEIS
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
            carga = JORNADA_DIARIA if util else None
            observacao = 'Incompleto'
        elif util and data < hoje:
            carga = faltas = JORNADA_DIARIA
            observacao = 'Falta'

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

    item['cartao'] = {
        'linhas': linhas,
        'totais': {chave: hhmm(valor) or '00:00' for chave, valor in totais.items()},
        'tem_manual': bool(manuais),
    }
    return item


def proximo_tipo_ponto(funcionario):
    hoje = timezone.localdate()
    registros = RegistroPonto.objects.filter(funcionario=funcionario, data_hora__date=hoje, ativo=True)
    batidas_registradas = registros.values_list('tipo', flat=True)

    for tipo in RegistroPonto.ORDEM_TIPOS:
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
            imagem = ImageOps.fit(ImageOps.exif_transpose(original).convert('RGB'), (512, 512))
            conteudo = BytesIO()
            imagem.save(conteudo, 'JPEG', quality=85)
        perfil.foto.save(f'{uuid4().hex}.jpg', ContentFile(conteudo.getvalue()), save=False)
    perfil.save(update_fields=['foto'])
    if antiga and antiga != perfil.foto.name:
        transaction.on_commit(lambda: storage.delete(antiga))


def obter_foto_perfil(usuario, usuario_id):
    perfil = Perfil.objects.filter(user_id=usuario_id, user__in=_pessoas(usuario)).first()
    return perfil.foto if perfil and perfil.foto else None


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
