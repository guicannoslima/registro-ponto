from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

# As quatro etapas da redefinição de senha usam a mesma tela.
SENHA = 'registration/password_reset.html'

urlpatterns = [
    path('administracao/jornadas/', views.jornadas, name='jornadas'),
    path('administracao/jornadas/nova/', views.jornada_formulario, name='jornada_criar'),
    path('administracao/jornadas/<int:jornada_id>/', views.jornada_formulario, name='jornada_editar'),
    path('administracao/jornadas/<int:jornada_id>/excluir/', views.jornada_excluir, name='jornada_excluir'),
    path('administracao/funcoes/', views.funcoes, name='funcoes'),
    path('administracao/funcoes/nova/', views.funcao_formulario, name='funcao_criar'),
    path('administracao/funcoes/<int:funcao_id>/', views.funcao_formulario, name='funcao_editar'),
    path('administracao/feriados/', views.feriados, name='feriados'),
    path('administracao/feriados/novo/', views.feriado_formulario, name='feriado_criar'),
    path('administracao/feriados/<int:feriado_id>/', views.feriado_formulario, name='feriado_editar'),
    path('perfil/', views.meu_perfil, name='meu_perfil'),
    path('perfil/foto/<int:usuario_id>/', views.foto_perfil, name='foto_perfil'),
    path('administracao/usuarios/', views.usuarios, name='usuarios'),
    path('administracao/usuarios/novo/', views.usuario_formulario, name='usuario_criar'),
    path('administracao/usuarios/<int:usuario_id>/', views.usuario_formulario, name='usuario_editar'),
    path('administracao/email/', views.configurar_email, name='configurar_email'),
    path('administracao/importar-planilha/', views.importar_planilha, name='importar_planilha'),
    path('ponto/camera/', views.ponto_facial, name='ponto_facial'),
    path('ponto/camera/cadastro/', views.cadastro_facial, name='cadastro_facial'),
    path('ponto/camera/abrir-terminal/', views.abrir_terminal, name='abrir_terminal'),
    path('terminal/', views.terminal_facial, name='terminal_facial'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(template_name=SENHA, extra_context={'etapa': 'pedir'}),
        name='password_reset',
    ),
    path(
        'password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name=SENHA, extra_context={'etapa': 'enviado'}),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(template_name=SENHA, extra_context={'etapa': 'nova_senha'}),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(template_name=SENHA, extra_context={'etapa': 'concluido'}),
        name='password_reset_complete',
    ),
    path('', views.painel, name='painel'),
    path('bater_ponto/', views.bater_ponto, name='bater_ponto'),
    path('ponto/lembretes/', views.lembretes_ponto_pendentes, name='lembretes_ponto'),
    path('equipe/', views.equipe, name='equipe'),
    path('ponto/criar/', views.criar_ponto_manual, name = 'criar_ponto_manual'),
    path('folgas/', views.folgas, name='folgas'),
    path('folgas/lancar/', views.folga_lancar, name='folga_lancar'),
    path('folgas/<int:folga_id>/cancelar/', views.folga_cancelar, name='folga_cancelar'),
    path('ponto/excluir/<int:registro_id>/', views.excluir_ponto, name = 'excluir_ponto'),
    path('ponto/solicitar/criacao/', views.solicitar_criacao, name='solicitar_criacao'),
    path('ponto/solicitar/exclusao/<int:registro_id>/', views.solicitar_exclusao, name='solicitar_exclusao'),
    path('ponto/solicitacoes_pendentes/', views.solicitacoes_pendentes, name='solicitacoes_pendentes'),
    path('ponto/rejeitar/<int:solicitacao_id>/', views.rejeitar_solicitacao, name='rejeitar_solicitacao'), 
    path('ponto/aprovar/<int:solicitacao_id>/', views.aprovar_solicitacao, name='aprovar_solicitacao'),
    path('ponto/historico/', views.historico_alteracoes, name='historico_alteracoes'),
    path('ponto/relatorios/', views.relatorio_ponto, name='relatorio_ponto'),
    path('ponto/banco-de-horas/', views.banco_de_horas, name='banco_de_horas'),
    path('ponto/relatorio/pdf/', views.exportar_relatorio_pdf, name='exportar_relatorio_pdf'),
    path('ponto/relatorio/pdf/visualizar/', views.visualizar_relatorio_pdf, name='visualizar_relatorio_pdf'),
    path('ponto/cadastro_usuario/', views.cadastro_usuario, name='cadastro_usuario'),
]
