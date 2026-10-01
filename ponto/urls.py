from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset.html', extra_context={'etapa': 'pedir'}), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset.html', extra_context={'etapa': 'enviado'}), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset.html', extra_context={'etapa': 'nova_senha'}), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset.html', extra_context={'etapa': 'concluido'}), name='password_reset_complete'),
    path('', views.painel, name='painel'),
    path('bater_ponto/', views.bater_ponto, name='bater_ponto'),
    path('equipe/', views.equipe, name='equipe'),
    path('ponto/criar/', views.criar_ponto_manual, name = 'criar_ponto_manual'),
    path('ponto/excluir/<int:registro_id>/', views.excluir_ponto, name = 'excluir_ponto'),
    path('ponto/solicitar/criacao/', views.solicitar_criacao, name='solicitar_criacao'),
    path('ponto/solicitar/exclusao/<int:registro_id>/', views.solicitar_exclusao, name='solicitar_exclusao'),
    path('ponto/solicitacoes_pendentes/', views.solicitacoes_pendentes, name='solicitacoes_pendentes'),
    path('ponto/rejeitar/<int:solicitacao_id>/', views.rejeitar_solicitacao, name='rejeitar_solicitacao'), 
    path('ponto/aprovar/<int:solicitacao_id>/', views.aprovar_solicitacao, name='aprovar_solicitacao'),
    path('ponto/historico/', views.historico_alteracoes, name='historico_alteracoes'),
    path('ponto/relatorios/', views.relatorio_ponto, name='relatorio_ponto'),
    path('ponto/relatorio/pdf/', views.exportar_relatorio_pdf, name='exportar_relatorio_pdf'),
    path('ponto/cadastro_usuario/', views.cadastro_usuario, name='cadastro_usuario'),
]