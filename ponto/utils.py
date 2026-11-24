"""Formatação de datas e durações e auxiliares de requisição e resposta HTTP."""

from datetime import timedelta
from time import time

from django.http import JsonResponse
from django.urls import reverse

from .constants import DIAS_CURTOS, DIAS_SEMANA, MESES
from .exceptions import CadastroFacialAusente, ErroFacial, FacialIndisponivel


def _limitar_captura(request):
    agora = time()
    anterior = request.session.get('facial_ultima_captura', 0)
    if agora - anterior < 3:
        raise ErroFacial('Aguarde 3 segundos antes de tentar novamente.')
    request.session['facial_ultima_captura'] = agora


def _erro(exc, continuar=True):
    dados = {
        'erro': str(exc),
        'continuar': continuar and not isinstance(exc, (FacialIndisponivel, CadastroFacialAusente)),
    }
    if isinstance(exc, CadastroFacialAusente):
        dados['cadastro_necessario'] = True
    return JsonResponse(
        dados,
        status=503 if isinstance(exc, FacialIndisponivel) else 400,
    )


def _presenca_facial(terminal):
    """Converte a presença guardada na sessão para os dados aceitos pelo serviço."""
    pessoa_id = terminal.get('facial_pessoa_presente')
    if pessoa_id is None:
        return None
    anterior = terminal['facial_resultado_presente']
    return {
        'pessoa_id': pessoa_id,
        'registrado': anterior['status'] == 200,
        'mensagem': anterior['dados'].get('mensagem') or anterior['dados']['erro'],
    }


def _resposta_registro_facial(resultado, terminal=None):
    """Adapta o resultado do serviço para HTTP e guarda a presença na sessão do terminal."""
    if resultado['registrado']:
        dados = {
            'mensagem': resultado['mensagem'],
            'repetido': resultado['repetido'],
            'confirmacao': {
                'nome': resultado['nome_completo'],
                'foto_url': reverse('foto_perfil', args=[resultado['pessoa_id']]) if resultado['tem_foto'] else None,
            },
        }
        status = 200
    else:
        dados = {'erro': resultado['mensagem'], 'continuar': terminal is not None}
        status = 409
    if terminal is not None:
        terminal['facial_pessoa_presente'] = resultado['pessoa_id']
        terminal['facial_resultado_presente'] = {'dados': dados, 'status': status}
    return JsonResponse(dados, status=status)


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


def hhmm_com_sinal(delta):
    """Saldo no formato do cartão ponto, com sinal ASCII para a fonte do PDF: '+56:27', '-06:12' ou '00:00'."""
    minutos = int(delta.total_seconds() / 60)
    if minutos == 0:
        return '00:00'
    sinal = '+' if minutos > 0 else '-'
    horas, resto = divmod(abs(minutos), 60)
    return f'{sinal}{horas:02d}:{resto:02d}'


def formatar_timedelta(delta):
    total = delta.total_seconds()
    
    if total < 0:
        total = abs(total)
        negativo = True
    else: 
        negativo = False

    total = int(total)

    horas = total // 3600
    resto = total % 3600
    minutos = resto // 60

    sinal = '-'
    if negativo:
        return f'{sinal}{horas}h{minutos:02d}min'
    else:
        return f'{horas}h{minutos:02d}min'
