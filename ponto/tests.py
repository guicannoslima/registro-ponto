from datetime import date, datetime, time, timedelta
from io import BytesIO
from smtplib import SMTPException
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .email import BackendEmail, cifrar_senha, decifrar_senha
from .exceptions import CadastroFacialAusente, ErroFacial, FacialIndisponivel, SemRosto
from .facial import extrair_vetor, identificar
from .models import (
    CadastroFacial,
    ConfiguracaoEmail,
    Funcao,
    HistoricoAlteracaoPonto,
    Perfil,
    RegistroPonto,
    SolicitacaoAjustePonto,
)
from .relatorios import montar_relatorio
from .services import (
    linha_do_dia,
    preparar_cartao_ponto,
    registrar_ponto_facial,
    situacao,
)
from .utils import formatar_saldo, hhmm

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
        self.assertEqual(user.perfil.get_papel_display(), 'Colaborador')

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

    def test_voltar_ao_topo_so_nas_telas_internas(self):
        self.client.force_login(self.funcionario)
        interna = self.client.get(reverse('painel'))
        self.client.logout()
        login = self.client.get(reverse('login'))

        self.assertContains(interna, 'id="voltar-topo"')
        self.assertContains(interna, 'aria-label="Voltar ao topo"')
        self.assertNotContains(login, 'voltar-topo')

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


@override_settings(STORAGES=STORAGES_DE_TESTE)
class CartaoPontoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('marina', password='senha-forte-123', first_name='Marina')
        self.segunda, self.terca = date(2026, 11, 16), date(2026, 11, 17)
        for tipo, hora in zip(RegistroPonto.ORDEM_TIPOS, (8, 12, 13, 15, 15, 18), strict=True):
            _batida(self.usuario, tipo, _momento(self.segunda, hora, 45 if tipo == RegistroPonto.VOLTA_CAFE else 0))
        _batida(
            self.usuario,
            RegistroPonto.ENTRADA,
            _momento(self.segunda + timedelta(days=3), 8),
            registrado_manualmente=True,
        )

    def _cartao(self):
        item = montar_relatorio(None, self.usuario, self.segunda, self.segunda + timedelta(days=3), False)[0]
        return preparar_cartao_ponto(item, self.segunda, self.segunda + timedelta(days=3))

    def test_hhmm(self):
        self.assertEqual(hhmm(timedelta(hours=7, minutes=45)), '07:45')
        self.assertEqual(hhmm(timedelta(hours=115, minutes=5)), '115:05')
        self.assertEqual(hhmm(None), '')

    def test_dia_util_sem_batidas_conta_jornada_como_falta(self):
        linha_terca = self._cartao()['cartao']['linhas'][1]

        self.assertEqual(linha_terca['faltas'], '07:45')
        self.assertEqual(linha_terca['observacao'], 'Falta')

    def test_dia_util_futuro_nao_conta_como_falta(self):
        futuro = timezone.localdate() + timedelta(days=30)  # longe das batidas criadas no setUp
        while futuro.weekday() >= 5:
            futuro += timedelta(days=1)
        item = montar_relatorio(None, self.usuario, futuro, futuro, False)[0]

        linha = preparar_cartao_ponto(item, futuro, futuro)['cartao']['linhas'][0]

        self.assertEqual((linha['faltas'], linha['carga'], linha['observacao']), ('', '', ''))

    def test_batida_manual_recebe_asterisco_e_dia_sem_saida_fica_incompleto(self):
        linha_quinta = self._cartao()['cartao']['linhas'][3]

        self.assertTrue(linha_quinta['batidas'][0]['manual'])
        self.assertEqual(linha_quinta['observacao'], 'Incompleto')

    def test_totais_de_normais_e_extras_batem_com_o_relatorio_da_tela(self):
        item = self._cartao()

        self.assertEqual(item['cartao']['totais']['normais'], hhmm(item['horas_normais']))
        self.assertEqual(item['cartao']['totais']['extras'], hhmm(item['horas_extras']))

    def test_exportar_gera_pdf_do_cartao(self):
        self.client.force_login(self.usuario)

        resposta = self.client.post(
            reverse('exportar_relatorio_pdf'),
            {'funcionario': self.usuario.id, 'data_inicio': '2026-11-16', 'data_fim': '2026-11-19'},
        )

        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertIn('cartao-ponto-20261116-20261119.pdf', resposta['Content-Disposition'])
        self.assertTrue(resposta.content.startswith(b'%PDF'))

    def test_gerar_relatorio_exibe_o_pdf_num_iframe(self):
        self.client.force_login(self.usuario)

        resposta = self.client.post(
            reverse('relatorio_ponto'),
            {'funcionario': self.usuario.id, 'data_inicio': '2026-11-16', 'data_fim': '2026-11-19'},
        )

        filtro = f'data_inicio=2026-11-16&data_fim=2026-11-19&funcionario={self.usuario.id}'
        url = f'{reverse("visualizar_relatorio_pdf")}?{filtro}'
        self.assertEqual(resposta.context['pdf_url'], url)
        self.assertContains(resposta, '<iframe class="visor-pdf"')

    def test_visualizar_entrega_pdf_inline_liberado_para_iframe_da_mesma_origem(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse('visualizar_relatorio_pdf'),
            {'funcionario': self.usuario.id, 'data_inicio': '2026-11-16', 'data_fim': '2026-11-19'},
        )

        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertTrue(resposta['Content-Disposition'].startswith('inline;'))
        self.assertEqual(resposta['X-Frame-Options'], 'SAMEORIGIN')

    def test_funcionario_nao_visualiza_o_cartao_de_outra_pessoa(self):
        outra = User.objects.create_user('rafael', password='senha-forte-123', first_name='Rafael')
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse('visualizar_relatorio_pdf'),
            {'funcionario': outra.id, 'data_inicio': '2026-11-16', 'data_fim': '2026-11-19'},
        )

        self.assertEqual(resposta.status_code, 400)


