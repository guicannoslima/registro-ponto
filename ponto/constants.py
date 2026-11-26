"""Constantes do app ponto: regras de jornada, limites das telas e textos fixos da interface."""

from datetime import date, timedelta

from .models import RegistroPonto

# ---------------------------------------------------------------------------------------------------------------------
# Regras de jornada
# ---------------------------------------------------------------------------------------------------------------------
JORNADA_DIARIA = timedelta(hours=7, minutes=45)

# Diferenças de até 10 minutos, para mais ou para menos, não entram no saldo do dia
TOLERANCIA_SALDO = timedelta(minutes=10)

# Domingo trabalhado sem expediente previsto: a hora vale o dobro (+100%). Se a semana seguinte, de segunda a
# sábado, tiver folga, feriado ou dia sem expediente não trabalhado (como o sábado), vale 40% a mais.
FATOR_DOMINGO = 2
FATOR_DOMINGO_COM_FOLGA = 1.4

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

# ---------------------------------------------------------------------------------------------------------------------
# Cartão ponto (PDF)
# ---------------------------------------------------------------------------------------------------------------------
EMPRESA_NOME = 'Núcleo Prime de Tecnologias LTDA'
EMPRESA_ENDERECO = 'Av. Belo Horizonte, 397'

# Horário contratual impresso no cartão: pares de entrada e saída, de segunda a sexta
HORARIO_DE_TRABALHO = (('09:00', '12:45'), ('14:00', '16:15'), ('16:30', '18:00'))
DIAS_UTEIS = (0, 1, 2, 3, 4)
DIAS_ABREVIADOS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']

# Reconhecimento facial: vetores normalizados SFace e limites da captura da câmera
FACIAL_LIMIAR = 0.5
FACIAL_MARGEM = 0.08
FOTO_MAX_BYTES = 1024 * 1024
FOTO_MAX_PIXELS = 1280 * 1280

# Administração de usuários
USUARIOS_POR_PAGINA = 25

# Foto escolhida pelo colaborador e confirmação visual da batida
FOTO_PERFIL_MAX_BYTES = 5 * 1024 * 1024
CONFIRMACAO_PONTO_MS = 3000
AVISO_PONTO_MS = 6000
TERMINAL_INATIVIDADE_MS = 30_000
TERMINAL_MANUTENCAO_MS = 5 * 60 * 1000
TERMINAL_SESSAO_SEGUNDOS = 30 * 24 * 60 * 60


# Feriados civis nacionais. Datas religiosas dependem da legislação local.
FERIADOS_NACIONAIS = (
    (1, 1, 'Confraternização Universal'),
    (4, 21, 'Tiradentes'),
    (5, 1, 'Dia do Trabalho'),
    (9, 7, 'Independência do Brasil'),
    (10, 12, 'Nossa Senhora Aparecida'),
    (11, 2, 'Finados'),
    (11, 15, 'Proclamação da República'),
    (11, 20, 'Dia Nacional de Zumbi e da Consciência Negra'),
    (12, 25, 'Natal'),
)

# ---------------------------------------------------------------------------------------------------------------------
# Importação da planilha de banco de horas (ponto retroativo)
# ---------------------------------------------------------------------------------------------------------------------
PLANILHA_MAX_BYTES = 5 * 1024 * 1024
PLANILHA_ABA_RESUMO = 'Resumo'
# CPF do colaborador na aba Resumo: linha 3, coluna B
PLANILHA_CELULA_CPF = (3, 2)
# Nas abas de mês, os dias começam na linha 5: data na coluna A e "S" na coluna C para feriado ou folga
PLANILHA_PRIMEIRA_LINHA = 5
PLANILHA_COLUNA_DATA = 1
PLANILHA_COLUNA_FOLGA = 3

# Colunas D a I das abas de mês, na ordem das batidas
COLUNAS_RELATORIO = {
    4: RegistroPonto.ENTRADA,
    5: RegistroPonto.SAIDA_ALMOCO,
    6: RegistroPonto.VOLTA_ALMOCO,
    7: RegistroPonto.SAIDA_CAFE,
    8: RegistroPonto.VOLTA_CAFE,
    9: RegistroPonto.SAIDA,
}

# Dia marcado com "S" e sem feriado cadastrado vira folga de dispensa com este motivo
MOTIVO_FOLGA_IMPORTADA = 'Folga negociada'
MOTIVOS_FOLGA_IMPORTADA_POR_DATA = {date(2026, 10, 9): 'Day-Off'}
# Dia com os horários em 00:00 vira folga de compensação
MOTIVO_COMPENSACAO_IMPORTADA = 'Compensação do banco de horas'

# ---------------------------------------------------------------------------------------------------------------------
# Lembretes de ponto no navegador
# ---------------------------------------------------------------------------------------------------------------------
LEMBRETE_ANTECEDENCIA_MINUTOS = 5
LEMBRETE_INTERVALO_ATRASO_MINUTOS = 2
LEMBRETE_ATRASO_MAXIMO_MINUTOS = 10
LEMBRETES_PONTO_AJUDA = (
    f'Avisa no navegador {LEMBRETE_ANTECEDENCIA_MINUTOS} minutos antes de cada batida prevista na jornada, '
    f'inclusive o café, na hora certa e, se a batida não for feita, a cada {LEMBRETE_INTERVALO_ATRASO_MINUTOS} '
    f'minutos até {LEMBRETE_ATRASO_MAXIMO_MINUTOS} minutos de atraso. Só funciona com o sistema aberto em uma aba.'
)
# A página consulta o servidor neste intervalo; o servidor decide pelo relógio dele
LEMBRETE_CONSULTA_SEGUNDOS = 30
# Etapas de cada batida, em minutos em relação ao horário previsto: antes, na hora e os atrasos
LEMBRETE_ETAPAS = (
    -LEMBRETE_ANTECEDENCIA_MINUTOS,
    0,
    *range(LEMBRETE_INTERVALO_ATRASO_MINUTOS, LEMBRETE_ATRASO_MAXIMO_MINUTOS + 1, LEMBRETE_INTERVALO_ATRASO_MINUTOS),
)
LEMBRETE_TITULO_ANTES = '{batida} em {minutos}'
LEMBRETE_TITULO_NA_HORA = 'Hora da {batida}'
LEMBRETE_TITULO_ATRASO = '{batida} atrasada há {minutos}'
LEMBRETE_CORPO = 'Prevista para {hora}. Clique para registrar o ponto.'
# O registro segue a ordem das batidas: se uma não foi feita, o botão a gravaria no lugar das seguintes. Por isso só
# a próxima batida pendente tem lembretes; as seguintes não têm, e a primeira delas dá um único alerta de ajuste
LEMBRETE_FALTANTE_TITULO = '{batida} não registrada hoje'
LEMBRETE_FALTANTE_CORPO = 'Sem essa batida, o ponto do dia fica incompleto. Clique para solicitar o ajuste de ponto.'
