"""Dados prontos para as telas internas: linha do dia, situação, saldo e datas por extenso."""

from datetime import timedelta

from .constants import DIAS_CURTOS, DIAS_SEMANA, MESES, ROTULOS_CURTOS
from .models import RegistroPonto
from .relatorios import formatar_timedelta


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


def preparar_relatorio(relatorio):
    """Acrescenta ao relatório os textos da tela: dia curto, saldo com sinal e totais formatados.

    Sábados e domingos sem nenhuma batida ficam fora da tabela, mas continuam no PDF.
    """
    for item in relatorio:
        dias = []
        incompletos = 0
        for dia in item['relatorio']:
            if dia['data'].weekday() >= 5 and not dia['horarios']:
                continue
            completo = dia['status'] == 'Completo'
            linha = {'data': dia['data'], 'rotulo': dia_curto(dia['data']), 'completo': completo}
            if completo:
                diferenca = dia['diferenca']
                linha.update(
                    trabalhado=formatar_timedelta(dia['tempo_trabalhado']),
                    esperado=formatar_timedelta(dia['esperado']),
                    saldo=formatar_saldo(diferenca),
                    saldo_classe='positivo'
                    if diferenca > timedelta()
                    else 'negativo'
                    if diferenca < timedelta()
                    else '',
                )
            else:
                incompletos += 1
            dias.append(linha)
        item.update(
            dias=dias,
            dias_incompletos=incompletos,
            horas_normais_texto=formatar_timedelta(item['horas_normais']),
            horas_extras_texto=formatar_timedelta(item['horas_extras']),
        )
    return relatorio