def foto():
    buffer = BytesIO()
    Image.new('RGB', (640, 480)).save(buffer, 'JPEG')
    return SimpleUploadedFile('camera.jpg', buffer.getvalue(), content_type='image/jpeg')


@override_settings(STORAGES=STORAGES_DE_TESTE)
class FluxosFaciaisTests(TestCase):
    def setUp(self):
        self.gestor = User.objects.create_user('gestor')
        self.gestor.perfil.papel = Perfil.PAPEL_GESTOR
        self.gestor.perfil.save()
        self.pessoa = User.objects.create_user('pessoa', first_name='Maria')
        self.pessoa.perfil.gestor = self.gestor.perfil
        self.pessoa.perfil.save()
        self.fora = User.objects.create_user('outra-equipe')
        self.cadastro = CadastroFacial.objects.create(funcionario=self.pessoa, vetor=[1., 0.])
        CadastroFacial.objects.create(funcionario=self.fora, vetor=[0., 1.])

    def test_telas_renderizam(self):
        self.client.force_login(self.gestor)
        for rota in ('painel', 'ponto_facial', 'cadastro_facial'):
            self.assertEqual(self.client.get(reverse(rota)).status_code, 200)
        resposta = self.client.get(reverse('cadastro_facial'))
        self.assertNotContains(resposta, 'outra-equipe')

    def test_consulta_distingue_cadastrado_de_sem_cadastro_sem_expor_biometria(self):
        self.client.force_login(self.gestor)
        rota = reverse('cadastro_facial')

        resposta = self.client.get(rota, {'estado': '1', 'funcionario': self.pessoa.pk})
        self.assertEqual(resposta.json(), {'funcionario_id': self.pessoa.pk, 'cadastrado': True})
        resposta = self.client.get(rota, {'estado': '1', 'funcionario': self.gestor.pk})
        self.assertEqual(resposta.json(), {'funcionario_id': self.gestor.pk, 'cadastrado': False})

    def test_consulta_de_cadastro_respeita_papel_e_equipe(self):
        self.client.force_login(self.gestor)
        dados = {'estado': '1', 'funcionario': self.fora.pk}
        self.assertEqual(self.client.get(reverse('cadastro_facial'), dados).status_code, 404)
        self.client.force_login(self.pessoa)
        self.assertEqual(self.client.get(reverse('cadastro_facial'), dados).status_code, 403)

    def test_lista_de_pessoas_informa_quem_tem_cadastro(self):
        self.client.force_login(self.gestor)
        resposta = self.client.get(reverse('cadastro_facial'))
        pessoas = {p.pk: p.rosto_cadastrado for p in resposta.context['pessoas']}
        self.assertTrue(pessoas[self.pessoa.pk])
        self.assertFalse(pessoas[self.gestor.pk])
        self.assertNotIn(self.fora.pk, pessoas)

    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_servico_registra_ponto_sem_requisicao_http(self, extrair):
        resultado = registrar_ponto_facial(self.pessoa, foto())

        self.assertTrue(resultado['registrado'])
        self.assertEqual(resultado['pessoa_id'], self.pessoa.pk)
        self.assertEqual(RegistroPonto.objects.get().funcionario, self.pessoa)

    @patch('ponto.services.extrair_vetor')
    def test_servico_sem_cadastro_falha_antes_de_processar_imagem(self, extrair):
        with self.assertRaises(CadastroFacialAusente):
            registrar_ponto_facial(self.gestor, foto())

        extrair.assert_not_called()
        self.assertFalse(RegistroPonto.objects.exists())

    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_usuario_logado_reconhece_e_registra_uma_unica_batida(self, extrair):
        self.client.force_login(self.pessoa)
        resposta = self.client.post(reverse('ponto_facial'), {'foto': foto()})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(RegistroPonto.objects.get().tipo, RegistroPonto.ENTRADA)
        self.assertFalse(RegistroPonto.objects.get().foto)
        self.client.post(reverse('bater_ponto'))
        self.assertEqual(RegistroPonto.objects.count(), 1)

    @patch('ponto.services.extrair_vetor', return_value=[0., 1.])
    def test_nao_grava_quando_rosto_e_de_outra_pessoa(self, extrair):
        self.client.force_login(self.pessoa)
        self.assertEqual(self.client.post(reverse('ponto_facial'), {'foto': foto()}).status_code, 400)
        self.assertFalse(RegistroPonto.objects.exists())

    @patch('ponto.services.extrair_vetor', side_effect=FacialIndisponivel('Modelos indisponíveis.'))
    def test_falha_do_motor_nao_grava_ponto(self, extrair):
        self.client.force_login(self.pessoa)
        self.assertEqual(self.client.post(reverse('ponto_facial'), {'foto': foto()}).status_code, 503)
        self.assertFalse(RegistroPonto.objects.exists())

    def test_sem_cadastro_nao_grava(self):
        self.client.force_login(self.gestor)
        resposta = self.client.post(reverse('ponto_facial'), {'foto': foto()})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(resposta.json()['continuar'])
        self.assertFalse(RegistroPonto.objects.exists())

    def test_funcionario_nao_cadastra_nem_abre_terminal(self):
        self.client.force_login(self.pessoa)
        self.assertEqual(self.client.get(reverse('cadastro_facial')).status_code, 403)
        self.assertEqual(self.client.post(reverse('abrir_terminal')).status_code, 403)

    @patch('ponto.services.extrair_vetor', return_value=[0.6, 0.8])
    def test_gestor_nao_cadastra_pessoa_de_outra_equipe(self, extrair):
        self.client.force_login(self.gestor)
        resposta = self.client.post(reverse('cadastro_facial'), {'funcionario': self.fora.pk, 'foto': foto()})
        self.assertEqual(resposta.status_code, 404)
        extrair.assert_not_called()

    @patch('ponto.services.extrair_vetor', return_value=[-1., 0.])
    def test_gestor_substitui_e_remove_cadastro_da_equipe(self, extrair):
        self.client.force_login(self.gestor)
        resposta = self.client.post(reverse('cadastro_facial'), {'funcionario': self.pessoa.pk, 'foto': foto()})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()['cadastrado'])
        self.assertEqual(resposta.json()['funcionario_id'], self.pessoa.pk)
        self.cadastro.refresh_from_db()
        self.assertEqual(self.cadastro.vetor, [-1., 0.])
        self.assertEqual(self.cadastro.cadastrado_por, self.gestor)
        resposta = self.client.post(reverse('cadastro_facial'), {'funcionario': self.pessoa.pk, 'acao': 'excluir'})
        self.assertFalse(resposta.json()['cadastrado'])
        self.assertEqual(resposta.json()['funcionario_id'], self.pessoa.pk)
        self.assertFalse(CadastroFacial.objects.filter(funcionario=self.pessoa).exists())
        resposta = self.client.get(reverse('cadastro_facial'), {'estado': '1', 'funcionario': self.pessoa.pk})
        self.assertFalse(resposta.json()['cadastrado'])

    @patch('ponto.services.extrair_vetor', return_value=[0., 1.])
    def test_nao_associa_o_mesmo_rosto_a_duas_contas(self, extrair):
        self.client.force_login(self.gestor)
        resposta = self.client.post(reverse('cadastro_facial'), {'funcionario': self.pessoa.pk, 'foto': foto()})
        self.assertEqual(resposta.status_code, 400)
        self.cadastro.refresh_from_db()
        self.assertEqual(self.cadastro.vetor, [1., 0.])

    def abrir(self):
        self.client.force_login(self.gestor)
        self.client.post(reverse('abrir_terminal'))

    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_terminal_identifica_sem_manter_sessao_do_gestor(self, extrair):
        self.abrir()
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get(reverse('terminal_facial')).status_code, 200)
        self.assertEqual(self.client.get(reverse('equipe')).status_code, 302)
        self.assertEqual(self.client.post(reverse('terminal_facial'), {'foto': foto()}).status_code, 200)
        self.assertEqual(RegistroPonto.objects.get().funcionario, self.pessoa)
        # O rosto reconhecido nunca vira uma sessão autenticada.
        self.assertNotIn('_auth_user_id', self.client.session)

    @patch('ponto.services.extrair_vetor', return_value=[0., 1.])
    def test_terminal_nao_reconhece_pessoas_fora_da_equipe(self, extrair):
        self.abrir()
        self.assertEqual(self.client.post(reverse('terminal_facial'), {'foto': foto()}).status_code, 400)
        self.assertFalse(RegistroPonto.objects.exists())

    def test_terminal_exige_autorizacao_e_pode_ser_encerrado(self):
        self.assertRedirects(self.client.get(reverse('terminal_facial')), reverse('login'))
        self.abrir()
        self.client.post(reverse('terminal_facial'), {'acao': 'encerrar'})
        self.assertNotIn('terminal_gestor_id', self.client.session)

    def test_terminal_perde_acesso_quando_gestor_e_desativado(self):
        self.abrir()
        self.gestor.is_active = False
        self.gestor.save()
        self.assertRedirects(self.client.get(reverse('terminal_facial')), reverse('login'))

    @patch('ponto.views._limitar_captura')
    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_terminal_nao_repete_batida_de_quem_permanece_na_camera(self, extrair, limitar):
        self.abrir()
        primeira = self.client.post(reverse('terminal_facial'), {'foto': foto()})
        with patch('ponto.services.timezone.now', return_value=timezone.now() + timedelta(minutes=11)):
            segunda = self.client.post(reverse('terminal_facial'), {'foto': foto()})
        self.assertEqual(segunda.json()['mensagem'], primeira.json()['mensagem'])
        self.assertFalse(primeira.json()['repetido'])
        self.assertTrue(segunda.json()['repetido'])
        self.assertEqual(RegistroPonto.objects.count(), 1)

    @patch('ponto.views._limitar_captura')
    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_terminal_libera_nova_batida_apos_sair_do_enquadramento(self, extrair, limitar):
        self.abrir()
        self.client.post(reverse('terminal_facial'), {'foto': foto()})
        extrair.side_effect = SemRosto('Aguardando rosto.')
        resposta = self.client.post(reverse('terminal_facial'), {'foto': foto()})
        self.assertTrue(resposta.json()['continuar'])
        self.assertNotIn('facial_pessoa_presente', self.client.session)
        extrair.side_effect = None
        with patch('ponto.services.timezone.now', return_value=timezone.now() + timedelta(minutes=11)):
            self.assertEqual(self.client.post(reverse('terminal_facial'), {'foto': foto()}).status_code, 200)
        self.assertEqual(RegistroPonto.objects.count(), 2)

    @patch('ponto.views._limitar_captura')
    @patch('ponto.services.extrair_vetor', side_effect=[[1., 0.], [0., 1.]])
    def test_terminal_registra_pessoas_diferentes_em_sequencia(self, extrair, limitar):
        outra = User.objects.create_user('colega')
        outra.perfil.gestor = self.gestor.perfil
        outra.perfil.save()
        CadastroFacial.objects.create(funcionario=outra, vetor=[0., 1.])
        self.abrir()
        self.assertEqual(self.client.post(reverse('terminal_facial'), {'foto': foto()}).status_code, 200)
        self.assertEqual(self.client.post(reverse('terminal_facial'), {'foto': foto()}).status_code, 200)
        self.assertEqual(
            set(RegistroPonto.objects.values_list('funcionario_id', flat=True)), {self.pessoa.pk, outra.pk},
        )

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.gestor)
        self.assertEqual(cliente.post(reverse('abrir_terminal')).status_code, 403)
        self.assertEqual(cliente.post(reverse('cadastro_facial')).status_code, 403)
        self.assertEqual(cliente.post(reverse('ponto_facial')).status_code, 403)
        self.assertEqual(cliente.post(reverse('terminal_facial')).status_code, 403)


