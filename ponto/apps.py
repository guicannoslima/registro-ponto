from django.apps import AppConfig


class PontoConfig(AppConfig):
    name = 'ponto'

    def ready(self):
        from . import signals  # noqa: F401  (registra os receivers)
