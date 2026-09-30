from datetime import timedelta
from .models import RegistroPonto

def calcular_horas_dia(funcionario,data):
    registros = RegistroPonto.objects.filter(
        funcionario = funcionario, 
        data_hora__date = data,
        ativo = True
    ).order_by('data_hora')

    horarios = {}

    for registro in registros:
        horarios[registro.tipo] = registro.data_hora

    completo = RegistroPonto.ENTRADA in horarios and RegistroPonto.SAIDA in horarios

    tempo_trabalhado = None
    esperado = None
    diferenca = None
    if completo:
        tempo_total = horarios[RegistroPonto.SAIDA] - horarios[RegistroPonto.ENTRADA]
        
        if RegistroPonto.SAIDA_ALMOCO in horarios and RegistroPonto.VOLTA_ALMOCO in horarios:
            tempo_almoco = horarios[RegistroPonto.VOLTA_ALMOCO] - horarios[RegistroPonto.SAIDA_ALMOCO]
        else:
            tempo_almoco = timedelta()
        
        tempo_trabalhado = tempo_total - tempo_almoco
        esperado = timedelta (hours=7, minutes=45)
        diferenca = tempo_trabalhado - esperado
        
    return {
        'tempo_trabalhado': tempo_trabalhado,
        'esperado': esperado,
        'diferenca': diferenca,
        'completo': completo,
        'horarios': horarios,
        }

def calcular_relatorio_periodo(funcionario, data_inicio, data_fim):
    relatorio = []

    data_atual = data_inicio
    while data_atual <= data_fim:
        resultado = calcular_horas_dia(funcionario, data_atual)

        if resultado['completo']:
            relatorio.append({
                'data': data_atual,
                'status': 'Completo',
                'tempo_trabalhado': resultado['tempo_trabalhado'],
                'esperado': resultado['esperado'],
                'diferenca': resultado['diferenca'],
                'horarios': resultado['horarios']
            })
        else:
            relatorio.append({
                'data': data_atual,
                'status': 'Incompleto',
                'horarios': resultado['horarios']
            })
        data_atual += timedelta(days = 1)
    return relatorio

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
    if negativo == True:
        return f'{sinal}{horas}h{minutos}min'
    else:
        return f'{horas}h{minutos}min'

def montar_relatorio(funcionarios, funcionario_escolhido, data_inicio, data_fim, gerar_todos):
    relatorio = []
    
    if gerar_todos is True:
        for funcionario in funcionarios:
            dias_calculados = calcular_relatorio_periodo(funcionario, data_inicio, data_fim)
            resumo = calcular_resumo(dias_calculados)
            relatorio_funcionario = {
            'funcionario': funcionario,
            'relatorio': dias_calculados,
            'horas_normais': resumo['horas_normais'],
            'horas_extras': resumo['horas_extras']
            }
            relatorio.append(relatorio_funcionario)
    else:
        dias_calculados = calcular_relatorio_periodo(funcionario_escolhido, data_inicio, data_fim)
        resumo = calcular_resumo(dias_calculados)
        relatorio_funcionario = {
        'funcionario': funcionario_escolhido,
        'relatorio': dias_calculados,
        'horas_normais': resumo['horas_normais'],
        'horas_extras': resumo['horas_extras']            
        }
    
        relatorio.append(relatorio_funcionario)  

    return relatorio

def calcular_resumo(dias_calculados):
    horas_normais = timedelta()
    horas_extras = timedelta()

    for dia in dias_calculados:
        if dia['status'] == 'Completo':
            horas_normais += dia['tempo_trabalhado']
            if dia['diferenca'] > timedelta():
                horas_extras += dia['diferenca']
    return {
        'horas_normais': horas_normais,
        'horas_extras': horas_extras,
    }