class MotorFacialTests(SimpleTestCase):
    def test_rejeita_imagem_invalida_e_arquivo_ausente(self):
        for arquivo in (None, SimpleUploadedFile('foto.jpg', b'nao e imagem')):
            with self.assertRaises(ErroFacial):
                extrair_vetor(arquivo)

    def test_rejeita_arquivo_grande(self):
        with self.assertRaises(ErroFacial):
            extrair_vetor(SimpleUploadedFile('foto.jpg', b'x' * (1024 * 1024 + 1)))

    def test_rejeita_foto_com_dimensoes_excessivas(self):
        buffer = BytesIO()
        Image.new('RGB', (2000, 1000)).save(buffer, 'JPEG')
        with self.assertRaises(ErroFacial):
            extrair_vetor(SimpleUploadedFile('foto.jpg', buffer.getvalue()))

    def test_rejeita_identificacao_ambigua(self):
        cadastros = [CadastroFacial(vetor=[1., 0.]), CadastroFacial(vetor=[0.99, 0.1])]
        with self.assertRaisesMessage(ErroFacial, 'inconclusiva'):
            identificar([1., 0.], cadastros)

    def test_rejeita_rosto_desconhecido(self):
        with self.assertRaisesMessage(ErroFacial, 'não reconhecido'):
            identificar([1., 0.], [CadastroFacial(vetor=[0., 1.])])


