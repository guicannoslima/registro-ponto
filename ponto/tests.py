from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Funcao, Perfil

# O test runner força DEBUG=False; sem collectstatic não há manifest, então os testes usam o storage simples
STORAGES_DE_TESTE = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(STORAGES=STORAGES_DE_TESTE)
class PerfilAutomaticoTests(TestCase):
    """Todo usuário precisa de um Perfil: sem ele as telas quebram com RelatedObjectDoesNotExist."""

    def test_superusuario_recebe_perfil_de_administrador(self):
        user = User.objects.create_superuser('admin', 'admin@example.com', 'senha-forte-123')

        self.assertEqual(user.perfil.papel, Perfil.PAPEL_ADMIN)

    def test_usuario_comum_recebe_perfil_de_funcionario(self):
        user = User.objects.create_user('joao', password='senha-forte-123')

        self.assertEqual(user.perfil.papel, Perfil.PAPEL_FUNCIONARIO)

    def test_superusuario_acessa_o_painel_sem_erro(self):
        user = User.objects.create_superuser('admin', 'admin@example.com', 'senha-forte-123')
        self.client.force_login(user)

        resposta = self.client.get(reverse('painel'))

        self.assertEqual(resposta.status_code, 200)

    def test_cadastro_pela_tela_preenche_o_perfil_criado_automaticamente(self):
        funcao = Funcao.objects.create(nome='Desenvolvedor')

        resposta = self.client.post(
            reverse('cadastro_usuario'),
            {
                'username': 'maria',
                'password': 'senha-forte-123',
                'password2': 'senha-forte-123',
                'first_name': 'Maria',
                'last_name': 'Silva',
                'cpf': '123.456.789-09',
                'email': 'maria@example.com',
                'funcao': funcao.pk,
            },
        )

        self.assertRedirects(resposta, reverse('login'))
        perfil = Perfil.objects.get(user__username='maria')
        self.assertEqual(perfil.papel, Perfil.PAPEL_FUNCIONARIO)
        self.assertEqual(perfil.cpf, '12345678909')
        self.assertEqual(perfil.funcao, funcao)
        self.assertEqual(Perfil.objects.filter(user__username='maria').count(), 1)
