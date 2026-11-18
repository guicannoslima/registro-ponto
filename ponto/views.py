from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa

from .apresentacao import (
    data_por_extenso,
    linha_do_dia,
    preparar_relatorio,
    proximo_tipo,
    rotulo_do_dia,
    situacao,
)
from .calculos import proximo_tipo_ponto
from .constants import (
    ABAS_DO_PAINEL,
    ACAO_REGISTRAR,
    DIAS_DE_AJUSTE,
    INTERVALO_MINIMO_MINUTOS,
    JORNADA_DIARIA,
    TOLERANCIA_SALDO,
)
from .forms import (
    CadastroForm,
    HistoricoFiltroForm,
    MotivoExclusaoForm,
    MotivoRejeicaoForm,
    RegistroManualForm,
    RelatorioForm,
    SolicitarCriacaoForm,
    SolicitarExclusaoForm,
)
from .models import HistoricoAlteracaoPonto, Perfil, RegistroPonto, SolicitacaoAjustePonto
from .permissoes import funcionarios_visiveis
from .relatorios import calcular_horas_dia, calcular_progresso, formatar_timedelta, montar_relatorio


def _registros_do_dia(usuario, data):
    return list(
        RegistroPonto.objects.filter(funcionario=usuario, data_hora__date=data, ativo=True).order_by('data_hora')
    )


def _linhas_da_equipe(gestor, hoje, agora):
    """Uma linha por pessoa visível ao gestor: batidas do dia, situação, última batida e horas trabalhadas."""
    linhas = []
    equipe_visivel = funcionarios_visiveis(gestor).select_related('perfil__funcao')
    for usuario in equipe_visivel.order_by('first_name', 'last_name'):
        registros = _registros_do_dia(usuario, hoje)
        progresso = calcular_progresso(calcular_horas_dia(usuario, hoje)['horarios'], agora)
        linhas.append({
            'usuario': usuario,
            'linha': linha_do_dia(registros),
            'situacao': situacao(registros),
            'ultima': registros[-1] if registros else None,
            'trabalhado': formatar_timedelta(progresso['tempo_trabalhado']) if registros else None,
        })
    return linhas


