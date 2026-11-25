from datetime import date, datetime, time, timedelta
from io import BytesIO
from smtplib import SMTPException
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
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

    def test_cadastro_lista_as_funcoes_iniciais(self):
        resposta = self.client.get(reverse('cadastro_usuario'))

        self.assertContains(resposta, 'Selecione sua função')
        funcoes = ('Auxiliar de Suporte', 'Programador Júnior', 'Supervisora Financeira', 'Coordenadora de Processos')
        for nome in funcoes:
            self.assertContains(resposta, f'>{nome}</option>')


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

    def test_lancamento_manual_permite_excluir_batidas_de_dias_anteriores(self):
        dia = self.hoje - timedelta(days=30)
        entrada = _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(dia, 8))
        repetida = _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(dia, 8, 2))
        self.client.force_login(self.gestor)

        resposta = self.client.get(
            reverse('criar_ponto_manual'), {'parcial': '1', 'funcionario': self.funcionario.id, 'data': dia.isoformat()}
        )

        self.assertContains(resposta, f"{reverse('excluir_ponto', args=[entrada.id])}?voltar=manual")
        self.assertContains(resposta, f"{reverse('excluir_ponto', args=[repetida.id])}?voltar=manual")
        self.assertContains(resposta, 'Entrada (repetida)')

    def test_exclusao_pelo_lancamento_manual_volta_para_o_mesmo_dia(self):
        dia = self.hoje - timedelta(days=30)
        entrada = _batida(self.funcionario, RegistroPonto.ENTRADA, _momento(dia, 8))
        self.client.force_login(self.gestor)
        url = f"{reverse('excluir_ponto', args=[entrada.id])}?voltar=manual"
        destino = f"{reverse('criar_ponto_manual')}?funcionario={self.funcionario.id}&data={dia.isoformat()}"

        self.assertContains(self.client.get(url), f'href="{destino.replace("&", "&amp;")}"')
        resposta = self.client.post(url, {'motivo': 'Batida duplicada.'})

        self.assertRedirects(resposta, destino)
        entrada.refresh_from_db()
        self.assertFalse(entrada.ativo)
        self.assertTrue(entrada.historico.filter(tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO).exists())
        # De volta ao lançamento, o formulário e o painel continuam no dia ajustado.
        retorno = self.client.get(destino)
        self.assertContains(retorno, f'value="{dia.isoformat()}T00:00"')
        self.assertContains(retorno, f'data-dia="{dia.isoformat()}"')

    def test_gestor_nao_exclui_batida_de_fora_da_equipe(self):
        outra = User.objects.create_user('outra_pessoa', first_name='Outra')
        batida = _batida(outra, RegistroPonto.ENTRADA, _momento(self.hoje, 8))
        self.client.force_login(self.gestor)

        resposta = self.client.post(reverse('excluir_ponto', args=[batida.id]), {'motivo': 'Tentativa.'})

        self.assertEqual(resposta.status_code, 404)
        batida.refresh_from_db()
        self.assertTrue(batida.ativo)

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

    def test_sabado_na_regra_anterior_conta_so_hora_extra(self):
        sabado = self.segunda + timedelta(days=5)
        _batida(self.usuario, RegistroPonto.ENTRADA, _momento(sabado, 8))
        _batida(self.usuario, RegistroPonto.SAIDA, _momento(sabado, 12))
        item = montar_relatorio(None, self.usuario, sabado, sabado, False)[0]

        linha = preparar_cartao_ponto(item, sabado, sabado)['cartao']['linhas'][0]

        self.assertEqual((linha['normais'], linha['faltas'], linha['extras']), ('', '', '04:00'))
        self.assertEqual(item['horas_extras'], timedelta(hours=4))

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
        self.assertTrue(resposta.json()['cadastro_necessario'])
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
        tela = self.client.get(reverse('terminal_facial'))
        self.assertEqual(tela.status_code, 200)
        self.assertNotContains(tela, 'Antes de registrar')
        self.assertContains(tela, 'Encerrar terminal', count=1)
        self.assertIn('Encerrar terminal', tela.content.decode().split('</header>', 1)[0])
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
        self.assertEqual(self.client.get(reverse('terminal_facial'), {'manter': '1'}).status_code, 401)
        self.abrir()
        self.client.post(reverse('terminal_facial'), {'acao': 'encerrar'})
        self.assertNotIn('terminal_gestor_id', self.client.session)
        self.assertEqual(self.client.get(reverse('terminal_facial'), {'manter': '1'}).status_code, 401)

    def test_terminal_renova_sessao_apos_13_horas_sem_gravar_batida(self):
        self.abrir()
        chave = self.client.session.session_key
        anterior = Session.objects.get(session_key=chave).expire_date
        futuro = timezone.now() + timedelta(hours=13)
        with patch('django.utils.timezone.now', return_value=futuro):
            resposta = self.client.get(reverse('terminal_facial'), {'manter': '1'})
        self.assertEqual(resposta.json(), {'ativo': True})
        self.assertGreater(Session.objects.get(session_key=chave).expire_date, anterior + timedelta(hours=12))
        self.assertFalse(RegistroPonto.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_terminal_perde_acesso_quando_gestor_e_desativado(self):
        self.abrir()
        self.gestor.is_active = False
        self.gestor.save()
        self.assertRedirects(self.client.get(reverse('terminal_facial')), reverse('login'))
        self.assertEqual(self.client.get(reverse('terminal_facial'), {'manter': '1'}).status_code, 401)

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

    def test_menu_restringe_cadastros_ao_administrador(self):
        self.assertContains(self.client.get(reverse('painel')), '<summary>Administração</summary>', html=True)
        self.client.force_login(self.gestor)
        resposta = self.client.get(reverse('painel'))
        self.assertContains(resposta, '<summary>Administração</summary>', html=True)
        for rota in ('usuarios', 'jornadas', 'feriados', 'configurar_email'):
            self.assertNotContains(resposta, f'href="{reverse(rota)}"')
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
            self.assertEqual(imagem.format, 'WEBP')
            self.assertEqual(imagem.size, (512, 512))
        self.assertTrue(arquivo.name.startswith('perfis/'))
        self.assertTrue(arquivo.name.endswith('.webp'))
        self.assertNotIn('camera', arquivo.name)
        self.assertFalse(self.outra.perfil.foto)
        self.assertTrue(CadastroFacial.objects.filter(funcionario=self.pessoa).exists())

    def test_foto_invalida_nao_e_salva(self):
        resposta = self.client.post(reverse('meu_perfil'), {'foto': SimpleUploadedFile('foto.jpg', b'invalida')})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['form'].errors)
        self.pessoa.perfil.refresh_from_db()
        self.assertFalse(self.pessoa.perfil.foto)

    def test_foto_acima_de_16_milhoes_de_pixels_e_reduzida_sem_rejeicao(self):
        for formato in ('JPEG', 'PNG', 'WEBP'):
            with self.subTest(formato=formato):
                buffer = BytesIO()
                with Image.new('RGB', (5000, 4000), (40, 100, 180)) as grande:
                    grande.save(buffer, formato)
                arquivo = SimpleUploadedFile(f'grande.{formato.lower()}', buffer.getvalue())
                with self.captureOnCommitCallbacks(execute=True):
                    resposta = self.client.post(reverse('meu_perfil'), {'foto': arquivo})
                self.assertRedirects(resposta, reverse('meu_perfil'))
                self.pessoa.perfil.refresh_from_db()
                with self.pessoa.perfil.foto.open('rb') as conteudo, Image.open(conteudo) as imagem:
                    self.assertEqual(imagem.format, 'WEBP')
                    self.assertEqual(imagem.size, (512, 512))

    def test_png_e_webp_sao_convertidos_para_webp_sem_metadados(self):
        for formato in ('PNG', 'WEBP'):
            with self.subTest(formato=formato):
                buffer = BytesIO()
                Image.new('RGBA', (300, 400), (40, 100, 180, 255)).save(buffer, formato)
                arquivo = SimpleUploadedFile(f'perfil.{formato.lower()}', buffer.getvalue())
                with self.captureOnCommitCallbacks(execute=True):
                    self.client.post(reverse('meu_perfil'), {'foto': arquivo})
                self.pessoa.perfil.refresh_from_db()
                with self.pessoa.perfil.foto.open('rb') as conteudo, Image.open(conteudo) as imagem:
                    self.assertEqual(imagem.format, 'WEBP')
                    self.assertEqual(imagem.size, (512, 512))
                    self.assertFalse(imagem.getexif())

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
        self.assertEqual(resposta['Content-Type'], 'image/webp')
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


