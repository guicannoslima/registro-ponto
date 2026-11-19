"""SMTP configurável pelo administrador, com credencial cifrada no banco."""

from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.smtp import EmailBackend

from .models import ConfiguracaoEmail


def _cifra():
    chave = sha256(('registro-ponto-email:' + settings.SECRET_KEY).encode()).digest()
    return Fernet(urlsafe_b64encode(chave))


def cifrar_senha(senha):
    return _cifra().encrypt(senha.encode()).decode() if senha else ''


def decifrar_senha(valor):
    try:
        return _cifra().decrypt(valor.encode()).decode() if valor else ''
    except InvalidToken as exc:
        raise ImproperlyConfigured('Salve novamente a senha SMTP após a troca da chave do sistema.') from exc


class BackendEmail(EmailBackend):
    def __init__(self, **kwargs):
        configuracao = ConfiguracaoEmail.objects.filter(pk=1).first()
        self.remetente = configuracao.remetente if configuracao else settings.DEFAULT_FROM_EMAIL
        if configuracao:
            parametros = {
                'host': configuracao.servidor,
                'port': configuracao.porta,
                'username': configuracao.usuario,
                'password': decifrar_senha(configuracao.senha_criptografada),
                'use_tls': configuracao.seguranca == 'tls',
                'use_ssl': configuracao.seguranca == 'ssl',
            }
            parametros.update(kwargs)
            kwargs = parametros
        kwargs.setdefault('timeout', 15)
        super().__init__(**kwargs)

    def send_messages(self, email_messages):
        for mensagem in email_messages or []:
            if mensagem.from_email == settings.DEFAULT_FROM_EMAIL:
                mensagem.from_email = self.remetente
        return super().send_messages(email_messages)