@login_required
def painel(request):
    perfil = request.user.perfil
    hoje = timezone.localdate()
    agora = timezone.now()

    registros_hoje = _registros_do_dia(request.user, hoje)
    progresso = calcular_progresso(calcular_horas_dia(request.user, hoje)['horarios'], agora)
    proximo = proximo_tipo(registros_hoje)

    ontem = hoje - timedelta(days=1)
    registros_ontem = _registros_do_dia(request.user, ontem)
    resultado_ontem = calcular_horas_dia(request.user, ontem)

    contexto = {
        'perfil': perfil,
        'titulo_do_dia': data_por_extenso(hoje),
        'linha': linha_do_dia(registros_hoje),
        'registros_hoje': registros_hoje,
        'exclusoes_pendentes': set(
            SolicitacaoAjustePonto.objects.filter(
                funcionario=request.user,
                tipo_acao=SolicitacaoAjustePonto.EXCLUSAO,
                status=SolicitacaoAjustePonto.PENDENTE,
            ).values_list('registro_id', flat=True)
        ),
        'progresso': progresso,
        'tempo_texto': formatar_timedelta(progresso['tempo_trabalhado']),
        'restante_texto': formatar_timedelta(progresso['tempo_restante']),
        'extra_texto': formatar_timedelta(progresso['tempo_extra']),
        'acao_registrar': ACAO_REGISTRAR.get(proximo),
        'jornada_texto': formatar_timedelta(JORNADA_DIARIA),
        'tolerancia_minutos': int(TOLERANCIA_SALDO.total_seconds() // 60),
        'hora_atual': timezone.localtime(agora),
        'ontem': ontem,
        'ontem_titulo': data_por_extenso(ontem),
        'linha_ontem': linha_do_dia(registros_ontem, marcar_proxima=False),
        'registros_ontem': registros_ontem,
        'ontem_completo': resultado_ontem['completo'],
        'ontem_trabalhado': (
            formatar_timedelta(resultado_ontem['tempo_trabalhado']) if resultado_ontem['completo'] else None
        ),
    }

    if perfil.papel != Perfil.PAPEL_FUNCIONARIO:
        funcionarios = funcionarios_visiveis(request.user)
        pendentes = SolicitacaoAjustePonto.objects.filter(
            funcionario__in=funcionarios, status=SolicitacaoAjustePonto.PENDENTE
        ).select_related('funcionario').order_by('criado_em')
        contexto['pendentes_total'] = pendentes.count()
        contexto['pendente_mais_antiga'] = pendentes.first()
        contexto['equipe_linhas'] = _linhas_da_equipe(request.user, hoje, agora)

    abas = ABAS_DO_PAINEL if 'equipe_linhas' in contexto else ABAS_DO_PAINEL[:2]
    aba = request.GET.get('aba')
    contexto['abas'] = abas
    contexto['aba_ativa'] = aba if aba in abas else abas[0]

    return render(request, 'ponto/painel.html', contexto)


@login_required
@require_POST
def bater_ponto(request):
    agora = timezone.now()
    limite = agora - timedelta(minutes=INTERVALO_MINIMO_MINUTOS)
    if RegistroPonto.objects.filter(funcionario=request.user, data_hora__gte=limite, ativo = True, data_hora__lte = agora).exists():
        messages.error(request, f"Você só pode bater ponto a cada {INTERVALO_MINIMO_MINUTOS} minutos.")
        return redirect('painel')
    proximo_tipo = proximo_tipo_ponto(request.user)
    if proximo_tipo:
        RegistroPonto.objects.create(funcionario=request.user, tipo=proximo_tipo, data_hora=agora)
    else:
        messages.error(request, "Todos os pontos do dia foram batidos.")
    return redirect('painel')


@login_required
def equipe(request):
    papel = request.user.perfil.papel
    if papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, "Somente os gestores tem acesso ao Painel de Equipes.")
        return redirect('painel')

    hoje = timezone.localdate()
    agora = timezone.now()
    linhas = _linhas_da_equipe(request.user, hoje, agora)
    return render(request, 'ponto/equipe.html', {'linhas': linhas, 'hoje': hoje, 'agora': timezone.localtime(agora)})


def _contexto_batidas_do_dia(funcionarios, funcionario_id, data_texto):
    """Batidas já registradas da pessoa na data, para o painel lateral do lançamento manual."""
    try:
        funcionario = funcionarios.get(pk=int(funcionario_id))
        data = date.fromisoformat((data_texto or '')[:10])
    except (ValueError, TypeError, User.DoesNotExist):
        return {'funcionario_contexto': None}
    return {
        'funcionario_contexto': funcionario,
        'data_contexto': data,
        'linha_contexto': linha_do_dia(_registros_do_dia(funcionario, data)),
    }


@login_required
def criar_ponto_manual(request):
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente gestores podem lançar pontos manuais.')
        return redirect('painel')

    funcionarios = funcionarios_visiveis(request.user).order_by('first_name', 'last_name')

    if request.GET.get('parcial'):
        contexto = _contexto_batidas_do_dia(funcionarios, request.GET.get('funcionario'), request.GET.get('data'))
        return render(request, 'ponto/_batidas_do_dia.html', contexto)

    if request.method == 'POST':
        form = RegistroManualForm(request.POST, funcionarios=funcionarios)
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
            nome = form.cleaned_data['funcionario'].get_full_name()
            messages.success(request, f'Ponto lançado para {nome}. A alteração está no histórico.')
            return redirect('equipe')
        funcionario_id = request.POST.get('funcionario')
        data_texto = request.POST.get('data_hora')
    else:
        funcionario_id = request.GET.get('funcionario')
        data_texto = request.GET.get('data') or timezone.localdate().isoformat()
        inicial = {}
        if funcionario_id and funcionarios.filter(pk=funcionario_id).exists():
            inicial['funcionario'] = funcionario_id
        form = RegistroManualForm(funcionarios=funcionarios, initial=inicial)

    contexto = {'form': form}
    contexto.update(_contexto_batidas_do_dia(funcionarios, funcionario_id, data_texto))
    return render(request, 'ponto/criar_ponto_manual.html', contexto)