@override_settings(STORAGES=STORAGES_DE_TESTE)
class RelatorioPermissoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin_relatorio', first_name='Administrador')
        cls.admin.perfil.papel = Perfil.PAPEL_ADMIN
        cls.admin.perfil.save()
        cls.gestor = User.objects.create_user('gestor_relatorio', first_name='Gestor')
        cls.gestor.perfil.papel = Perfil.PAPEL_GESTOR
        cls.gestor.perfil.save()
        cls.pessoa = User.objects.create_user('equipe_relatorio', first_name='Pessoa')
        cls.pessoa.perfil.gestor = cls.gestor.perfil
        cls.pessoa.perfil.save()
        cls.outra = User.objects.create_user('outra_relatorio', first_name='Outra')

    def dados(self, pessoa=None, **alteracoes):
        dados = {'data_inicio': '2026-11-16', 'data_fim': '2026-11-18'}
        if pessoa:
            dados['funcionario'] = pessoa.pk
        dados.update(alteracoes)
        return dados

    def test_opcoes_do_relatorio_seguem_o_papel_e_a_equipe(self):
        for usuario, permitidos in (
            (self.admin, {self.admin.pk, self.gestor.pk, self.pessoa.pk, self.outra.pk}),
            (self.gestor, {self.pessoa.pk}),
            (self.pessoa, {self.pessoa.pk}),
        ):
            with self.subTest(papel=usuario.perfil.papel):
                self.client.force_login(usuario)
                form = self.client.get(reverse('relatorio_ponto')).context['form']
                self.assertSetEqual(set(form.fields['funcionario'].queryset.values_list('pk', flat=True)), permitidos)
                self.assertEqual('gerar_todos' in form.fields, usuario != self.pessoa)

    @patch('ponto.views._cartao_ponto_pdf', return_value=HttpResponse(b'%PDF', content_type='application/pdf'))
    def test_visualizacao_e_download_permitidos_por_papel(self, gerar_pdf):
        for usuario, alvo in ((self.admin, self.outra), (self.gestor, self.pessoa), (self.pessoa, self.pessoa)):
            with self.subTest(papel=usuario.perfil.papel):
                self.client.force_login(usuario)
                pagina = self.client.post(reverse('relatorio_ponto'), self.dados(alvo))
                self.assertIn('pdf_url', pagina.context)
                for rota, metodo in (('visualizar_relatorio_pdf', 'get'), ('exportar_relatorio_pdf', 'post')):
                    resposta = getattr(self.client, metodo)(reverse(rota), self.dados(alvo))
                    self.assertEqual(resposta.status_code, 200)
                    self.assertEqual(gerar_pdf.call_args.args[1]['funcionario'], alvo)

    @patch('ponto.views._cartao_ponto_pdf')
    def test_trocar_id_nao_libera_relatorio_fora_do_escopo(self, gerar_pdf):
        for usuario in (self.gestor, self.pessoa):
            with self.subTest(papel=usuario.perfil.papel):
                self.client.force_login(usuario)
                dados = self.dados(self.outra, gerar_todos='on')
                pagina = self.client.post(reverse('relatorio_ponto'), dados)
                self.assertNotIn('pdf_url', pagina.context)
                self.assertIn('funcionario', pagina.context['form'].errors)
                self.assertEqual(self.client.get(reverse('visualizar_relatorio_pdf'), dados).status_code, 400)
                self.assertEqual(self.client.post(reverse('exportar_relatorio_pdf'), dados).status_code, 302)
        gerar_pdf.assert_not_called()

    @patch('ponto.views._cartao_ponto_pdf', return_value=HttpResponse(b'%PDF', content_type='application/pdf'))
    def test_gerar_todos_nao_amplia_as_permissoes(self, gerar_pdf):
        for usuario, permitidos in (
            (self.admin, {self.admin.pk, self.gestor.pk, self.pessoa.pk, self.outra.pk}),
            (self.gestor, {self.pessoa.pk}),
            (self.pessoa, {self.pessoa.pk}),
        ):
            with self.subTest(papel=usuario.perfil.papel):
                self.client.force_login(usuario)
                dados = self.dados(self.pessoa if usuario == self.pessoa else None, gerar_todos='on')
                for rota, metodo in (('visualizar_relatorio_pdf', 'get'), ('exportar_relatorio_pdf', 'post')):
                    self.assertEqual(getattr(self.client, metodo)(reverse(rota), dados).status_code, 200)
                    pessoas, filtro = gerar_pdf.call_args.args
                    self.assertSetEqual(set(pessoas.values_list('pk', flat=True)), permitidos)
                    self.assertEqual(bool(filtro.get('gerar_todos')), usuario != self.pessoa)