SENHA = 'Acesso-inicial-482!'
SEGREDO = 'smtp-teste-482!'


@override_settings(STORAGES=STORAGES_DE_TESTE)
class AdministracaoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('caio', first_name='Caio', email='caio@example.com', password=SENHA)
        self.admin.perfil.papel = Perfil.PAPEL_ADMIN
        self.admin.perfil.save()
        self.gestor = User.objects.create_user('gestor')
        self.gestor.perfil.papel = Perfil.PAPEL_GESTOR
        self.gestor.perfil.save()
        self.funcionario = User.objects.create_user('funcionario', password=SENHA, email='pessoa@example.com')
        self.funcao = Funcao.objects.create(nome='Analista')
        self.client.force_login(self.admin)

    def dados_usuario(self, **alteracoes):
        dados = {
            'first_name': 'Marina',
            'last_name': 'Silva',
            'username': 'marina',
            'email': 'marina@example.com',
            'cpf': '123.456.789-09',
            'papel': Perfil.PAPEL_FUNCIONARIO,
            'gestor': self.gestor.perfil.pk,
            'funcao': self.funcao.pk,
            'senha': SENHA,
            'confirmar_senha': SENHA,
            'is_active': 'on',
        }
        dados.update(alteracoes)
        return dados

    def dados_email(self, **alteracoes):
        dados = {
            'servidor': 'smtp.example.com',
            'porta': '587',
            'usuario': 'conta@example.com',
            'senha': SEGREDO,
            'seguranca': 'tls',
            'remetente': 'ponto@example.com',
        }
        dados.update(alteracoes)
        return dados

    def test_admin_cadastra_usuario_e_perfil_com_email_e_senha(self):
        resposta = self.client.post(reverse('usuario_criar'), self.dados_usuario())
        self.assertRedirects(resposta, reverse('usuarios'))
        pessoa = User.objects.get(username='marina')
        self.assertTrue(pessoa.check_password(SENHA))
        self.assertEqual(pessoa.email, 'marina@example.com')
        self.assertEqual(pessoa.perfil.cpf, '12345678909')
        self.assertEqual(pessoa.perfil.gestor, self.gestor.perfil)
        self.assertEqual(pessoa.perfil.funcao, self.funcao)
        self.assertEqual(Perfil.objects.filter(user=pessoa).count(), 1)
        self.assertFalse(pessoa.is_staff)
        self.assertFalse(pessoa.is_superuser)

    def test_admin_edita_email_sem_trocar_senha(self):
        dados = self.dados_usuario(username='funcionario', cpf='', senha='', confirmar_senha='')
        self.client.post(reverse('usuario_editar', args=[self.funcionario.pk]), dados)
        self.funcionario.refresh_from_db()
        self.assertEqual(self.funcionario.email, 'marina@example.com')
        self.assertTrue(self.funcionario.check_password(SENHA))

    def test_pode_desativar_usuario_e_mudar_papel(self):
        dados = self.dados_usuario(
            username='funcionario',
            cpf='',
            senha='',
            confirmar_senha='',
            is_active='',
            papel=Perfil.PAPEL_GESTOR,
            gestor='',
        )
        self.client.post(reverse('usuario_editar', args=[self.funcionario.pk]), dados)
        self.funcionario.refresh_from_db()
        self.assertFalse(self.funcionario.is_active)
        self.assertEqual(self.funcionario.perfil.papel, Perfil.PAPEL_GESTOR)

    def test_nao_permite_bloquear_a_propria_conta(self):
        dados = self.dados_usuario(username='caio', cpf='', senha='', confirmar_senha='', is_active='')
        resposta = self.client.post(reverse('usuario_editar', args=[self.admin.pk]), dados)
        self.assertContains(resposta, 'Você não pode desativar sua própria conta.')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.perfil.papel, Perfil.PAPEL_ADMIN)

    def test_nao_aceita_usuario_cpf_duplicados_senha_fraca_e_email_invalido(self):
        casos = [
            self.dados_usuario(username='caio'),
            self.dados_usuario(email='invalido'),
            self.dados_usuario(senha='123', confirmar_senha='123'),
        ]
        self.funcionario.perfil.cpf = '12345678909'
        self.funcionario.perfil.save()
        casos.append(self.dados_usuario())
        for campo, dados in zip(('username', 'email', 'senha', 'cpf'), casos, strict=True):
            with self.subTest(campo=campo):
                resposta = self.client.post(reverse('usuario_criar'), dados)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn(campo, resposta.context['form'].errors)
        self.assertFalse(User.objects.filter(username='marina').exists())

    def test_funcionario_nao_pode_ser_usado_como_gestor(self):
        resposta = self.client.post(reverse('usuario_criar'), self.dados_usuario(gestor=self.funcionario.perfil.pk))
        self.assertContains(resposta, 'Faça uma escolha válida')
        self.assertFalse(User.objects.filter(username='marina').exists())

    def test_busca_por_email(self):
        resposta = self.client.get(reverse('usuarios'), {'q': 'pessoa@example.com'})
        self.assertContains(resposta, 'pessoa@example.com')
        self.assertNotContains(resposta, 'caio@example.com')

    def test_administracao_exige_papel_e_login_em_get_e_post(self):
        for usuario in (self.gestor, self.funcionario):
            self.client.force_login(usuario)
            for rota in ('usuarios', 'usuario_criar', 'configurar_email'):
                self.assertEqual(self.client.get(reverse(rota)).status_code, 403)
                self.assertEqual(self.client.post(reverse(rota), {}).status_code, 403)
            self.assertEqual(self.client.get(reverse('usuario_editar', args=[self.admin.pk])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('usuarios')).status_code, 302)

    def test_menu_mostra_administracao_so_ao_administrador(self):
        self.assertContains(self.client.get(reverse('painel')), '<summary>Administração</summary>', html=True)
        self.client.force_login(self.gestor)
        self.assertNotContains(self.client.get(reverse('painel')), '<summary>Administração</summary>', html=True)
        self.client.force_login(self.funcionario)
        resposta = self.client.get(reverse('painel'))
        self.assertNotContains(resposta, '<summary>Gestão</summary>', html=True)

    def test_formularios_exigem_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        for rota in ('usuario_criar', 'configurar_email'):
            self.assertEqual(cliente.post(reverse(rota), {}).status_code, 403)

    def test_salva_smtp_sem_expor_senha_na_tela(self):
        resposta = self.client.post(reverse('configurar_email'), self.dados_email())
        self.assertRedirects(resposta, reverse('configurar_email'))
        config = ConfiguracaoEmail.objects.get()
        self.assertEqual(decifrar_senha(config.senha_criptografada), SEGREDO)
        self.assertNotEqual(config.senha_criptografada, SEGREDO)
        self.assertEqual(config.atualizado_por, self.admin)
        self.assertNotContains(self.client.get(reverse('configurar_email')), SEGREDO)

    def test_senha_em_branco_preserva_a_atual_e_remocao_e_explicita(self):
        self.client.post(reverse('configurar_email'), self.dados_email())
        self.client.post(reverse('configurar_email'), self.dados_email(senha='', porta='465', seguranca='ssl'))
        self.assertEqual(decifrar_senha(ConfiguracaoEmail.objects.get().senha_criptografada), SEGREDO)
        self.client.post(reverse('configurar_email'), self.dados_email(senha='', limpar_senha='on'))
        self.assertEqual(ConfiguracaoEmail.objects.get().senha_criptografada, '')
        self.assertEqual(ConfiguracaoEmail.objects.count(), 1)

    def test_smtp_rejeita_porta_servidor_e_remetente_invalidos(self):
        for dados in (
            self.dados_email(porta='65536'),
            self.dados_email(servidor='https://smtp.example.com'),
            self.dados_email(remetente='invalido'),
        ):
            self.assertEqual(self.client.post(reverse('configurar_email'), dados).status_code, 200)
        self.assertFalse(ConfiguracaoEmail.objects.exists())

    @patch('ponto.views.BackendEmail')
    @patch('ponto.views.EmailMessage.send', return_value=1)
    def test_envio_de_teste_so_ocorre_por_acao_explicita(self, enviar, backend):
        backend.return_value.__enter__.return_value.remetente = 'ponto@example.com'
        self.client.post(reverse('configurar_email'), self.dados_email())
        enviar.assert_not_called()
        resposta = self.client.post(reverse('configurar_email'), {'acao': 'testar', 'destinatario': 'caio@example.com'})
        self.assertRedirects(resposta, reverse('configurar_email'))
        enviar.assert_called_once()

    @patch('ponto.views.BackendEmail', side_effect=SMTPException('Falha de autenticação'))
    def test_falha_de_envio_nao_declara_sucesso(self, backend):
        resposta = self.client.post(
            reverse('configurar_email'), {'acao': 'testar', 'destinatario': 'caio@example.com'}, follow=True
        )
        self.assertContains(resposta, 'O teste falhou.')
        self.assertNotContains(resposta, 'O servidor aceitou')

    @override_settings(EMAIL_BACKEND='ponto.email.BackendEmail')
    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_recuperacao_de_senha_usa_o_smtp_e_remetente_salvos(self, enviar):
        self.client.post(reverse('configurar_email'), self.dados_email())
        self.client.post(reverse('password_reset'), {'email': self.funcionario.email})
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[0][0].from_email, 'ponto@example.com')

    @override_settings(EMAIL_HOST='ambiente.example.com', EMAIL_PORT=2525, EMAIL_HOST_PASSWORD=SEGREDO)
    def test_backend_usa_ambiente_ate_salvar_configuracao(self):
        backend = BackendEmail()
        self.assertEqual(backend.host, 'ambiente.example.com')
        self.assertEqual(backend.port, 2525)
        self.assertEqual(backend.password, SEGREDO)
        self.client.post(reverse('configurar_email'), self.dados_email(senha=''))
        self.assertEqual(BackendEmail().password, SEGREDO)

    def test_backend_usa_host_porta_autenticacao_e_seguranca_salvos(self):
        self.client.post(reverse('configurar_email'), self.dados_email(porta='465', seguranca='ssl'))
        backend = BackendEmail()
        self.assertEqual(backend.host, 'smtp.example.com')
        self.assertEqual(backend.port, 465)
        self.assertEqual(backend.username, 'conta@example.com')
        self.assertEqual(backend.password, SEGREDO)
        self.assertTrue(backend.use_ssl)
        self.assertFalse(backend.use_tls)

    def test_troca_de_chave_exige_recadastrar_senha_smtp(self):
        cifrada = cifrar_senha(SEGREDO)
        with override_settings(SECRET_KEY=SEGREDO + '-outra-chave'):
            with self.assertRaises(ImproperlyConfigured):
                decifrar_senha(cifrada)


