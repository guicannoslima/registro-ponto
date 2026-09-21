from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .calculos import proximo_tipo_ponto
from ponto.models import RegistroPonto
from django.shortcuts import redirect
from django.utils import timezone

@login_required
def painel(request):
    perfil = request.user.perfil
    hoje = timezone.localdate()
    registro_hoje = RegistroPonto.objects.filter(funcionario=request.user, data_hora__date=hoje, ativo = True)
    return render(request, 'ponto/painel.html', {'perfil': perfil, 'registro_hoje': registro_hoje})

@login_required
@require_POST
def bater_ponto(request):
    proximo_tipo = proximo_tipo_ponto(request.user)
    if proximo_tipo:
        RegistroPonto.objects.create(funcionario=request.user, tipo=proximo_tipo, data_hora=timezone.now())
    return redirect('painel')