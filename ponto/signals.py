from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Perfil


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_perfil_do_usuario(sender, instance, created, raw=False, **kwargs):
    """Garante que todo usuário tenha um Perfil, venha de onde vier (cadastro, createsuperuser, admin, shell).

    Superusuários recebem o papel de administrador; os demais começam como colaborador.
    """
    if not created or raw:  # raw: carga de fixtures (loaddata), em que o Perfil vem junto nos dados
        return

    papel = Perfil.PAPEL_ADMIN if instance.is_superuser else Perfil.PAPEL_FUNCIONARIO
    Perfil.objects.get_or_create(user=instance, defaults={'papel': papel})
