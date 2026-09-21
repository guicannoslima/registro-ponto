from django.contrib.auth.models import User
from .models import Perfil

def funcionarios_visiveis(usuario):
    perfil = usuario.perfil
    if perfil.papel == perfil.PAPEL_ADMIN:
        return User.objects.filter(perfil__isnull=False)
    
    elif perfil.papel == perfil.PAPEL_GESTOR:
        return User.objects.filter(perfil__gestor=usuario.perfil)
        
    elif perfil.papel == perfil.PAPEL_FUNCIONARIO:
        return User.objects.none()