from django.template.library import Library

from ponto.constants import LEMBRETE_CONSULTA_SEGUNDOS
from ponto.utils import formatar_timedelta

register = Library()


@register.simple_tag
def lembrete_consulta_segundos():
    """Intervalo da consulta de lembretes de ponto, lido pelo script das telas internas."""
    return LEMBRETE_CONSULTA_SEGUNDOS


@register.filter
def ponto_filter(delta):
    resultado = formatar_timedelta(delta)
    return resultado