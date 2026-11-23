"""Baixa modelos públicos OpenCV, verificando o SHA-256 publicado no Git LFS."""

import hashlib
from urllib.error import URLError
from urllib.request import urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

MODELOS = (
    ('face_detection_yunet', 'face_detection_yunet_2023mar.onnx',
     '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'),
    ('face_recognition_sface', 'face_recognition_sface_2021dec.onnx',
     '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'),
)


class Command(BaseCommand):
    help = 'Prepara os modelos YuNet e SFace para reconhecimento facial local.'

    def handle(self, *args, **options):
        pasta = settings.FACIAL_MODELS_DIR
        pasta.mkdir(parents=True, exist_ok=True)
        for diretorio, nome, digest in MODELOS:
            destino = pasta / nome
            if destino.is_file() and hashlib.sha256(destino.read_bytes()).hexdigest() == digest:
                self.stdout.write(f'{nome}: já verificado.')
                continue
            url = f'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/{diretorio}/{nome}'
            try:
                with urlopen(url, timeout=120) as resposta:  # noqa: S310 - origem HTTPS fixa
                    dados = resposta.read(40 * 1024 * 1024)
                if hashlib.sha256(dados).hexdigest() != digest:
                    raise CommandError(f'{nome}: SHA-256 diferente do modelo esperado.')
                temporario = destino.with_suffix('.tmp')
                temporario.write_bytes(dados)
                temporario.replace(destino)
            except (URLError, OSError) as exc:
                raise CommandError(f'Não foi possível preparar {nome}: {exc}') from exc
            self.stdout.write(self.style.SUCCESS(f'{nome}: pronto.'))
