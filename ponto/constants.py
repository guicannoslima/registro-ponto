"""Constantes do app ponto: regras de jornada, limites das telas e textos fixos da interface."""

from datetime import timedelta

from .models import RegistroPonto

# ---------------------------------------------------------------------------------------------------------------------
# Regras de jornada
# ---------------------------------------------------------------------------------------------------------------------
JORNADA_DIARIA = timedelta(hours=7, minutes=45)

# Diferenças de até 10 minutos, para mais ou para menos, não entram no saldo do dia
TOLERANCIA_SALDO = timedelta(minutes=10)

# Espera mínima entre duas batidas, contra cliques repetidos
INTERVALO_MINIMO_MINUTOS = 10

# ---------------------------------------------------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------------------------------------------------
# Períodos, em dias, das batidas listadas em "Bati um ponto errado"; o primeiro é o padrão
DIAS_DE_AJUSTE = (7, 14, 30)

# Abas da página inicial, na ordem; "equipe" só aparece para gestores e administradores
ABAS_DO_PAINEL = ('hoje', 'ontem', 'equipe')

ESCOLHA_DE_BATIDA = [('', 'Selecione a batida')] + RegistroPonto.TIPO_CHOICES

ROTULOS_CURTOS = {
    RegistroPonto.ENTRADA: 'Entrada',
    RegistroPonto.SAIDA_ALMOCO: 'Saída almoço',
    RegistroPonto.VOLTA_ALMOCO: 'Volta almoço',
    RegistroPonto.SAIDA_CAFE: 'Saída café',
    RegistroPonto.VOLTA_CAFE: 'Volta café',
    RegistroPonto.SAIDA: 'Saída',
}

# Texto do botão principal do painel: diz qual batida será gravada
ACAO_REGISTRAR = {
    RegistroPonto.ENTRADA: 'Registrar entrada',
    RegistroPonto.SAIDA_ALMOCO: 'Registrar saída para o almoço',
    RegistroPonto.VOLTA_ALMOCO: 'Registrar volta do almoço',
    RegistroPonto.SAIDA_CAFE: 'Registrar saída para o café',
    RegistroPonto.VOLTA_CAFE: 'Registrar volta do café',
    RegistroPonto.SAIDA: 'Registrar saída',
}

# ---------------------------------------------------------------------------------------------------------------------
# Datas por extenso
# ---------------------------------------------------------------------------------------------------------------------
DIAS_SEMANA = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
DIAS_CURTOS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
MESES = [
    'janeiro',
    'fevereiro',
    'março',
    'abril',
    'maio',
    'junho',
    'julho',
    'agosto',
    'setembro',
    'outubro',
    'novembro',
    'dezembro',
]
