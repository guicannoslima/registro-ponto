from datetime import date, datetime, time, timedelta
from functools import wraps
from smtplib import SMTPException
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods, require_POST
from xhtml2pdf import pisa

from .constants import (
    ABAS_DO_PAINEL,
    ACAO_REGISTRAR,
    AVISO_PONTO_MS,
    CONFIRMACAO_PONTO_MS,
    DIAS_DE_AJUSTE,
    EMPRESA_ENDERECO,
    EMPRESA_NOME,
    TERMINAL_INATIVIDADE_MS,
    TERMINAL_MANUTENCAO_MS,
    TERMINAL_SESSAO_SEGUNDOS,
    TOLERANCIA_SALDO,
    USUARIOS_POR_PAGINA,
)
from .email import BackendEmail
from .exceptions import ErroBatida, ErroFacial, ErroImportacao, SemRosto
from .forms import (
    AnoFeriadosForm,
    CadastroForm,
    ConfiguracaoEmailForm,
    FeriadoForm,
    FolgaForm,
    FotoPerfilForm,
    HistoricoFiltroForm,
    ImportarPlanilhaForm,
    JornadaForm,
    MotivoExclusaoForm,
    MotivoRejeicaoForm,
    RegistroManualForm,
    RelatorioForm,
    SolicitarCriacaoForm,
    SolicitarExclusaoForm,
    TesteEmailForm,
    UsuarioAdministracaoForm,
)
from .models import (
    ConfiguracaoEmail,
    Feriado,
    Folga,
    HistoricoAlteracaoPonto,
    Jornada,
    Perfil,
    RegistroPonto,
    SolicitacaoAjustePonto,
)
from .permissoes import funcionarios_visiveis
from .relatorios import calcular_horas_dia, calcular_progresso, montar_relatorio
from .services import (
    _gestor,
    aviso_do_dia,
    cancelar_folga,
    configuracao_jornada,
    efeito_da_folga,
    estado_cadastro_facial,
    importar_planilha_ponto,
    jornadas_para_listagem,
    lancar_folgas,
    linha_do_dia,
    obter_foto_perfil,
    pessoas_para_cadastro_facial,
    pessoas_para_relatorio,
    preparar_cartao_ponto,
    registrar_batida,
    registrar_ponto_facial,
    remover_cadastro_facial,
    saldos_do_banco,
    salvar_cadastro_facial,
    salvar_foto_perfil,
    sincronizar_feriados_nacionais,
    situacao,
    situacao_sem_batida,
    tem_cadastro_facial,
    tipos_da_jornada,
)
from .utils import (
    _erro,
    _limitar_captura,
    _presenca_facial,
    _resposta_registro_facial,
    data_por_extenso,
    formatar_timedelta,
    rotulo_do_dia,
)


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
        configuracao = configuracao_jornada(usuario, hoje)
        progresso = calcular_progresso(calcular_horas_dia(usuario, hoje)['horarios'], agora, configuracao['carga'])
        linhas.append({
            'usuario': usuario,
            'linha': linha_do_dia(registros, usuario=usuario, data=hoje),
            'situacao': situacao(registros) if registros else situacao_sem_batida(configuracao),
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
    configuracao = configuracao_jornada(request.user, hoje)
    progresso = calcular_progresso(calcular_horas_dia(request.user, hoje)['horarios'], agora, configuracao['carga'])
    feitos = {r.tipo for r in registros_hoje}
    proximo = next((t for t in tipos_da_jornada(request.user, hoje) if t not in feitos), None)

    ontem = hoje - timedelta(days=1)
    registros_ontem = _registros_do_dia(request.user, ontem)
    resultado_ontem = calcular_horas_dia(request.user, ontem)

    contexto = {
        'perfil': perfil,
        'titulo_do_dia': data_por_extenso(hoje),
        'linha': linha_do_dia(registros_hoje, usuario=request.user, data=hoje),
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
        'jornada_texto': formatar_timedelta(configuracao['carga']),
        'aviso': aviso_do_dia(request.user, hoje, configuracao),
        'aviso_ontem': aviso_do_dia(request.user, ontem),
        'tolerancia_minutos': int(TOLERANCIA_SALDO.total_seconds() // 60),
        'hora_atual': timezone.localtime(agora),
        'ontem': ontem,
        'ontem_titulo': data_por_extenso(ontem),
        'linha_ontem': linha_do_dia(registros_ontem, marcar_proxima=False, usuario=request.user, data=ontem),
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
    try:
        registrar_batida(request.user)
    except ErroBatida as exc:
        messages.error(request, str(exc))
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
    registros = _registros_do_dia(funcionario, data)
    linha = linha_do_dia(registros)
    na_linha = {passo['registro'].pk for passo in linha if passo['registro']}
    return {
        'funcionario_contexto': funcionario,
        'data_contexto': data,
        'linha_contexto': linha,
        # Batidas repetidas do mesmo tipo ficam fora da linha; aparecem à parte para poderem ser excluídas.
        'repetidas_contexto': [registro for registro in registros if registro.pk not in na_linha],
    }


def _destino_apos_exclusao(request, registro):
    """Volta ao lançamento manual com a pessoa e o dia da batida quando a exclusão veio de lá; senão, à Equipe."""
    if request.GET.get('voltar') == 'manual':
        parametros = urlencode({
            'funcionario': registro.funcionario_id,
            'data': timezone.localtime(registro.data_hora).date().isoformat(),
        })
        return f"{reverse('criar_ponto_manual')}?{parametros}"
    return reverse('equipe')


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
        try:
            # Volta de uma exclusão: o formulário já abre no dia que estava sendo ajustado; falta só a hora.
            inicial['data_hora'] = datetime.combine(date.fromisoformat(request.GET.get('data', '')), time())
        except ValueError:
            pass
        form = RegistroManualForm(funcionarios=funcionarios, initial=inicial)

    contexto = {'form': form}
    contexto.update(_contexto_batidas_do_dia(funcionarios, funcionario_id, data_texto))
    return render(request, 'ponto/criar_ponto_manual.html', contexto)


@login_required
def excluir_ponto(request, registro_id):
    if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
        messages.error(request, 'Somente os gestores podem excluir pontos.')
        return redirect('painel')

    # Só batidas ativas de quem o usuário enxerga: gestor exclui da própria equipe, administrador de todos.
    registro = get_object_or_404(
        RegistroPonto, id=registro_id, ativo=True, funcionario__in=funcionarios_visiveis(request.user)
    )
    destino = _destino_apos_exclusao(request, registro)

    if request.method == 'POST':
        motivo_exclusao = MotivoExclusaoForm(request.POST)
        if motivo_exclusao.is_valid():
            registro.ativo = False
            registro.save()
            HistoricoAlteracaoPonto.objects.create(
                tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO,
                registro=registro,
                realizado_por=request.user,
                motivo=motivo_exclusao.cleaned_data['motivo'],
            )
            messages.success(request, 'Batida excluída. A alteração está no histórico.')
            return redirect(destino)
    else:
        motivo_exclusao = MotivoExclusaoForm()
    return render(request, 'ponto/excluir_ponto.html', {
        'form': motivo_exclusao,
        'registro': registro,
        'destino': destino,
        'veio_do_manual': request.GET.get('voltar') == 'manual',
    })


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


def _cartao_ponto_pdf(funcionarios, dados, inline):
    """Gera o PDF do cartão ponto a partir dos dados validados do RelatorioForm."""
    data_inicio, data_fim = dados['data_inicio'], dados['data_fim']
    relatorio = montar_relatorio(
        funcionarios, dados['funcionario'], data_inicio, data_fim, dados.get('gerar_todos')
    )
    for item in relatorio:
        preparar_cartao_ponto(item, data_inicio, data_fim)

    html = get_template('ponto/relatorio_pdf.html').render({
        'relatorio': relatorio,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'emitido_em': timezone.localtime(),
        'logo': finders.find('ponto/logo.png'),
        'empresa_nome': EMPRESA_NOME,
        'empresa_endereco': EMPRESA_ENDERECO,
        'tolerancia': int(TOLERANCIA_SALDO.total_seconds() // 60),
    })
    response = HttpResponse(content_type='application/pdf')
    disposicao = 'inline' if inline else 'attachment'
    nome_arquivo = f'cartao-ponto-{data_inicio:%Y%m%d}-{data_fim:%Y%m%d}.pdf'
    response['Content-Disposition'] = f'{disposicao}; filename="{nome_arquivo}"'
    if pisa.CreatePDF(html, dest=response).err:
        return HttpResponse('Não foi possível gerar o PDF. Tente novamente.', status=500)
    return response


def _parametros_do_relatorio(dados):
    """Query string que reproduz o filtro validado, usada pelo iframe do PDF."""
    parametros = {
        'data_inicio': dados['data_inicio'].isoformat(),
        'data_fim': dados['data_fim'].isoformat(),
    }
    if dados['funcionario']:
        parametros['funcionario'] = dados['funcionario'].pk
    if dados.get('gerar_todos'):
        parametros['gerar_todos'] = 'on'
    return urlencode(parametros)


@login_required
def relatorio_ponto(request):
    funcionarios, eh_funcionario = pessoas_para_relatorio(request.user)
    contexto = {}

    if request.method == 'POST':
        form = RelatorioForm(request.POST, funcionarios=funcionarios, permite_todos=not eh_funcionario)
        if form.is_valid():
            dados = form.cleaned_data
            contexto['pdf_url'] = f"{reverse('visualizar_relatorio_pdf')}?{_parametros_do_relatorio(dados)}"
            if dados.get('gerar_todos'):
                contexto['titulo_pdf'] = 'Cartão ponto da equipe'
            else:
                contexto['titulo_pdf'] = f"Cartão ponto de {dados['funcionario'].get_full_name()}"
            contexto['periodo_pdf'] = dados
    else:
        form = RelatorioForm(funcionarios=funcionarios, permite_todos=not eh_funcionario)

    contexto['form'] = form
    return render(request, 'ponto/relatorio_ponto.html', contexto)


@login_required
@require_POST
def exportar_relatorio_pdf(request):
    """Baixar PDF: o cartão ponto como anexo."""
    funcionarios, eh_funcionario = pessoas_para_relatorio(request.user)
    form = RelatorioForm(request.POST, funcionarios=funcionarios, permite_todos=not eh_funcionario)
    if form.is_valid():
        return _cartao_ponto_pdf(funcionarios, form.cleaned_data, inline=False)
    messages.error(request, 'Formulário inválido, verifique os dados e tente novamente.')
    return redirect('relatorio_ponto')


@login_required
@xframe_options_sameorigin
def visualizar_relatorio_pdf(request):
    """Gerar relatório: o mesmo cartão ponto exibido no navegador, dentro do iframe da página de relatório."""
    funcionarios, eh_funcionario = pessoas_para_relatorio(request.user)
    form = RelatorioForm(request.GET, funcionarios=funcionarios, permite_todos=not eh_funcionario)
    if not form.is_valid():
        return HttpResponse('Filtro do relatório inválido. Gere o relatório de novo.', status=400)
    return _cartao_ponto_pdf(funcionarios, form.cleaned_data, inline=True)


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


@login_required
@require_http_methods(['GET', 'POST'])
def cadastro_facial(request):
    if not _gestor(request.user):
        return HttpResponseForbidden('Somente gestores podem cadastrar rostos.')
    pessoas = pessoas_para_cadastro_facial(request.user)
    if request.method == 'POST' or request.GET.get('estado') == '1':
        dados = request.POST if request.method == 'POST' else request.GET
        try:
            pessoa_id = int(dados.get('funcionario', ''))
        except ValueError as exc:
            raise Http404 from exc
        pessoa = get_object_or_404(pessoas, pk=pessoa_id)
        if request.method == 'GET':
            return JsonResponse(estado_cadastro_facial(pessoa))
        if request.POST.get('acao') == 'excluir':
            return JsonResponse(remover_cadastro_facial(pessoa))
        try:
            _limitar_captura(request)
            resultado = salvar_cadastro_facial(pessoa, request.FILES.get('foto'), request.user)
        except ErroFacial as exc:
            return _erro(exc)
        return JsonResponse(resultado)
    return render(request, 'ponto/camera.html', {
        'modo': 'cadastro', 'pessoas': pessoas, 'confirmacao_ms': CONFIRMACAO_PONTO_MS,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def ponto_facial(request):
    if request.method == 'GET':
        return render(request, 'ponto/camera.html', {
            'modo': 'pessoal', 'tem_cadastro': tem_cadastro_facial(request.user),
            'confirmacao_ms': CONFIRMACAO_PONTO_MS,
            'aviso_ms': AVISO_PONTO_MS,
        })
    try:
        _limitar_captura(request)
        resultado = registrar_ponto_facial(request.user, request.FILES.get('foto'))
    except ErroFacial as exc:
        return _erro(exc)
    return _resposta_registro_facial(resultado)


@login_required
@require_POST
def abrir_terminal(request):
    if not _gestor(request.user):
        return HttpResponseForbidden('Somente gestores podem abrir o terminal.')
    gestor_id = request.user.pk
    # A sessão do gestor termina: o computador compartilhado só pode bater ponto.
    logout(request)
    request.session['terminal_gestor_id'] = gestor_id
    request.session.set_expiry(TERMINAL_SESSAO_SEGUNDOS)
    return redirect('terminal_facial')


@require_http_methods(['GET', 'POST'])
def terminal_facial(request):
    gestor_id = request.session.get('terminal_gestor_id')
    gestor = User.objects.filter(pk=gestor_id, is_active=True).first() if gestor_id else None
    if not gestor or not _gestor(gestor):
        if request.GET.get('manter') == '1':
            return JsonResponse({'ativo': False}, status=401)
        return redirect('login')
    request.session.set_expiry(TERMINAL_SESSAO_SEGUNDOS)
    if request.method == 'GET' and request.GET.get('manter') == '1':
        return JsonResponse({'ativo': True})
    if request.method == 'POST':
        if request.POST.get('acao') == 'encerrar':
            request.session.flush()
            return redirect('login')
        try:
            _limitar_captura(request)
            resultado = registrar_ponto_facial(
                gestor, request.FILES.get('foto'), compartilhado=True,
                presenca_anterior=_presenca_facial(request.session),
            )
            return _resposta_registro_facial(resultado, terminal=request.session)
        except SemRosto as exc:
            request.session.pop('facial_pessoa_presente', None)
            request.session.pop('facial_resultado_presente', None)
            return _erro(exc)
        except ErroFacial as exc:
            return _erro(exc)
    return render(request, 'ponto/camera.html', {
        'modo': 'terminal', 'confirmacao_ms': CONFIRMACAO_PONTO_MS,
        'inatividade_ms': TERMINAL_INATIVIDADE_MS, 'manutencao_ms': TERMINAL_MANUTENCAO_MS,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def meu_perfil(request):
    form = FotoPerfilForm()
    if request.method == 'POST':
        if request.POST.get('acao') == 'remover':
            salvar_foto_perfil(request.user, remover=True)
            messages.success(request, 'Foto de perfil removida.')
            return redirect('meu_perfil')
        form = FotoPerfilForm(request.POST, request.FILES)
        if form.is_valid():
            salvar_foto_perfil(request.user, form.cleaned_data['foto'])
            messages.success(request, 'Foto de perfil atualizada.')
            return redirect('meu_perfil')
    return render(request, 'ponto/meu_perfil.html', {'form': form})


@require_http_methods(['GET'])
def foto_perfil(request, usuario_id):
    visualizador = request.user
    if not visualizador.is_authenticated:
        anterior = request.session.get('facial_resultado_presente', {})
        if request.session.get('facial_pessoa_presente') != usuario_id or anterior.get('status') != 200:
            raise Http404
        visualizador = User.objects.filter(pk=request.session.get('terminal_gestor_id'), is_active=True).first()
        if not visualizador or not _gestor(visualizador):
            raise Http404
    foto = obter_foto_perfil(visualizador, usuario_id)
    if not foto:
        raise Http404
    try:
        arquivo = foto.open('rb')
    except OSError as exc:
        raise Http404 from exc
    resposta = FileResponse(arquivo)
    resposta['Cache-Control'] = 'private, no-store'
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


def gestor_required(view):
    @login_required
    @wraps(view)
    def protegida(request, *args, **kwargs):
        if request.user.perfil.papel == Perfil.PAPEL_FUNCIONARIO:
            messages.error(request, 'Somente gestores podem acessar esta página.')
            return redirect('painel')
        return view(request, *args, **kwargs)

    return protegida


def administrador_required(view):
    @login_required
    @wraps(view)
    def protegida(request, *args, **kwargs):
        if request.user.perfil.papel != Perfil.PAPEL_ADMIN:
            return HttpResponseForbidden('Somente administradores podem acessar esta página.')
        return view(request, *args, **kwargs)

    return protegida


@administrador_required
@require_http_methods(['GET'])
def usuarios(request):
    busca = request.GET.get('q', '').strip()
    pessoas = User.objects.select_related('perfil__funcao', 'perfil__gestor__user').order_by('first_name', 'username')
    if busca:
        pessoas = pessoas.filter(
            Q(first_name__icontains=busca)
            | Q(last_name__icontains=busca)
            | Q(username__icontains=busca)
            | Q(email__icontains=busca),
        )
    pagina = Paginator(pessoas, USUARIOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'ponto/usuarios.html', {'usuarios': pagina, 'busca': busca})


@administrador_required
@require_http_methods(['GET', 'POST'])
def usuario_formulario(request, usuario_id=None):
    pessoa = get_object_or_404(User, pk=usuario_id) if usuario_id else None
    form = UsuarioAdministracaoForm(request.POST or None, instance=pessoa, administrador=request.user)
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        if usuario.pk == request.user.pk and form.cleaned_data.get('senha'):
            update_session_auth_hash(request, usuario)
        messages.success(request, 'Usuário atualizado.' if pessoa else 'Usuário cadastrado.')
        return redirect('usuarios')
    return render(request, 'ponto/usuario_formulario.html', {
        'form': form, 'pessoa': pessoa, 'vinculos': pessoa.perfil.jornadas.all() if pessoa else [],
    })


def _email_do_ambiente():
    seguranca = 'ssl' if getattr(settings, 'EMAIL_USE_SSL', False) else 'tls' if settings.EMAIL_USE_TLS else 'nenhuma'
    return ConfiguracaoEmail(
        servidor=settings.EMAIL_HOST,
        porta=settings.EMAIL_PORT,
        usuario=settings.EMAIL_HOST_USER,
        seguranca=seguranca,
        remetente=settings.DEFAULT_FROM_EMAIL,
    )


@administrador_required
@require_http_methods(['GET', 'POST'])
def configurar_email(request):
    configuracao = ConfiguracaoEmail.objects.filter(pk=1).first()
    form = ConfiguracaoEmailForm(instance=configuracao or _email_do_ambiente())
    teste = TesteEmailForm(initial={'destinatario': request.user.email})
    if request.method == 'POST':
        if request.POST.get('acao') == 'testar':
            teste = TesteEmailForm(request.POST)
            if teste.is_valid():
                try:
                    with BackendEmail() as conexao:
                        quantidade = EmailMessage(
                            'Teste de envio — Registro de Ponto',
                            'Este é um teste de envio de e-mails do Registro de Ponto.',
                            conexao.remetente,
                            [teste.cleaned_data['destinatario']],
                            connection=conexao,
                        ).send()
                    if quantidade != 1:
                        raise SMTPException('Envio não aceito pelo servidor.')
                except (SMTPException, OSError, ImproperlyConfigured):
                    messages.error(request, 'O teste falhou. Confira servidor, porta, segurança, usuário e senha SMTP.')
                else:
                    messages.success(
                        request, 'O servidor aceitou o e-mail de teste. Confira a caixa de entrada e spam.'
                    )
                return redirect('configurar_email')
        else:
            form = ConfiguracaoEmailForm(request.POST, instance=configuracao or _email_do_ambiente())
            if form.is_valid():
                form.save(administrador=request.user)
                messages.success(request, 'Configuração de envio de e-mails salva.')
                return redirect('configurar_email')
    return render(
        request,
        'ponto/configurar_email.html',
        {
            'form': form,
            'teste': teste,
            'configuracao_salva': configuracao is not None,
            'tem_senha': bool(configuracao.senha_criptografada if configuracao else settings.EMAIL_HOST_PASSWORD),
        },
    )


@administrador_required
@require_http_methods(['GET'])
def jornadas(request):
    return render(request, 'ponto/jornadas.html', {'jornadas': jornadas_para_listagem()})


@administrador_required
@require_http_methods(['GET', 'POST'])
def jornada_formulario(request, jornada_id=None):
    jornada = get_object_or_404(Jornada, pk=jornada_id) if jornada_id else None
    if not jornada and request.GET.get('copiar'):
        original = get_object_or_404(Jornada, pk=request.GET['copiar'])
        jornada = Jornada(nome=f'Cópia de {original.nome}', semana=original.semana)
    dados = request.POST if request.method == 'POST' else None
    form = JornadaForm(dados, instance=jornada)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Jornada salva. Vincule no cadastro do colaborador para aplicar os horários.')
        return redirect('jornadas')
    return render(request, 'ponto/jornada_formulario.html', {'form': form, 'jornada': jornada})


@administrador_required
@require_http_methods(['GET', 'POST'])
def feriados(request):
    dados = request.POST if request.method == 'POST' else request.GET or {'ano': timezone.localdate().year}
    form = AnoFeriadosForm(dados)
    ano = timezone.localdate().year
    if form.is_valid():
        ano = form.cleaned_data['ano']
        if request.method == 'POST':
            criados = sincronizar_feriados_nacionais(ano)
            messages.success(
                request,
                f'Calendário de {ano} sincronizado: {criados} novos feriados. Cadastros existentes preservados.'
            )
            return redirect(f"{reverse('feriados')}?ano={ano}")
    return render(request, 'ponto/feriados.html', {
        'form': form, 'ano': ano, 'feriados': Feriado.objects.filter(data__year=ano),
    })


@administrador_required
@require_http_methods(['GET', 'POST'])
def feriado_formulario(request, feriado_id=None):
    feriado = get_object_or_404(Feriado, pk=feriado_id) if feriado_id else None
    form = FeriadoForm(request.POST if request.method == 'POST' else None, instance=feriado)
    if request.method == 'POST' and form.is_valid():
        item = form.save()
        messages.success(request, 'Feriado salvo.')
        return redirect(f"{reverse('feriados')}?ano={item.data.year}")
    return render(request, 'ponto/feriado_formulario.html', {'form': form})


@administrador_required
@require_http_methods(['GET', 'POST'])
def importar_planilha(request):
    form = ImportarPlanilhaForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            resultado = importar_planilha_ponto(form.cleaned_data['planilha'], request.user)
        except ErroImportacao as exc:
            form.add_error('planilha', str(exc))
        else:
            nome = resultado['pessoa'].get_full_name() or resultado['pessoa'].username
            texto = f'Planilha de {nome} importada: {resultado["batidas"]} batidas e {resultado["folgas"]} folgas.'
            if resultado['batidas_substituidas'] or resultado['folgas_substituidas']:
                texto += (
                    f' Substituídas: {resultado["batidas_substituidas"]} batidas e '
                    f'{resultado["folgas_substituidas"]} folgas que já estavam no sistema.'
                )
            messages.success(request, texto)
            for aviso in resultado['avisos']:
                messages.warning(request, aviso)
            return redirect('importar_planilha')
    return render(request, 'ponto/importar_planilha.html', {'form': form})


@gestor_required
@require_http_methods(['GET'])
def folgas(request):
    lista = Folga.objects.filter(
        funcionario__in=funcionarios_visiveis(request.user), ativa=True
    ).select_related('funcionario', 'lancada_por')
    pagina = Paginator(lista, USUARIOS_POR_PAGINA).get_page(request.GET.get('pagina'))
    return render(request, 'ponto/folgas.html', {'pagina': pagina})


@gestor_required
@require_http_methods(['GET', 'POST'])
def folga_lancar(request):
    funcionarios = funcionarios_visiveis(request.user).order_by('first_name', 'last_name')
    dados = request.POST if request.method == 'POST' else request.GET

    if request.GET.get('parcial'):
        return render(request, 'ponto/_efeito_folga.html', efeito_da_folga(funcionarios, request.GET))

    if request.method == 'POST':
        form = FolgaForm(request.POST, funcionarios=funcionarios)
        if form.is_valid():
            criadas = lancar_folgas(
                form.cleaned_data['funcionarios'],
                form.cleaned_data['data'],
                form.cleaned_data['tipo'],
                form.cleaned_data['motivo'],
                request.user,
            )
            quantidade = len(criadas)
            messages.success(
                request,
                f'Folga lançada para {quantidade} colaborador{"es" if quantidade > 1 else ""} '
                f'em {form.cleaned_data["data"]:%d/%m/%Y}.',
            )
            return redirect('folgas')
    else:
        form = FolgaForm(funcionarios=funcionarios, initial={'data': timezone.localdate()})

    saldos = saldos_do_banco(funcionarios)
    opcoes = [(opcao, saldos.get(opcao.data['value'].value)) for opcao in form['funcionarios']]
    contexto = {'form': form, 'opcoes': opcoes}
    contexto.update(efeito_da_folga(funcionarios, dados))
    return render(request, 'ponto/folga_lancar.html', contexto)


@gestor_required
@require_POST
def folga_cancelar(request, folga_id):
    folga = get_object_or_404(
        Folga, pk=folga_id, ativa=True, funcionario__in=funcionarios_visiveis(request.user)
    )
    cancelar_folga(folga, request.user)
    messages.success(
        request, f'Folga de {folga.funcionario.get_full_name()} em {folga.data:%d/%m/%Y} cancelada.'
    )
    return redirect('folgas')
