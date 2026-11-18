from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .apresentacao import formatar_saldo, linha_do_dia, preparar_relatorio, situacao
from .models import Funcao, HistoricoAlteracaoPonto, Perfil, RegistroPonto, SolicitacaoAjustePonto
from .relatorios import montar_relatorio

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


def _batida(usuario, tipo, quando, **extra):
    return RegistroPonto.objects.create(funcionario=usuario, tipo=tipo, data_hora=quando, **extra)


def _momento(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class ApresentacaoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('bruno', password='senha-forte-123', first_name='Bruno')
        self.hoje = timezone.localdate()

    def test_linha_do_dia_marca_a_proxima_batida(self):
        registros = [
            _batida(self.usuario, RegistroPonto.ENTRADA, _momento(self.hoje, 8)),
            _batida(self.usuario, RegistroPonto.SAIDA_ALMOCO, _momento(self.hoje, 12)),
        ]

        linha = linha_do_dia(registros)

        self.assertEqual([p['tipo'] for p in linha], RegistroPonto.ORDEM_TIPOS)
        self.assertEqual([p['proxima'] for p in linha], [False, False, True, False, False, False])
        self.assertIsNotNone(linha[1]['registro'])

    def test_linha_de_um_dia_passado_nao_marca_proxima(self):
        registros = [_batida(self.usuario, RegistroPonto.ENTRADA, _momento(self.hoje, 8))]

        linha = linha_do_dia(registros, marcar_proxima=False)

        self.assertFalse(any(p['proxima'] for p in linha))

    def test_situacao_segue_a_ultima_batida(self):
        self.assertEqual(situacao([]), ('Sem entrada', 'neutro'))
        entrada = _batida(self.usuario, RegistroPonto.ENTRADA, _momento(self.hoje, 8))
        self.assertEqual(situacao([entrada]), ('Em jornada', 'info'))
        almoco = _batida(self.usuario, RegistroPonto.SAIDA_ALMOCO, _momento(self.hoje, 12))
        self.assertEqual(situacao([entrada, almoco]), ('No almoço', 'atencao'))
        saida = _batida(self.usuario, RegistroPonto.SAIDA, _momento(self.hoje, 17))
        self.assertEqual(situacao([entrada, almoco, saida]), ('Jornada encerrada', 'sucesso'))

    def test_formatar_saldo_com_sinal(self):
        self.assertEqual(formatar_saldo(timedelta()), '0min')
        self.assertEqual(formatar_saldo(timedelta(minutes=50)), '+0h50min')
        self.assertEqual(formatar_saldo(-timedelta(hours=1, minutes=5)), '−1h05min')

    def test_relatorio_omite_fim_de_semana_sem_batidas(self):
        sabado = date(2026, 11, 14)
        relatorio = preparar_relatorio(montar_relatorio(None, self.usuario, sabado, sabado + timedelta(days=2), False))

        dias = relatorio[0]['dias']
        self.assertEqual([d['data'] for d in dias], [sabado + timedelta(days=2)])
        self.assertEqual(relatorio[0]['dias_incompletos'], 1)


@override_settings(STORAGES=STORAGES_DE_TESTE)
class TelasInternasTests(TestCase):
    def setUp(self):
        self.gestor = User.objects.create_user('ana', password='senha-forte-123', first_name='Ana', last_name='Ribeiro')
        self.gestor.perfil.papel = Perfil.PAPEL_GESTOR
        self.gestor.perfil.save()
        self.funcionario = User.objects.create_user(
            'diego', password='senha-forte-123', first_name='Diego', last_name='Santos'
        )
        self.funcionario.perfil.gestor = self.gestor.perfil
        self.funcionario.perfil.save()
        self.hoje = timezone.localdate()

    def test_painel_do_funcionario_nomeia_a_proxima_batida(self):
        self.client.force_login(self.funcionario)
        _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(self.hoje, 8))

        resposta = self.client.get(reverse('painel'))

        self.assertContains(resposta, 'Registrar saída para o almoço')

    def test_painel_do_gestor_avisa_solicitacoes_pendentes(self):
        SolicitacaoAjustePonto.objects.create(
            funcionario=self.funcionario,
            tipo_acao=SolicitacaoAjustePonto.CRIACAO,
            tipo=RegistroPonto.SAIDA,
            data_hora=_momento(self.hoje, 17),
            motivo_funcionario='Esqueci a saída.',
        )
        self.client.force_login(self.gestor)

        resposta = self.client.get(reverse('painel'))

        self.assertContains(resposta, '1 solicitação de ajuste aguarda sua revisão')
        self.assertContains(resposta, 'id="aba-equipe"')
        self.assertContains(resposta, 'Diego Santos')

    def test_painel_abre_na_aba_hoje_e_aceita_aba_pela_url(self):
        self.client.force_login(self.funcionario)

        padrao = self.client.get(reverse('painel'))
        ontem = self.client.get(reverse('painel'), {'aba': 'ontem'})

        self.assertEqual(padrao.context['aba_ativa'], 'hoje')
        self.assertEqual(ontem.context['aba_ativa'], 'ontem')
        self.assertContains(ontem, 'id="painel-hoje" aria-labelledby="aba-hoje" hidden')

    def test_aba_sua_equipe_so_aparece_para_gestor(self):
        self.client.force_login(self.funcionario)

        resposta = self.client.get(reverse('painel'), {'aba': 'equipe'})

        self.assertEqual(resposta.context['abas'], ('hoje', 'ontem'))
        self.assertEqual(resposta.context['aba_ativa'], 'hoje')
        self.assertNotContains(resposta, 'id="aba-equipe"')

    def test_equipe_lista_situacao_e_link_de_exclusao(self):
        entrada = _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(self.hoje, 8, 14))
        self.client.force_login(self.gestor)

        resposta = self.client.get(reverse('equipe'))

        self.assertContains(resposta, 'Em jornada')
        self.assertContains(resposta, reverse('excluir_ponto', args=[entrada.id]))

    def test_lancamento_manual_mostra_batidas_ja_registradas_no_dia(self):
        _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(self.hoje, 8, 9))
        self.client.force_login(self.gestor)

        resposta = self.client.get(
            reverse('criar_ponto_manual'),
            {'parcial': '1', 'funcionario': self.funcionario.id, 'data': self.hoje.isoformat()},
        )

        self.assertContains(resposta, f'Diego em {self.hoje:%d/%m/%Y}')
        self.assertContains(resposta, '08:09')

    def test_excluir_batida_volta_para_a_equipe(self):
        entrada = _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(self.hoje, 8))
        self.client.force_login(self.gestor)

        resposta = self.client.post(reverse('excluir_ponto', args=[entrada.id]), {'motivo': 'Batida duplicada.'})

        self.assertRedirects(resposta, reverse('equipe'))
        entrada.refresh_from_db()
        self.assertFalse(entrada.ativo)

    def test_rejeitar_sem_motivo_mostra_o_erro(self):
        solicitacao = SolicitacaoAjustePonto.objects.create(
            funcionario=self.funcionario,
            tipo_acao=SolicitacaoAjustePonto.CRIACAO,
            tipo=RegistroPonto.SAIDA,
            data_hora=_momento(self.hoje, 17),
            motivo_funcionario='Esqueci a saída.',
        )
        self.client.force_login(self.gestor)

        resposta = self.client.post(reverse('rejeitar_solicitacao', args=[solicitacao.id]), {'motivo_rejeicao': ''})

        self.assertContains(resposta, 'Informe o motivo da rejeição para continuar.')

    def test_historico_filtra_por_acao(self):
        entrada = _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(self.hoje, 8))
        HistoricoAlteracaoPonto.objects.create(
            registro=entrada,
            tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO,
            realizado_por=self.gestor,
            motivo='Batida duplicada.',
        )
        self.client.force_login(self.gestor)

        com_exclusao = self.client.get(reverse('historico_alteracoes'), {'acao': 'exclusao'})
        so_inclusoes = self.client.get(reverse('historico_alteracoes'), {'acao': 'criacao_manual'})

        self.assertContains(com_exclusao, 'Batida duplicada.')
        self.assertContains(so_inclusoes, 'Nenhuma alteração com esses filtros.')

    def test_relatorio_mostra_nome_completo_no_select(self):
        self.client.force_login(self.gestor)

        resposta = self.client.get(reverse('relatorio_ponto'))

        self.assertContains(resposta, '>Diego Santos</option>')
