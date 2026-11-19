"""Reconhecimento local com YuNet e SFace; imagens são usadas apenas em memória."""

from io import BytesIO
from threading import Lock

from django.conf import settings
from PIL import Image, UnidentifiedImageError

from .constants import FACIAL_LIMIAR, FACIAL_MARGEM, FOTO_MAX_BYTES, FOTO_MAX_PIXELS
from .exceptions import ErroFacial, FacialIndisponivel, SemRosto

_lock = Lock()
_motor = None


def _motor_local():
    global _motor
    if _motor is None:
        try:
            import cv2
        except ImportError as exc:
            raise FacialIndisponivel('Instale as dependências de reconhecimento facial no servidor.') from exc
        pasta = settings.FACIAL_MODELS_DIR
        detector = pasta / 'face_detection_yunet_2023mar.onnx'
        reconhecedor = pasta / 'face_recognition_sface_2021dec.onnx'
        if not detector.is_file() or not reconhecedor.is_file():
            raise FacialIndisponivel('O administrador precisa preparar os modelos de reconhecimento facial.')
        try:
            _motor = (
                cv2.FaceDetectorYN.create(str(detector), '', (640, 480), 0.9),
                cv2.FaceRecognizerSF.create(str(reconhecedor), ''),
            )
        except cv2.error as exc:
            raise FacialIndisponivel('Não foi possível carregar os modelos de reconhecimento facial.') from exc
    return _motor


def extrair_vetor(arquivo):
    if arquivo is None or not arquivo.size or arquivo.size > FOTO_MAX_BYTES:
        raise ErroFacial('Capture uma imagem de até 1 MB pela câmera.')
    try:
        imagem = Image.open(BytesIO(arquivo.read(FOTO_MAX_BYTES + 1)))
        if imagem.format not in ('JPEG', 'PNG') or imagem.width * imagem.height > FOTO_MAX_PIXELS:
            raise ErroFacial('Capture uma imagem JPEG ou PNG de até 1280 × 1280 pixels.')
        imagem.load()
        imagem = imagem.convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ErroFacial('Não foi possível ler a imagem. Capture novamente.') from exc
    with _lock:
        detector, reconhecedor = _motor_local()
        import cv2
        import numpy as np

        quadro = cv2.cvtColor(np.array(imagem), cv2.COLOR_RGB2BGR)
        detector.setInputSize((imagem.width, imagem.height))
        try:
            _, rostos = detector.detect(quadro)
            if rostos is None or len(rostos) == 0:
                raise SemRosto('Aguardando rosto. Posicione-se diante da câmera.')
            if len(rostos) != 1:
                raise ErroFacial('Enquadre apenas um rosto, com boa iluminação, e tente novamente.')
            if min(rostos[0][2:4]) < 80:
                raise ErroFacial('Aproxime o rosto da câmera e tente novamente.')
            alinhada = reconhecedor.alignCrop(quadro, rostos[0])
            vetor = reconhecedor.feature(alinhada).flatten()
            norma = np.linalg.norm(vetor)
            if not np.isfinite(vetor).all() or norma == 0:
                raise ErroFacial('Não foi possível reconhecer o rosto. Capture novamente.')
            return (vetor / norma).tolist()
        except cv2.error as exc:
            raise ErroFacial('Não foi possível processar o rosto. Capture novamente.') from exc


def identificar(vetor, cadastros):
    """Rejeita rosto desconhecido ou próximo demais de duas pessoas cadastradas."""
    resultados = sorted(
        ((sum(a * b for a, b in zip(vetor, cadastro.vetor, strict=True)), cadastro) for cadastro in cadastros),
        key=lambda item: item[0], reverse=True,
    )
    if not resultados or resultados[0][0] < FACIAL_LIMIAR:
        raise ErroFacial('Rosto não reconhecido. Tente novamente ou use o registro comum.')
    if len(resultados) > 1 and resultados[0][0] - resultados[1][0] < FACIAL_MARGEM:
        raise ErroFacial('Identificação inconclusiva. Use o registro comum e peça a revisão do cadastro facial.')
    return resultados[0][1].funcionario
