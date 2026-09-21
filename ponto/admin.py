from django.contrib import admin
from .models import Perfil, RegistroPonto

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