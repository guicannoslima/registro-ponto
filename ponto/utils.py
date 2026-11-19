"""Utilitários de acesso, captura e respostas do reconhecimento facial."""

from time import time

from django.contrib.auth.models import User
from django.http import JsonResponse

from .exceptions import ErroFacial, FacialIndisponivel
from .models import Perfil
from .permissoes import funcionarios_visiveis


def _gestor(usuario):
    return usuario.is_authenticated and usuario.is_active and usuario.perfil.papel in (
        Perfil.PAPEL_GESTOR, Perfil.PAPEL_ADMIN,
    )


def _pessoas(usuario):
    return (funcionarios_visiveis(usuario) | User.objects.filter(pk=usuario.pk)).filter(is_active=True)


def _limitar_captura(request):
    agora = time()
    anterior = request.session.get('facial_ultima_captura', 0)
    if agora - anterior < 3:
        raise ErroFacial('Aguarde 3 segundos antes de tentar novamente.')
    request.session['facial_ultima_captura'] = agora


def _erro(exc, continuar=True):
    return JsonResponse(
        {'erro': str(exc), 'continuar': continuar and not isinstance(exc, FacialIndisponivel)},
        status=503 if isinstance(exc, FacialIndisponivel) else 400,
    )
