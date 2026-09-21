from django.utils import timezone
from ponto.models import RegistroPonto

def proximo_tipo_ponto(funcionario):
    hoje = timezone.localdate()
    registros = RegistroPonto.objects.filter(funcionario=funcionario, data_hora__date=hoje)
    batidas_registradas = registros.values_list('tipo', flat=True)

    for tipo in RegistroPonto.ORDEM_TIPOS:
        if tipo not in batidas_registradas:
            return tipo