@override_settings(STORAGES=STORAGES_DE_TESTE)
class JornadasFeriadosTests(TestCase):
    def setUp(self):
        from .models import Jornada

        self.admin = User.objects.create_superuser('admin_jornada', 'admin@example.com', 'senha-forte-123')
        self.pessoa = User.objects.create_user('pessoa_jornada')
        self.jornada = Jornada.objects.get(nome='40h · Seg–sex · 08h')
        self.segunda = date(2026, 11, 16)
        self.client.force_login(self.admin)

    def vincular(self, inicio=None):
        from .services import vincular_jornada

        vincular_jornada(self.pessoa.perfil, self.jornada, inicio or self.segunda)

    def test_modelos_iniciais_e_cargas(self):
        from .services import jornadas_para_listagem

        cargas = {j.nome: j.carga_semanal for j in jornadas_para_listagem()}
        self.assertEqual(len(cargas), 8)
        for nome, carga in cargas.items():
            self.assertEqual(carga, timedelta(hours=int(nome.split('h')[0])))

    def test_telas_administracao_restritas(self):
        for nome in ('jornadas', 'jornada_criar', 'feriados', 'feriado_criar'):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200)
        self.client.force_login(self.pessoa)
        for nome in ('jornadas', 'jornada_criar', 'feriados', 'feriado_criar'):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 403)
            self.assertEqual(self.client.post(reverse(nome), {}).status_code, 403)

    def test_form_valida_ordem_intervalos_e_folgas(self):
        from .forms import JornadaForm

        dados = {'nome': 'Teste', 'ativa': 'on', 'dia_0_0': '08:00', 'dia_0_5': '17:00'}
        for alteracoes in ({'dia_0_5': '07:00'}, {'dia_0_1': '12:00'}, {'dia_0_0': ''}):
            form = JornadaForm(dados | alteracoes)
            self.assertFalse(form.is_valid())
        form = JornadaForm(dados | {'dia_0_1': '12:00', 'dia_0_2': '13:00'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().semana, {'0': ['08:00', '12:00', '13:00', '', '', '17:00']})

    def test_jornada_vigente_preserva_periodo_anterior_e_snapshot(self):
        from .services import configuracao_jornada

        self.vincular()
        sexta_anterior = self.segunda - timedelta(days=3)
        self.assertEqual(configuracao_jornada(self.pessoa, sexta_anterior)['carga'], timedelta(hours=7, minutes=45))
        self.assertEqual(configuracao_jornada(self.pessoa, self.segunda - timedelta(days=1))['carga'], timedelta())
        self.assertEqual(configuracao_jornada(self.pessoa, self.segunda)['carga'], timedelta(hours=8))
        self.jornada.semana = {'0': ['09:00', '', '', '', '', '12:00']}
        self.jornada.save()
        self.assertEqual(configuracao_jornada(self.pessoa, self.segunda)['carga'], timedelta(hours=8))
        self.assertEqual(configuracao_jornada(self.pessoa, date(2026, 11, 21))['carga'], timedelta())

    def test_batida_pula_intervalos_nao_previstos(self):
        from .services import registrar_batida

        self.vincular()
        with patch('ponto.services.timezone.now', return_value=_momento(self.segunda, 8)):
            self.assertEqual(registrar_batida(self.pessoa).tipo, RegistroPonto.ENTRADA)
        _batida(self.pessoa, RegistroPonto.SAIDA_ALMOCO, _momento(self.segunda, 12))
        _batida(self.pessoa, RegistroPonto.VOLTA_ALMOCO, _momento(self.segunda, 13))
        with patch('ponto.services.timezone.now', return_value=_momento(self.segunda, 17)):
            self.assertEqual(registrar_batida(self.pessoa).tipo, RegistroPonto.SAIDA)

    def test_calculo_e_pdf_usam_carga_individual(self):
        from .relatorios import calcular_horas_dia

        self.vincular()
        for tipo, hora in zip(
            (RegistroPonto.ENTRADA, RegistroPonto.SAIDA_ALMOCO, RegistroPonto.VOLTA_ALMOCO, RegistroPonto.SAIDA),
            (8, 12, 13, 17),
            strict=True,
        ):
            _batida(self.pessoa, tipo, _momento(self.segunda, hora))
        resultado = calcular_horas_dia(self.pessoa, self.segunda)
        self.assertEqual(resultado['diferenca'], timedelta())
        item = montar_relatorio(None, self.pessoa, self.segunda, self.segunda, False)[0]
        cartao = preparar_cartao_ponto(item, self.segunda, self.segunda)
        self.assertEqual(cartao['cartao']['totais']['carga'], '08:00')
        self.assertEqual(cartao['horario'][0]['pares'][0], ('08:00', '12:00'))

    def test_sincronizacao_idempotente_preserva_ajustes_e_nao_importa_facultativos(self):
        from .models import Feriado
        from .services import sincronizar_feriados_nacionais

        self.assertEqual(sincronizar_feriados_nacionais(2026), 9)
        item = Feriado.objects.get(data=date(2026, 11, 20))
        item.nome = 'Empresa funciona'
        item.dispensa_expediente = False
        item.save()
        self.assertEqual(sincronizar_feriados_nacionais(2026), 0)
        item.refresh_from_db()
        self.assertEqual(item.nome, 'Empresa funciona')
        self.assertFalse(item.dispensa_expediente)
        self.assertFalse(Feriado.objects.filter(data=date(2026, 2, 17)).exists())

    def test_feriado_sem_ponto_nao_gera_falta(self):
        from .models import Feriado

        self.vincular()
        Feriado.objects.create(data=self.segunda, nome='Feriado local')
        item = montar_relatorio(None, self.pessoa, self.segunda, self.segunda, False)[0]
        cartao = preparar_cartao_ponto(item, self.segunda, self.segunda)['cartao']
        self.assertEqual(cartao['totais']['faltas'], '00:00')
        self.assertEqual(cartao['linhas'][0]['observacao'], 'Feriado')

    def test_vinculo_no_cadastro_do_colaborador(self):
        dados = {
            'username': self.pessoa.username,
            'first_name': 'Pessoa',
            'last_name': 'Teste',
            'email': 'pessoa@example.com',
            'papel': Perfil.PAPEL_FUNCIONARIO,
            'jornada': self.jornada.pk,
            'jornada_inicio': '2026-11-16',
            'is_active': 'on',
        }
        resposta = self.client.post(reverse('usuario_editar', args=[self.pessoa.pk]), dados)
        self.assertRedirects(resposta, reverse('usuarios'))
        self.assertEqual(self.pessoa.perfil.jornadas.get().jornada, self.jornada)
        self.client.post(reverse('usuario_editar', args=[self.pessoa.pk]), dados)
        self.assertEqual(self.pessoa.perfil.jornadas.count(), 1)

    def test_reaplicar_jornada_e_agendar_preserva_vigencia(self):
        from .services import configuracao_jornada, vincular_jornada

        self.vincular()
        outra = self.jornada.__class__.objects.get(nome='40h · Seg–sex · 09h')
        vincular_jornada(self.pessoa.perfil, outra, self.segunda + timedelta(days=7))
        self.assertEqual(configuracao_jornada(self.pessoa, self.segunda)['horarios'][0], '08:00')
        self.assertEqual(configuracao_jornada(self.pessoa, self.segunda + timedelta(days=7))['horarios'][0], '09:00')

    def test_feriado_com_batida_completa_e_progresso_sem_divisao_por_zero(self):
        from .models import Feriado
        from .relatorios import calcular_horas_dia, calcular_progresso

        self.vincular()
        Feriado.objects.create(data=self.segunda, nome='Feriado local')
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(self.segunda, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(self.segunda, 12))
        resultado = calcular_horas_dia(self.pessoa, self.segunda)
        self.assertEqual(resultado['diferenca'], timedelta(hours=4))
        progresso = calcular_progresso(resultado['horarios'], _momento(self.segunda, 12), timedelta())
        self.assertEqual(progresso['percentual'], 100)

    def test_jornada_inativa_nao_aceita_novo_vinculo(self):
        from .forms import UsuarioAdministracaoForm

        self.jornada.ativa = False
        self.jornada.save()
        form = UsuarioAdministracaoForm(instance=self.pessoa, administrador=self.admin)
        self.assertNotIn(self.jornada, form.fields['jornada'].queryset)
        self.vincular()
        form = UsuarioAdministracaoForm(instance=self.pessoa, administrador=self.admin)
        self.assertIn(self.jornada, form.fields['jornada'].queryset)

    def test_sincronizacao_pela_tela_valida_ano(self):
        from .models import Feriado

        resposta = self.client.post(reverse('feriados'), {'ano': 2027})
        self.assertRedirects(resposta, reverse('feriados') + '?ano=2027')
        self.assertEqual(Feriado.objects.filter(data__year=2027).count(), 9)
        resposta = self.client.post(reverse('feriados'), {'ano': 'inválido'})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['form'].errors)
        self.assertEqual(Feriado.objects.count(), 9)

    def test_cadastro_feriado_e_data_duplicada(self):
        dados = {'data': '2027-03-26', 'nome': 'Feriado local', 'dispensa_expediente': 'on'}
        self.assertRedirects(self.client.post(reverse('feriado_criar'), dados), reverse('feriados') + '?ano=2027')
        resposta = self.client.post(reverse('feriado_criar'), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['form'].errors)

    def test_reaplicar_no_formulario_e_mudar_email_nao_reaplica(self):
        self.vincular()
        dados = {
            'username': self.pessoa.username,
            'first_name': 'Pessoa',
            'last_name': 'Teste',
            'email': 'pessoa@example.com',
            'papel': Perfil.PAPEL_FUNCIONARIO,
            'jornada': self.jornada.pk,
            'jornada_inicio': '2026-11-20',
            'is_active': 'on',
        }
        self.client.post(reverse('usuario_editar', args=[self.pessoa.pk]), dados)
        self.assertEqual(self.pessoa.perfil.jornadas.count(), 1)
        self.client.post(reverse('usuario_editar', args=[self.pessoa.pk]), dados | {'atualizar_jornada': 'on'})
        self.assertEqual(self.pessoa.perfil.jornadas.count(), 2)


