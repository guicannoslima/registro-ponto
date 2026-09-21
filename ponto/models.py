from django.conf import settings
from django.db import models


class Perfil(models.Model):

    PAPEL_FUNCIONARIO = "funcionario"
    PAPEL_GESTOR = "gestor"
    PAPEL_ADMIN = "admin"

    PAPEL_CHOICES = [
        (PAPEL_FUNCIONARIO, "Funcionário"),
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

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_papel_display()})"


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