@override_settings(STORAGES=STORAGES_DE_TESTE)
class FotoPerfilTests(TestCase):
    def setUp(self):
        self.pasta = TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        ambiente = override_settings(MEDIA_ROOT=self.pasta.name)
        ambiente.enable()
        self.addCleanup(ambiente.disable)
        self.gestor = User.objects.create_user('gestor_foto')
        self.gestor.perfil.papel = Perfil.PAPEL_GESTOR
        self.gestor.perfil.save()
        self.pessoa = User.objects.create_user('caio_foto', first_name='Caio Henrique', last_name='Pereira')
        self.pessoa.perfil.gestor = self.gestor.perfil
        self.pessoa.perfil.save()
        self.outra = User.objects.create_user('outra_foto')
        CadastroFacial.objects.create(funcionario=self.pessoa, vetor=[1., 0.])
        self.client.force_login(self.pessoa)

    def enviar_foto(self):
        return self.client.post(reverse('meu_perfil'), {'foto': foto()})

    def test_colaborador_escolhe_foto_e_arquivo_e_normalizado(self):
        self.assertRedirects(self.enviar_foto(), reverse('meu_perfil'))
        self.pessoa.perfil.refresh_from_db()
        arquivo = self.pessoa.perfil.foto
        with arquivo.open('rb') as conteudo, Image.open(conteudo) as imagem:
            self.assertEqual(imagem.format, 'JPEG')
            self.assertEqual(imagem.size, (512, 512))
        self.assertTrue(arquivo.name.startswith('perfis/'))
        self.assertNotIn('camera', arquivo.name)
        self.assertFalse(self.outra.perfil.foto)
        self.assertTrue(CadastroFacial.objects.filter(funcionario=self.pessoa).exists())

    def test_foto_invalida_nao_e_salva(self):
        resposta = self.client.post(reverse('meu_perfil'), {'foto': SimpleUploadedFile('foto.jpg', b'invalida')})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['form'].errors)
        self.pessoa.perfil.refresh_from_db()
        self.assertFalse(self.pessoa.perfil.foto)

    def test_substituir_e_remover_apaga_arquivos_antigos(self):
        self.enviar_foto()
        self.pessoa.perfil.refresh_from_db()
        antiga = self.pessoa.perfil.foto.name
        storage = self.pessoa.perfil.foto.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.enviar_foto()
        self.assertFalse(storage.exists(antiga))
        self.pessoa.perfil.refresh_from_db()
        atual = self.pessoa.perfil.foto.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('meu_perfil'), {'acao': 'remover'})
        self.assertFalse(storage.exists(atual))
        self.pessoa.perfil.refresh_from_db()
        self.assertFalse(self.pessoa.perfil.foto)

    def test_fotos_sao_privadas_e_limitadas_a_equipe(self):
        self.enviar_foto()
        rota = reverse('foto_perfil', args=[self.pessoa.pk])
        resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Cache-Control'], 'private, no-store')
        b''.join(resposta.streaming_content)
        self.client.force_login(self.gestor)
        resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200)
        b''.join(resposta.streaming_content)
        self.client.force_login(self.outra)
        self.assertEqual(self.client.get(rota).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(rota).status_code, 404)
        self.assertEqual(self.client.get(reverse('meu_perfil')).status_code, 302)

    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_confirmacao_usa_primeiro_nome_foto_e_omite_tipo_e_horario(self, extrair):
        self.enviar_foto()
        resposta = self.client.post(reverse('ponto_facial'), {'foto': foto()})
        dados = resposta.json()
        self.assertEqual(dados['mensagem'], 'PONTO REGISTRADO - CAIO')
        self.assertEqual(dados['confirmacao']['nome'], 'Caio Henrique Pereira')
        self.assertEqual(dados['confirmacao']['foto_url'], reverse('foto_perfil', args=[self.pessoa.pk]))
        self.assertFalse(dados['repetido'])

    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_sem_foto_orienta_imagem_generica_com_nome(self, extrair):
        dados = self.client.post(reverse('ponto_facial'), {'foto': foto()}).json()
        self.assertIsNone(dados['confirmacao']['foto_url'])
        self.assertEqual(dados['confirmacao']['nome'], self.pessoa.get_full_name())

    @patch('ponto.services.extrair_vetor', return_value=[1., 0.])
    def test_terminal_so_acessa_foto_da_pessoa_confirmada(self, extrair):
        self.enviar_foto()
        self.client.force_login(self.gestor)
        self.client.post(reverse('abrir_terminal'))
        rota = reverse('foto_perfil', args=[self.pessoa.pk])
        self.assertEqual(self.client.get(rota).status_code, 404)
        self.assertEqual(self.client.post(reverse('terminal_facial'), {'foto': foto()}).status_code, 200)
        resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200)
        b''.join(resposta.streaming_content)
        self.assertEqual(self.client.get(reverse('foto_perfil', args=[self.outra.pk])).status_code, 404)
        self.gestor.is_active = False
        self.gestor.save()
        self.assertEqual(self.client.get(rota).status_code, 404)

    def test_inicio_mantem_acoes_de_gestao_apenas_no_menu(self):
        self.client.force_login(self.gestor)
        html = self.client.get(reverse('painel')).content.decode()
        principal = html.split('<main', 1)[1].split('</main>', 1)[0]
        self.assertNotIn(reverse('cadastro_facial'), principal)
        self.assertNotIn(reverse('abrir_terminal'), principal)
        self.assertIn(reverse('cadastro_facial'), html)
        self.assertIn(reverse('abrir_terminal'), html)
