"""Exceções de domínio do Registro de Ponto."""


class ErroBatida(Exception):
    """A sequência ou o intervalo das batidas impede o registro."""


class ErroFacial(Exception):
    """A captura ou a comparação facial não permite identificar uma pessoa."""


class FacialIndisponivel(ErroFacial):
    """O servidor não tem o motor facial pronto para uso."""


class CadastroFacialAusente(ErroFacial):
    """Não há cadastro facial disponível para o registro solicitado."""


class SemRosto(ErroFacial):
    """Nenhum rosto foi encontrado no enquadramento da câmera."""
