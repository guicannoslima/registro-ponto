from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .calculos import proximo_tipo_ponto
from ponto.models import RegistroPonto
from django.shortcuts import redirect
from django.utils import timezone
from .permissoes import funcionarios_visiveis
from django.contrib import messages
from .models import Perfil

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

@login_required
def equipe(request):
    papel = request.user.perfil.papel
    if papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, "Somente os gestores tem acesso ao Painel de Equipes.")
        return redirect('painel')

    equipe = funcionarios_visiveis(request.user)
    return render(request, 'ponto/equipe.html', {'equipe': equipe})
    