from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .calculos import proximo_tipo_ponto
from ponto.models import RegistroPonto
from django.shortcuts import redirect
from django.utils import timezone
from .permissoes import funcionarios_visiveis
from django.contrib import messages
from .models import Perfil, HistoricoAlteracaoPonto, SolicitacaoAjustePonto
from .forms import RegistroManualForm, MotivoExclusaoForm, SolicitarCriacaoForm, SolicitarExclusaoForm

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
    hoje = timezone.localdate()
    equipe_com_registros = []

    for usuario in equipe:
        registro_do_usuario = RegistroPonto.objects.filter(funcionario=usuario, data_hora__date=hoje, ativo=True)
        equipe_com_registros.append((usuario, registro_do_usuario))
    
    return render(request, 'ponto/equipe.html', {'equipe':  equipe_com_registros})

@login_required
def criar_ponto_manual(request):
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente gestores podem lançar pontos manuais.')
        return redirect('painel')

    if request.method == 'POST':
        form = RegistroManualForm(request.POST)
        if form.is_valid():
            registros_pontos = RegistroPonto.objects.create(
            funcionario=form.cleaned_data['funcionario'],
            tipo = form.cleaned_data['tipo'],
            data_hora = form.cleaned_data['data_hora'],
            registrado_manualmente = True
            )
            HistoricoAlteracaoPonto.objects.create(
            registro = registros_pontos,
            tipo_acao = HistoricoAlteracaoPonto.CRIACAO_MANUAL,
            realizado_por=request.user,
            motivo=form.cleaned_data['motivo'])
            return redirect('equipe')
    else:
        form = RegistroManualForm()
    return render(request, 'ponto/criar_ponto_manual.html', {'form': form})

@login_required
def excluir_ponto(request, registro_id):
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente os gestores podem excluir pontos.')
        return redirect('painel')

    registro = RegistroPonto.objects.get(id=registro_id)

    if request.method == 'POST':
        motivo_exclusao = MotivoExclusaoForm(request.POST)
        if motivo_exclusao.is_valid():
            registro.ativo = False
            registro.save()
            HistoricoAlteracaoPonto.objects.create(
                tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO, registro=registro, realizado_por=request.user, motivo=motivo_exclusao.cleaned_data['motivo']
             )
            return redirect('painel')
    else:
        motivo_exclusao = MotivoExclusaoForm()
    return render (request, 'ponto/excluir_ponto.html', {'form': motivo_exclusao, 'registro': registro})

@login_required
def solicitar_criacao(request):
    if request.method == 'POST':
        form = SolicitarCriacaoForm(request.POST)
        if form.is_valid():
            SolicitacaoAjustePonto.objects.create(
                funcionario = request.user,
                tipo_acao = SolicitacaoAjustePonto.CRIACAO,
                tipo = form.cleaned_data['tipo'],
                motivo_funcionario = form.cleaned_data['motivo_funcionario'],
                data_hora = form.cleaned_data['data_hora']
                )
            return redirect('painel')
    else:
        form = SolicitarCriacaoForm()
    return render (request, 'ponto/solicitar_criacao.html', {'form': form})

@login_required
def solicitar_exclusao(request, registro_id):
    registro = RegistroPonto.objects.get(id=registro_id)
    if registro.funcionario != request.user:
        messages.error(request, 'Somente o usuário pode solicitar o ajuste de ponto.')
        return redirect ('painel')
    if request.method == 'POST':
        form = SolicitarExclusaoForm(request.POST)
        if form.is_valid():
            SolicitacaoAjustePonto.objects.create(
                funcionario=request.user,
                tipo_acao = SolicitacaoAjustePonto.EXCLUSAO,
                registro = registro,
                motivo_funcionario=form.cleaned_data['motivo_funcionario'],
            )
            return redirect ('painel')
    else:
        form = SolicitarExclusaoForm()
    return render (request, 'ponto/solicitar_exclusao.html', {'form': form, 'registro': registro})