from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ponto.services import sincronizar_feriados_nacionais


class Command(BaseCommand):
    help = 'Carrega feriados civis nacionais sem duplicar nem substituir ajustes manuais.'

    def add_arguments(self, parser):
        parser.add_argument('--ano', type=int, default=timezone.localdate().year)

    def handle(self, *args, **options):
        ano = options['ano']
        if not 2000 <= ano <= 2099:
            raise CommandError('Informe um ano entre 2000 e 2099.')
        criados = sincronizar_feriados_nacionais(ano)
        self.stdout.write(self.style.SUCCESS(f'{ano}: {criados} feriados adicionados.'))
