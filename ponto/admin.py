from django.contrib import admin
from .models import Perfil, RegistroPonto, HistoricoAlteracaoPonto, SolicitacaoAjustePonto

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "papel", "gestor")
    list_filter = ("papel",)
    search_fields = ("user__username", "user__first_name", "user__last_name")

@admin.register(RegistroPonto)
class RegistroPontoAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "tipo", "data_hora", "registrado_manualmente")
    list_filter = ("tipo", "registrado_manualmente")
    search_fields = ("funcionario__username", "funcionario__first_name",)
    date_hierarchy = "data_hora"

@admin.register(HistoricoAlteracaoPonto)
class HistoricoAlteracaoPontoAdmin(admin.ModelAdmin):
    list_display = ('registro', 'tipo_acao', 'realizado_por', 'criado_em')
    list_filter = ("tipo_acao",)

@admin.register(SolicitacaoAjustePonto)
class SolicitacaoAjustePontoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'tipo_acao', 'status', 'criado_em')