@override_settings(STORAGES=STORAGES_DE_TESTE)
class FolgasBancoHorasTests(TestCase):
    def setUp(self):
        self.gestor = User.objects.create_user('gestora_folga', first_name='Ana', last_name='Souza')
        self.gestor.perfil.papel = Perfil.PAPEL_GESTOR
        self.gestor.perfil.save()
        self.pessoa = User.objects.create_user('bruno_folga', first_name='Bruno', last_name='Carvalho')
        self.pessoa.perfil.gestor = self.gestor.perfil
        self.pessoa.perfil.save()
        self.segunda = date(2026, 11, 16)

    def _folga(self, data, tipo, horas=None):
        from .models import Folga

        return Folga.objects.create(
            funcionario=self.pessoa, data=data, tipo=tipo, horas_abatidas=horas, motivo='Teste', lancada_por=self.gestor
        )

    def test_banco_de_horas_soma_extras_desconta_faltas_e_compensacoes(self):
        from .models import Folga
        from .services import saldo_banco_horas

        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(self.segunda, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(self.segunda, 17))  # 9h: +1h15
        quarta = self.segunda + timedelta(days=2)
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(quarta, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(quarta, 15, 50))  # 5 min a mais: dentro da tolerância
        sabado = self.segunda + timedelta(days=5)
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(sabado, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(sabado, 10))  # fim de semana: +2h
        with patch('django.utils.timezone.localdate', return_value=sabado):
            # terça sem batida: -7h45; quinta e sexta sem batida: -15h30
            self.assertEqual(saldo_banco_horas(self.pessoa), timedelta(hours=1, minutes=15 + 120 - 3 * 465))
            self._folga(self.segunda + timedelta(days=4), Folga.DISPENSA)  # sexta abonada
            self.assertEqual(saldo_banco_horas(self.pessoa), timedelta(hours=1, minutes=15 + 120 - 2 * 465))
            self._folga(self.segunda + timedelta(days=7), Folga.COMPENSACAO, timedelta(hours=7, minutes=45))
            self.assertEqual(saldo_banco_horas(self.pessoa), timedelta(hours=1, minutes=15 + 120 - 3 * 465))

    def test_cartao_mostra_saldo_do_banco_com_as_compensacoes(self):
        from .models import Folga
        from .services import saldo_banco_horas

        terca, quarta = self.segunda + timedelta(days=1), self.segunda + timedelta(days=2)
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(self.segunda, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(self.segunda, 17))  # 9h: +1h15
        self._folga(terca, Folga.COMPENSACAO, timedelta(hours=7, minutes=45))
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(quarta, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(quarta, 15, 45))  # jornada exata
        with patch('django.utils.timezone.localdate', return_value=quarta):
            item = montar_relatorio(None, self.pessoa, self.segunda, quarta, False)[0]
            banco = preparar_cartao_ponto(item, self.segunda, quarta)['cartao']['banco']
            ate_segunda = saldo_banco_horas(self.pessoa, ate=self.segunda)

        self.assertEqual(
            (banco['extras'], banco['faltas'], banco['compensacoes']), ('01:15', '00:00', '07:45')
        )
        self.assertEqual((banco['saldo_periodo'], banco['saldo_acumulado']), ('-06:30', '-06:30'))
        self.assertEqual(banco['data_saldo'], quarta)
        # Parando na segunda, a compensação de terça ainda não abate.
        self.assertEqual(ate_segunda, timedelta(hours=1, minutes=15))

    def _domingo_trabalhado(self):
        """Domingo de 4h e uma semana seguinte de segunda a sábado com jornada exata (sábado de 2h)."""
        domingo = self.segunda + timedelta(days=6)
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(domingo, 9))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(domingo, 13))
        for dias in range(1, 6):
            _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(domingo + timedelta(days=dias), 8))
            _batida(self.pessoa, RegistroPonto.SAIDA, _momento(domingo + timedelta(days=dias), 15, 45))
        sabado = domingo + timedelta(days=6)
        return domingo, sabado

    def test_domingo_vale_o_dobro_sem_folga_na_semana_seguinte(self):
        from .services import configuracao_jornada, fator_do_dia, saldo_banco_horas

        domingo, sabado = self._domingo_trabalhado()
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(sabado, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(sabado, 10))

        self.assertEqual(fator_do_dia(self.pessoa, domingo, configuracao_jornada(self.pessoa, domingo)), 2)
        with patch('django.utils.timezone.localdate', return_value=sabado):
            # domingo 4h x 2 = 8h, mais as 2h do sábado
            self.assertEqual(saldo_banco_horas(self.pessoa), timedelta(hours=10))
            item = montar_relatorio(None, self.pessoa, domingo, domingo, False)[0]
            linha = preparar_cartao_ponto(item, domingo, domingo)['cartao']['linhas'][0]
        self.assertEqual((linha['extras'], linha['observacao']), ('08:00', 'Dom. +100%'))

    def test_domingo_vale_40_por_cento_com_folga_ou_sabado_livre(self):
        from .models import Folga
        from .services import configuracao_jornada, fator_do_dia, saldo_banco_horas

        domingo, sabado = self._domingo_trabalhado()

        configuracao = configuracao_jornada(self.pessoa, domingo)
        self.assertEqual(fator_do_dia(self.pessoa, domingo, configuracao), 1.4)  # sábado sem trabalho
        with patch('django.utils.timezone.localdate', return_value=sabado + timedelta(days=1)):
            self.assertEqual(saldo_banco_horas(self.pessoa), timedelta(hours=5, minutes=36))  # 4h x 1,4
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(sabado, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(sabado, 10))
        self._folga(domingo + timedelta(days=3), Folga.DISPENSA)
        self.assertEqual(fator_do_dia(self.pessoa, domingo, configuracao), 1.4)  # folga na quarta
        self.assertEqual(fator_do_dia(self.pessoa, sabado, configuracao_jornada(self.pessoa, sabado)), 1)

    def test_hhmm_com_sinal(self):
        from .utils import hhmm_com_sinal

        self.assertEqual(hhmm_com_sinal(timedelta(hours=56, minutes=27)), '+56:27')
        self.assertEqual(hhmm_com_sinal(-timedelta(hours=6, minutes=12)), '-06:12')
        self.assertEqual(hhmm_com_sinal(timedelta(seconds=30)), '00:00')

    def test_folga_zera_carga_e_marca_cartao(self):
        from .models import Folga
        from .services import configuracao_jornada

        terca = self.segunda + timedelta(days=1)
        self._folga(terca, Folga.COMPENSACAO, timedelta(hours=7, minutes=45))
        configuracao = configuracao_jornada(self.pessoa, terca)
        self.assertEqual(configuracao['carga'], timedelta())
        self.assertEqual(configuracao['carga_sem_folga'], timedelta(hours=7, minutes=45))
        item = montar_relatorio(None, self.pessoa, terca, terca, False)[0]
        linha = preparar_cartao_ponto(item, terca, terca)['cartao']['linhas'][0]
        self.assertEqual((linha['faltas'], linha['observacao']), ('', 'Folga comp.'))

    def test_gestor_lanca_compensacao_e_formulario_valida(self):
        from .models import Folga

        self.client.force_login(self.gestor)
        dados = {'funcionarios': [self.pessoa.pk], 'data': '2026-11-23', 'tipo': 'compensacao', 'motivo': 'Fechamento'}
        resposta = self.client.post(reverse('folga_lancar'), dados)
        self.assertRedirects(resposta, reverse('folgas'))
        folga = Folga.objects.get(funcionario=self.pessoa)
        self.assertEqual(folga.horas_abatidas, timedelta(hours=7, minutes=45))
        self.assertContains(self.client.get(reverse('folgas')), 'Fechamento')

        repetida = self.client.post(reverse('folga_lancar'), dados)
        self.assertContains(repetida, 'Já existe folga em 23/11/2026')
        sabado = self.client.post(reverse('folga_lancar'), dados | {'data': '2026-11-21', 'tipo': 'dispensa'})
        self.assertContains(sabado, '21/11/2026 é sábado e já não tem expediente para Bruno Carvalho.')

        from .models import Feriado

        Feriado.objects.update_or_create(data=date(2026, 11, 20), defaults={'nome': 'Consciência Negra'})
        feriado = self.client.post(reverse('folga_lancar'), dados | {'data': '2026-11-20'})
        self.assertContains(
            feriado, '20/11/2026 é feriado (Consciência Negra) e já não tem expediente para Bruno Carvalho.'
        )

        parcial = self.client.get(reverse('folga_lancar'), dados | {'parcial': '1'})
        self.assertContains(parcial, 'Abate 7h45min')

    def test_cancelar_so_na_propria_equipe_e_colaborador_sem_acesso(self):
        from .models import Folga

        folga = self._folga(self.segunda, Folga.DISPENSA)
        outro = User.objects.create_user('outro_gestor')
        outro.perfil.papel = Perfil.PAPEL_GESTOR
        outro.perfil.save()
        self.client.force_login(outro)
        self.assertEqual(self.client.post(reverse('folga_cancelar', args=[folga.pk])).status_code, 404)

        self.client.force_login(self.pessoa)
        self.assertRedirects(self.client.get(reverse('folgas')), reverse('painel'))

        self.client.force_login(self.gestor)
        self.client.post(reverse('folga_cancelar', args=[folga.pk]))
        folga.refresh_from_db()
        self.assertFalse(folga.ativa)
        self.assertEqual(folga.cancelada_por, self.gestor)

    def test_painel_e_equipe_mostram_folga_do_dia(self):
        from .models import Folga

        self._folga(timezone.localdate(), Folga.DISPENSA)
        self.client.force_login(self.pessoa)
        painel = self.client.get(reverse('painel'))
        self.assertContains(painel, 'Folga lançada por Ana Souza')
        self.assertContains(painel, 'Contam como extra')

        self.client.force_login(self.gestor)
        equipe = self.client.get(reverse('painel'), {'aba': 'equipe'})
        self.assertContains(equipe, '<span class="selo selo--sucesso">Folga</span>', html=True)

    def test_aviso_de_feriado_e_folga_semanal(self):
        from .models import Feriado
        from .services import aviso_do_dia

        Feriado.objects.update_or_create(data=self.segunda, defaults={'nome': 'Feriado local'})
        self.assertEqual(aviso_do_dia(self.pessoa, self.segunda)['titulo'], 'Feriado: Feriado local')
        self.assertEqual(aviso_do_dia(self.pessoa, self.segunda + timedelta(days=5))['titulo'], 'Folga semanal')
        self.assertIsNone(aviso_do_dia(self.pessoa, self.segunda + timedelta(days=1)))


