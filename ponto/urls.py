from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.painel, name='painel'),
    path('bater_ponto/', views.bater_ponto, name='bater_ponto'),
    path('equipe/', views.equipe, name='equipe'),
    path('ponto/criar/', views.criar_ponto_manual, name = 'criar_ponto_manual'),
    path('ponto/excluir/<int:registro_id>/', views.excluir_ponto, name = 'excluir_ponto'),
    path('ponto/solicitar/criacao/', views.solicitar_criacao, name='solicitar_criacao')
]