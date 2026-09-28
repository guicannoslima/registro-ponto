from django.template.library import Library
from ponto.relatorios import formatar_timedelta

register = Library()

@register.filter
def ponto_filter(delta):
    resultado = formatar_timedelta(delta)
    return resultado