def _planilha(dias, cpf='02264845643'):
    """Planilha de banco de horas no formato importado: CPF em Resumo!B3 e uma aba de mês a partir da linha 5."""
    from openpyxl import Workbook

    livro = Workbook()
    livro.active.title = 'Resumo'
    livro['Resumo']['B3'] = cpf
    aba = livro.create_sheet('Outubro 2026')
    aba.append(['Banco de Horas — Outubro 2026'])
    for numero, (dia, marcado, horas) in enumerate(dias, start=5):
        aba.cell(row=numero, column=1, value=datetime.combine(dia, time()))
        aba.cell(row=numero, column=3, value=marcado)
        for coluna, hora in enumerate(horas, start=4):
            aba.cell(row=numero, column=coluna, value=hora)
    aba.cell(row=len(dias) + 6, column=9, value='Total do mês:')
    arquivo = BytesIO()
    livro.save(arquivo)
    return SimpleUploadedFile('banco_de_horas.xlsx', arquivo.getvalue())


@override_settings(STORAGES=STORAGES_DE_TESTE)
class ImportacaoPlanilhaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin_planilha', first_name='Caio')
        self.admin.perfil.papel = Perfil.PAPEL_ADMIN
        self.admin.perfil.save()
        self.pessoa = User.objects.create_user('gui_planilha', first_name='Guilherme', last_name='Lima')
        self.pessoa.perfil.cpf = '02264845643'
        self.pessoa.perfil.save()
        self.client.force_login(self.admin)
        self.dia_util = (date(2026, 10, 1), None, [time(8), time(12), time(13), time(16, 15), time(16, 30), time(18)])

    def _importar(self, planilha, pessoa=None):
        dados = {'planilha': planilha, 'funcionario': (pessoa or self.pessoa).pk}
        return self.client.post(reverse('importar_planilha'), dados, follow=True)

    def test_importa_batidas_folgas_e_respeita_feriados_cadastrados(self):
        from .models import Feriado, Folga

        Feriado.objects.create(data=date(2026, 10, 12), nome='Nossa Senhora Aparecida')
        zerado = [time(0), time(0), time(0), time(16, 15), time(16, 30), time(0)]
        planilha = _planilha([
            self.dia_util,
            (date(2026, 10, 9), 'S', []),
            (date(2026, 10, 12), 'S', []),
            (date(2026, 10, 16), None, zerado),
            (date(2026, 10, 18), None, [time(11, 45), None, None, None, None, time(16, 50)]),
            (date(2026, 10, 20), 's', zerado),
            (date(2026, 10, 24), None, []),
        ])

        resposta = self._importar(planilha)

        self.assertContains(resposta, 'Planilha de Guilherme Lima importada: 8 batidas e 3 folgas.')
        horarios = [
            timezone.localtime(r.data_hora).strftime('%d %H:%M')
            for r in RegistroPonto.objects.filter(funcionario=self.pessoa, ativo=True)
        ]
        self.assertEqual(horarios, [
            '01 08:00', '01 12:00', '01 13:00', '01 16:15', '01 16:30', '01 18:00', '18 11:45', '18 16:50',
        ])
        self.assertFalse(RegistroPonto.objects.filter(registrado_manualmente=False).exists())
        criacoes = HistoricoAlteracaoPonto.objects.filter(tipo_acao=HistoricoAlteracaoPonto.CRIACAO_MANUAL)
        self.assertEqual(criacoes.count(), 8)
        lancadas = Folga.objects.filter(funcionario=self.pessoa)
        folgas = {f.data.day: (f.tipo, f.motivo, f.horas_abatidas) for f in lancadas}
        self.assertEqual(folgas, {
            9: (Folga.DISPENSA, 'Day-Off', None),
            16: (Folga.COMPENSACAO, 'Compensação do banco de horas', timedelta(hours=7, minutes=45)),
            20: (Folga.DISPENSA, 'Folga negociada', None),
        })

    def test_planilha_substitui_batidas_e_folgas_do_mesmo_dia(self):
        from .models import Folga

        antiga = _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(date(2026, 10, 1), 9))
        outro_dia = _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(date(2026, 10, 2), 9))
        folga = Folga.objects.create(
            funcionario=self.pessoa, data=date(2026, 10, 1), tipo=Folga.DISPENSA, motivo='Antiga',
            lancada_por=self.admin,
        )

        resposta = self._importar(_planilha([self.dia_util]))

        self.assertContains(resposta, 'Substituídas: 1 batidas e 1 folgas que já estavam no sistema.')
        antiga.refresh_from_db()
        outro_dia.refresh_from_db()
        folga.refresh_from_db()
        self.assertFalse(antiga.ativo)
        self.assertTrue(outro_dia.ativo)
        self.assertFalse(folga.ativa)
        self.assertTrue(antiga.historico.filter(tipo_acao=HistoricoAlteracaoPonto.EXCLUSAO).exists())

    def test_cpf_digitado_como_numero_recupera_o_zero_da_frente(self):
        from .services import ler_planilha_ponto

        cpf, batidas, folgas, avisos = ler_planilha_ponto(_planilha([self.dia_util], cpf=2264845643))

        self.assertEqual(cpf, '02264845643')
        self.assertEqual(len(batidas), 6)
        self.assertEqual((folgas, avisos), ([], []))

    def test_dia_fora_de_ordem_e_datas_futuras_viram_avisos(self):
        fora_de_ordem = (date(2026, 10, 2), None, [time(13), time(12), None, None, None, time(18)])

        with patch('django.utils.timezone.localdate', return_value=date(2026, 9, 30)):
            resposta = self._importar(_planilha([self.dia_util, fora_de_ordem]))

        self.assertContains(resposta, '02/10/2026: os horários estão fora de ordem. O dia não foi importado.')
        self.assertContains(resposta, 'Batidas em datas futuras não foram importadas: 01/10/2026.')
        self.assertFalse(RegistroPonto.objects.exists())

    def test_cpf_sem_cadastro_importa_para_o_colaborador_escolhido(self):
        resposta = self._importar(_planilha([self.dia_util], cpf='11122233344'))

        self.assertContains(resposta, 'Planilha de Guilherme Lima importada: 6 batidas e 0 folgas.')
        self.assertEqual(RegistroPonto.objects.filter(funcionario=self.pessoa).count(), 6)

    def test_planilha_sem_cpf_importa_para_o_colaborador_escolhido(self):
        resposta = self._importar(_planilha([self.dia_util], cpf=None))

        self.assertContains(resposta, 'Planilha de Guilherme Lima importada: 6 batidas e 0 folgas.')

    def test_cpf_de_outra_pessoa_nao_grava_nada(self):
        outra = User.objects.create_user('rafa_planilha', first_name='Rafael', last_name='Souza')

        resposta = self._importar(_planilha([self.dia_util]), pessoa=outra)

        self.assertContains(resposta, 'O CPF da planilha (022.648.456-43) é de Guilherme Lima.')
        self.assertFalse(RegistroPonto.objects.exists())

    def test_arquivo_que_nao_e_planilha_e_recusado(self):
        resposta = self._importar(SimpleUploadedFile('ponto.xlsx', b'nao sou uma planilha'))

        self.assertContains(resposta, 'Não foi possível abrir o arquivo. Envie a planilha no formato .xlsx.')

    def test_menu_gestao_mostra_importacao_para_gestor_e_administrador(self):
        link = f'href="{reverse("importar_planilha")}"'

        self.assertContains(self.client.get(reverse('painel')), link)
        self.admin.perfil.papel = Perfil.PAPEL_GESTOR
        self.admin.perfil.save()
        self.assertContains(self.client.get(reverse('painel')), link)
        self.admin.perfil.papel = Perfil.PAPEL_FUNCIONARIO
        self.admin.perfil.save()
        self.assertNotContains(self.client.get(reverse('painel')), link)

    def test_gestor_importa_somente_para_a_propria_equipe(self):
        self.admin.perfil.papel = Perfil.PAPEL_GESTOR
        self.admin.perfil.save()
        fora = User.objects.create_user('fora_planilha', first_name='Fora')
        self.pessoa.perfil.gestor = self.admin.perfil
        self.pessoa.perfil.save()

        tela = self.client.get(reverse('importar_planilha'))
        self.assertContains(tela, 'Guilherme Lima')
        self.assertNotContains(tela, '>Fora<')

        resposta = self._importar(_planilha([self.dia_util], cpf=None), pessoa=fora)
        self.assertContains(resposta, 'Faça uma escolha válida')
        self.assertFalse(RegistroPonto.objects.exists())

        resposta = self._importar(_planilha([self.dia_util]))
        self.assertContains(resposta, 'Planilha de Guilherme Lima importada: 6 batidas e 0 folgas.')

    def test_colaborador_nao_importa(self):
        self.admin.perfil.papel = Perfil.PAPEL_FUNCIONARIO
        self.admin.perfil.save()

        self._importar(_planilha([self.dia_util]))
        self.assertRedirects(self.client.get(reverse('importar_planilha')), reverse('painel'))
        self.assertFalse(RegistroPonto.objects.exists())