@login_required
def excluir_ponto(request, registro_id):
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente os gestores podem excluir pontos.')
        return redirect('painel')

    registro = get_object_or_404(RegistroPonto, id=registro_id)

    if request.method == 'POST':
        motivo_exclusao = MotivoExclusaoForm(request.POST)
        if motivo_exclusao.is_valid():
            registro.ativo = False
            registro.save()
            HistoricoAlteracaoPonto.objects.create(
                tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO, registro=registro, realizado_por=request.user, motivo=motivo_exclusao.cleaned_data['motivo']
             )
            messages.success(request, 'Batida excluída. A alteração está no histórico.')
            return redirect('equipe')
    else:
        motivo_exclusao = MotivoExclusaoForm()
    return render (request, 'ponto/excluir_ponto.html', {'form': motivo_exclusao, 'registro': registro})


@login_required
def solicitar_criacao(request):
    hoje = timezone.localdate()
    try:
        dias = int(request.GET.get('dias', DIAS_DE_AJUSTE[0]))
    except ValueError:
        dias = DIAS_DE_AJUSTE[0]
    if dias not in DIAS_DE_AJUSTE:
        dias = DIAS_DE_AJUSTE[0]

    pontos_recentes = RegistroPonto.objects.filter(
        funcionario = request.user,
        ativo = True,
        data_hora__date__gte=hoje - timedelta(days=dias),
    ).order_by('-data_hora')
    ids_pendentes = set(SolicitacaoAjustePonto.objects.filter(
        funcionario = request.user,
        tipo_acao=SolicitacaoAjustePonto.EXCLUSAO,
        status = SolicitacaoAjustePonto.PENDENTE
    ).values_list('registro_id', flat=True))

    grupos = []
    for registro in pontos_recentes:
        data = timezone.localtime(registro.data_hora).date()
        if not grupos or grupos[-1]['data'] != data:
            grupos.append({'data': data, 'rotulo': rotulo_do_dia(data, hoje), 'registros': []})
        grupos[-1]['registros'].append(registro)

    proximo_periodo = next((d for d in DIAS_DE_AJUSTE if d > dias), None)

    if request.method == 'POST':
        form = SolicitarCriacaoForm(request.POST)
        if form.is_valid():
            if SolicitacaoAjustePonto.objects.filter(
                funcionario = request.user,
                tipo = form.cleaned_data['tipo'],
                data_hora__date = form.cleaned_data['data_hora'].date(),
                tipo_acao = SolicitacaoAjustePonto.CRIACAO,
                status = SolicitacaoAjustePonto.PENDENTE
            ).exists():
                messages.error(request, "Não foi possível solicitar o ajuste, você já solicitou esse ponto.")
            else:
                SolicitacaoAjustePonto.objects.create(
                    funcionario = request.user,
                    tipo_acao = SolicitacaoAjustePonto.CRIACAO,
                    tipo = form.cleaned_data['tipo'],
                    motivo_funcionario = form.cleaned_data['motivo_funcionario'],
                    data_hora = form.cleaned_data['data_hora']
                    )
                messages.success(request, 'Pedido enviado. Seu gestor vai revisar.')
                return redirect('painel')
    else:
        form = SolicitarCriacaoForm()
    return render(request, 'ponto/solicitar_criacao.html', {
        'form': form,
        'grupos': grupos,
        'ids_pendentes': ids_pendentes,
        'dias': dias,
        'proximo_periodo': proximo_periodo,
    })


