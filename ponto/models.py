from django.conf import settings
from django.db import models


class Jornada(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    semana = models.JSONField(default=dict)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class VinculoJornada(models.Model):
    perfil = models.ForeignKey('Perfil', on_delete=models.CASCADE, related_name='jornadas')
    jornada = models.ForeignKey(Jornada, on_delete=models.PROTECT, null=True, blank=True)
    inicio = models.DateField()
    # Cópia dos horários contratados: editar o modelo não reescreve o histórico.
    semana = models.JSONField(default=dict)
    nome = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-inicio']
        constraints = [models.UniqueConstraint(fields=['perfil', 'inicio'], name='jornada_por_inicio')]

    def __str__(self):
        return f'{self.perfil} — {self.nome} desde {self.inicio:%d/%m/%Y}'


class Feriado(models.Model):
    data = models.DateField(unique=True)
    nome = models.CharField(max_length=150)
    nacional = models.BooleanField(default=False, editable=False)
    dispensa_expediente = models.BooleanField(default=True)

    class Meta:
        ordering = ['data']

    def __str__(self):
        return f'{self.data:%d/%m/%Y} — {self.nome}'


class Funcao(models.Model):
    
    nome = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.nome

class Perfil(models.Model):

    PAPEL_FUNCIONARIO = "funcionario"
    PAPEL_GESTOR = "gestor"
    PAPEL_ADMIN = "admin"

    PAPEL_CHOICES = [
        (PAPEL_FUNCIONARIO, "Colaborador"),
        (PAPEL_GESTOR, "Gestor"),
        (PAPEL_ADMIN, "Administrador"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    papel = models.CharField(
        max_length=20,
        choices=PAPEL_CHOICES,
        default=PAPEL_FUNCIONARIO,
    )
    gestor = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipe",
        limit_choices_to={"papel": PAPEL_GESTOR},
    )

    funcao = models.ForeignKey(
        'Funcao',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    foto = models.ImageField(upload_to='perfis/', blank=True, verbose_name='foto de perfil')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_papel_display()})"

    cpf = models.CharField(max_length=11, unique=True, null=True, blank=True)

class RegistroPonto(models.Model):

    ENTRADA = "entrada"
    SAIDA_ALMOCO = "saida_almoco"
    VOLTA_ALMOCO = "volta_almoco"
    SAIDA_CAFE = "saida_cafe"
    VOLTA_CAFE = "volta_cafe"
    SAIDA = "saida"

    TIPO_CHOICES = [
        (ENTRADA, "Entrada"),
        (SAIDA_ALMOCO, "Saída para o almoço"),
        (VOLTA_ALMOCO, "Volta do almoço"),
        (SAIDA_CAFE, "Saída para o café"),
        (VOLTA_CAFE, "Volta do café"),
        (SAIDA, "Saída"),
    ]

    ORDEM_TIPOS = [
        ENTRADA,
        SAIDA_ALMOCO,
        VOLTA_ALMOCO,
        SAIDA_CAFE,
        VOLTA_CAFE,
        SAIDA
    ]

    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='colaborador',
        on_delete=models.CASCADE,
        related_name="registros_ponto",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    data_hora = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)

    foto = models.ImageField(upload_to="pontos/%Y/%m/%d/", null=True, blank=True)
    registrado_manualmente = models.BooleanField(default=False)
    observacao = models.TextField(blank=True)

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["data_hora"]

    def __str__(self):
        return f"{self.funcionario} - {self.get_tipo_display()} em {self.data_hora:%d/%m/%Y %H:%M}"

class HistoricoAlteracaoPonto(models.Model):
    registro = models.ForeignKey(
        RegistroPonto,
        on_delete=models.CASCADE,
        related_name='historico',
    )

    CRIACAO_MANUAL = 'criacao_manual'
    EDICAO = 'edicao'
    EXCLUSAO = 'exclusao'

    ACAO_CHOICES = [
        (CRIACAO_MANUAL, 'Criação manual'),
        (EDICAO, 'Edição'),
        (EXCLUSAO, 'Exclusão'),
    ]

    tipo_acao = models.CharField(max_length= 20, choices=ACAO_CHOICES)

    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )

    motivo = models.TextField(
    )

    criado_em = models.DateTimeField(
        auto_now_add = True
    )

class SolicitacaoAjustePonto(models.Model):
    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='colaborador',
        on_delete=models.SET_NULL,
        null=True,
        related_name = 'solicitacoes',
    )

    CRIACAO = "criacao"
    EXCLUSAO = "exclusao"

    TIPO_ACAO = [
        (CRIACAO,"Criação"),
        (EXCLUSAO, "Exclusão"),
    ] 

    tipo_acao = models.CharField(max_length=20, choices=TIPO_ACAO)

    registro = models.ForeignKey(
        RegistroPonto,
        on_delete=models.SET_NULL,
        null = True,
        blank = True,
    )

    tipo = models.CharField(max_length=20, choices=RegistroPonto.TIPO_CHOICES, null=True, blank=True)

    data_hora = models.DateTimeField(null=True, blank=True)

    motivo_funcionario = models.TextField(verbose_name='motivo do colaborador')

    PENDENTE = "pendente"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"

    STATUS_CHOICE = [
        (PENDENTE, 'Pendente'),
        (APROVADO, 'Aprovado'),
        (REJEITADO, 'Rejeitado'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICE, default=PENDENTE)

    gestor_revisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitacoes_revisadas',
    )

    motivo_rejeicao = models.TextField(
        blank=True
    )

    criado_em = models.DateTimeField(auto_now_add=True)


class CadastroFacial(models.Model):
    funcionario = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='colaborador',
        on_delete=models.CASCADE, related_name='cadastro_facial',
    )
    vetor = models.JSONField(editable=False)
    cadastrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'cadastro facial'
        verbose_name_plural = 'cadastros faciais'

    def __str__(self):
        return f'Cadastro facial de {self.funcionario}'


class ConfiguracaoEmail(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    servidor = models.CharField(max_length=255)
    porta = models.PositiveIntegerField(default=587)
    usuario = models.CharField(max_length=254, blank=True)
    senha_criptografada = models.TextField(blank=True, editable=False)
    seguranca = models.CharField(
        max_length=10, default='tls',
        choices=[('tls', 'STARTTLS'), ('ssl', 'SSL/TLS'), ('nenhuma', 'Sem criptografia')],
    )
    remetente = models.EmailField()
    atualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'configuração de e-mail'
        verbose_name_plural = 'configurações de e-mail'
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name='configuracao_email_unica')]

    def __str__(self):
        return 'Envio de e-mails'