@override_settings(STORAGES=STORAGES_DE_TESTE)
class BancoHorasPorOrigemTests(TestCase):
    """Descontos saem das horas positivas mais antigas; o total é sempre o de saldo_banco_horas."""

    def setUp(self):
        from .models import Jornada, VinculoJornada

        self.gestor = User.objects.create_user('gestor_banco', first_name='Gil')
        self.gestor.perfil.papel = Perfil.PAPEL_GESTOR
        self.gestor.perfil.save()
        self.pessoa = User.objects.create_user('pessoa_banco', first_name='Bia')
        self.pessoa.perfil.gestor = self.gestor.perfil
        self.pessoa.perfil.save()
        # Jornada sem dias de trabalho: sem faltas no meio, cada dia trabalhado vira crédito inteiro.
        jornada = Jornada.objects.create(nome='Sem expediente', semana={})
        VinculoJornada.objects.create(perfil=self.pessoa.perfil, jornada=jornada, inicio=date(2026, 1, 1), semana={})
        self.hoje = date(2026, 9, 30)

    def _horas(self, dia, horas):
        _batida(self.pessoa, RegistroPonto.ENTRADA, _momento(dia, 8))
        _batida(self.pessoa, RegistroPonto.SAIDA, _momento(dia, 8 + horas))

    def _compensacao(self, dia, horas):
        from .models import Folga

        Folga.objects.create(
            funcionario=self.pessoa, data=dia, tipo=Folga.COMPENSACAO, horas_abatidas=horas, motivo='Teste',
            lancada_por=self.gestor,
        )

    def test_folga_desconta_do_mes_mais_antigo(self):
        from .services import banco_horas_por_origem, saldo_banco_horas

        self._horas(date(2026, 7, 4), 10)
        self._horas(date(2026, 8, 1), 10)
        self._compensacao(date(2026, 9, 15), timedelta(hours=7, minutes=45))

        with patch('django.utils.timezone.localdate', return_value=self.hoje):
            banco = banco_horas_por_origem(self.pessoa)
            saldo = saldo_banco_horas(self.pessoa)

        restantes = [(m['mes'], m['restante']) for m in banco['meses']]
        self.assertEqual(restantes, [(7, timedelta(hours=2, minutes=15)), (8, timedelta(hours=10))])
        origem = {'data': date(2026, 7, 4), 'horas': timedelta(hours=7, minutes=45)}
        self.assertEqual(banco['descontos'][0]['origens'], [origem])
        self.assertEqual(banco['saldo'], saldo)
        self.assertEqual(saldo, timedelta(hours=12, minutes=15))

    def test_desconto_sem_horas_vira_devedor_e_e_pago_pelo_proximo_credito(self):
        from .services import banco_horas_por_origem

        self._horas(date(2026, 6, 6), 2)
        self._compensacao(date(2026, 6, 10), timedelta(hours=5))
        self._horas(date(2026, 7, 4), 10)

        with patch('django.utils.timezone.localdate', return_value=self.hoje):
            banco = banco_horas_por_origem(self.pessoa)

        origens = [(o['data'].month, o['horas']) for o in banco['descontos'][0]['origens']]
        self.assertEqual(origens, [(6, timedelta(hours=2)), (7, timedelta(hours=3))])
        self.assertEqual((banco['devedor'], banco['saldo']), (timedelta(), timedelta(hours=7)))

    def test_tela_mostra_o_banco_conforme_o_papel(self):
        outra = User.objects.create_user('fora_da_equipe', first_name='Rui')
        self._horas(date(2026, 7, 4), 10)
        self._compensacao(date(2026, 9, 15), timedelta(hours=7, minutes=45))

        self.client.force_login(self.pessoa)
        with patch('django.utils.timezone.localdate', return_value=self.hoje):
            propria = self.client.get(reverse('banco_de_horas'), {'funcionario': outra.pk})
        self.assertContains(propria, '+2h15min')
        self.assertContains(propria, 'julho de 2026 (7h45min)')
        self.assertNotContains(propria, 'name="funcionario"')
        self.assertNotContains(propria, 'Rui')

        self.client.force_login(self.gestor)
        with patch('django.utils.timezone.localdate', return_value=self.hoje):
            da_equipe = self.client.get(reverse('banco_de_horas'), {'funcionario': self.pessoa.pk})
            de_fora = self.client.get(reverse('banco_de_horas'), {'funcionario': outra.pk})
        self.assertContains(da_equipe, '<h2 id="titulo-saldo">Bia</h2>', html=False)
        self.assertContains(da_equipe, 'name="funcionario"')
        self.assertContains(de_fora, '<h2 id="titulo-saldo">Gil</h2>', html=False)