@login_required
def solicitar_exclusao(request, registro_id):
    registro = get_object_or_404(RegistroPonto, id=registro_id)
    if registro.funcionario != request.user:
        messages.error(request, 'Somente o usuário pode solicitar o ajuste de ponto.')
        return redirect ('painel')
    if SolicitacaoAjustePonto.objects.filter(
        registro = registro,
        tipo_acao = SolicitacaoAjustePonto.EXCLUSAO,
        status = SolicitacaoAjustePonto.PENDENTE,
    ).exists():
        messages.error(request, "Já existe uma solicitação de exclusão pendente para este ponto.")
        return redirect ('solicitar_criacao')
    if request.method == 'POST':
        form = SolicitarExclusaoForm(request.POST)
        if form.is_valid():
            SolicitacaoAjustePonto.objects.create(
                funcionario=request.user,
                tipo_acao = SolicitacaoAjustePonto.EXCLUSAO,
                registro = registro,
                motivo_funcionario=form.cleaned_data['motivo_funcionario'],
            )
            messages.success(request, 'Pedido enviado. A batida vale até o seu gestor aprovar.')
            return redirect ('solicitar_criacao')
    else:
        form = SolicitarExclusaoForm()
    return render (request, 'ponto/solicitar_exclusao.html', {'form': form, 'registro': registro})


@login_required
def solicitacoes_pendentes(request):
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente gestores podem ver as solicitações pendentes.')
        return redirect ('painel')

    funcionarios = funcionarios_visiveis(request.user)

    solicitacoes = SolicitacaoAjustePonto.objects.filter(
        funcionario__in=funcionarios, status = SolicitacaoAjustePonto.PENDENTE
    ).select_related('funcionario', 'registro').order_by('criado_em')
    return render(request, 'ponto/solicitacoes_pendentes.html', {'solicitacoes': solicitacoes})


@login_required
def rejeitar_solicitacao(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoAjustePonto, id=solicitacao_id)
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente gestores tem acesso a essa página.')
        return redirect ('painel')

    if request.method == 'POST':
        motivo_rejeicao = MotivoRejeicaoForm(request.POST)
        if motivo_rejeicao.is_valid():
            solicitacao.status = SolicitacaoAjustePonto.REJEITADO
            solicitacao.motivo_rejeicao = motivo_rejeicao.cleaned_data['motivo_rejeicao']
            solicitacao.gestor_revisor = request.user
            solicitacao.save()
            messages.success(request, f'Solicitação de {solicitacao.funcionario.get_full_name()} rejeitada.')
            return redirect ('solicitacoes_pendentes')
    else:
        motivo_rejeicao = MotivoRejeicaoForm()
    return render (request, 'ponto/rejeitar_solicitacao.html', {'solicitacao': solicitacao, 'motivo_rejeicao': motivo_rejeicao})


@login_required
@require_POST
def aprovar_solicitacao(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoAjustePonto, id=solicitacao_id)
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente gestores podem aprovar.')
        return redirect ('painel')
    if solicitacao.tipo_acao == SolicitacaoAjustePonto.CRIACAO:
        registro = RegistroPonto.objects.create(
            tipo = solicitacao.tipo,
            data_hora = solicitacao.data_hora,
            funcionario = solicitacao.funcionario
            )
        HistoricoAlteracaoPonto.objects.create(
            registro = registro,
            tipo_acao = HistoricoAlteracaoPonto.CRIACAO_MANUAL,
            realizado_por=request.user,
            motivo = solicitacao.motivo_funcionario
        )
        solicitacao.status = SolicitacaoAjustePonto.APROVADO
        solicitacao.gestor_revisor = request.user
        solicitacao.save()
        nome = solicitacao.funcionario.get_full_name()
        messages.success(request, f'Solicitação de {nome} aprovada. A batida foi incluída.')
        return redirect('solicitacoes_pendentes')
    else:
        registro = solicitacao.registro
        registro.ativo = False
        registro.save()
        HistoricoAlteracaoPonto.objects.create(
            tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO,
            registro= solicitacao.registro,
            realizado_por=request.user,
            motivo = solicitacao.motivo_funcionario
        )

        solicitacao.status = SolicitacaoAjustePonto.APROVADO
        solicitacao.gestor_revisor = request.user
        solicitacao.save()
        nome = solicitacao.funcionario.get_full_name()
        messages.success(request, f'Solicitação de {nome} aprovada. A batida foi excluída.')
        return redirect('solicitacoes_pendentes')


