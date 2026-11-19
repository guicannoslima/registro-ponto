"""Dados prontos para as telas internas: linha do dia, situação, saldo e datas por extenso."""

from datetime import timedelta

from django.utils import timezone

from .constants import DIAS_ABREVIADOS, DIAS_CURTOS, DIAS_SEMANA, DIAS_UTEIS, JORNADA_DIARIA, MESES, ROTULOS_CURTOS
from .models import RegistroPonto


def data_por_extenso(data):
    """18/11/2026 -> 'Quarta-feira, 18 de novembro'."""
    return f'{DIAS_SEMANA[data.weekday()]}, {data.day} de {MESES[data.month - 1]}'


def dia_curto(data):
    """05/11/2026 -> 'Qui, 05/11'."""
    return f'{DIAS_CURTOS[data.weekday()]}, {data:%d/%m}'


def rotulo_do_dia(data, hoje):
    """Rótulo para agrupar batidas: 'Hoje, 18/11', 'Ontem, 17/11' ou 'Seg, 16/11'."""
    if data == hoje:
        return f'Hoje, {data:%d/%m}'
    if data == hoje - timedelta(days=1):
        return f'Ontem, {data:%d/%m}'
    return dia_curto(data)


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


def formatar_saldo(delta):
    """Saldo do dia com sinal: '+0h50min', '−0h13min' ou '0min' quando zerado pela tolerância."""
    total = int(delta.total_seconds()) // 60
    if total == 0:
        return '0min'
    sinal = '+' if total > 0 else '−'
    horas, minutos = divmod(abs(total), 60)
    return f'{sinal}{horas}h{minutos:02d}min'


def hhmm(delta):
    """Duração no formato do cartão ponto: timedelta(hours=7, minutes=45) -> '07:45'; vazio quando não há valor."""
    if not delta:
        return ''
    minutos = int(delta.total_seconds()) // 60
    return f'{minutos // 60:02d}:{minutos % 60:02d}'


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

        linhas.append({
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
        })

    item['cartao'] = {
        'linhas': linhas,
        'totais': {chave: hhmm(valor) or '00:00' for chave, valor in totais.items()},
        'tem_manual': bool(manuais),
    }
    return item