@login_required
def historico_alteracoes(request):
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente gestores tem acesso a essa página.')
        return redirect ('painel')
    funcionarios = funcionarios_visiveis(request.user).order_by('first_name', 'last_name')

    historico = HistoricoAlteracaoPonto.objects.filter(
        registro__funcionario__in=funcionarios
    ).select_related('registro__funcionario', 'realizado_por').order_by('-criado_em')

    filtro = HistoricoFiltroForm(request.GET or None, funcionarios=funcionarios)
    if filtro.is_valid():
        if filtro.cleaned_data['funcionario']:
            historico = historico.filter(registro__funcionario=filtro.cleaned_data['funcionario'])
        if filtro.cleaned_data['acao']:
            historico = historico.filter(tipo_acao=filtro.cleaned_data['acao'])
        if filtro.cleaned_data['de']:
            historico = historico.filter(criado_em__date__gte=filtro.cleaned_data['de'])
        if filtro.cleaned_data['ate']:
            historico = historico.filter(criado_em__date__lte=filtro.cleaned_data['ate'])

    return render (request, 'ponto/historico_alteracoes.html', {
        'historico': historico,
        'filtro': filtro,
        'filtrado': bool(request.GET),
    })


@login_required
def relatorio_ponto(request):
    eh_funcionario =  request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO
    if eh_funcionario:
        funcionarios = User.objects.filter(pk=request.user.pk)
    else:
        funcionarios = funcionarios_visiveis(request.user).order_by('first_name', 'last_name')

    relatorio = None

    if request.method == 'POST':
        form = RelatorioForm(request.POST, funcionarios= funcionarios, permite_todos= not eh_funcionario)
        if form.is_valid():
            data_inicio = form.cleaned_data['data_inicio']
            data_fim = form.cleaned_data['data_fim']
            gerar_todos = form.cleaned_data.get('gerar_todos')
            funcionario_escolhido = form.cleaned_data['funcionario']
            relatorio = preparar_relatorio(
                montar_relatorio(funcionarios, funcionario_escolhido, data_inicio, data_fim, gerar_todos)
            )
    else:
        form = RelatorioForm(funcionarios = funcionarios, permite_todos= not eh_funcionario)
    return render(request, 'ponto/relatorio_ponto.html', {
        'form': form,
        'relatorio': relatorio,
        'eh_funcionario': eh_funcionario,
        'tolerancia_minutos': int(TOLERANCIA_SALDO.total_seconds() // 60),
    })


@login_required
@require_POST
def exportar_relatorio_pdf(request):
    eh_funcionario = request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO
    if eh_funcionario:
        funcionarios = User.objects.filter(pk=request.user.pk)
    else:
        funcionarios = funcionarios_visiveis(request.user)

    form = RelatorioForm(request.POST, funcionarios=funcionarios, permite_todos=not eh_funcionario)
    if form.is_valid():
        data_inicio = form.cleaned_data['data_inicio']
        data_fim = form.cleaned_data['data_fim']
        gerar_todos = form.cleaned_data.get('gerar_todos')
        funcionario_escolhido = form.cleaned_data['funcionario']
        relatorio = montar_relatorio(funcionarios, funcionario_escolhido, data_inicio, data_fim, gerar_todos)

        template = get_template('ponto/relatorio_pdf.html')
        html = template.render({'relatorio': relatorio})
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="relatorio.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response)

        if pisa_status.err:
            return HttpResponse('Erro ao gerar PDF')
        else:
            return response
    else:
        messages.error(request, 'Formulário inválido, verifique os dados e tente novamente.')
        return redirect('relatorio_ponto')

def cadastro_usuario(request):
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=form.cleaned_data['email'],
            )
            # O Perfil já foi criado pelo signal post_save do User; aqui só completamos os dados do cadastro
            perfil = user.perfil
            perfil.cpf = form.cleaned_data['cpf']
            perfil.papel = Perfil.PAPEL_FUNCIONARIO
            perfil.funcao = form.cleaned_data['funcao']
            perfil.save()
            messages.success(request, 'Usuário cadastrado com sucesso.')
            return redirect('login')
    else:
        form = CadastroForm()
    return render(request, 'ponto/cadastro_usuario.html', {'form': form})