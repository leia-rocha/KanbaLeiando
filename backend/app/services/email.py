"""Envio de e-mails por SMTP e geracao de links de acao Firebase (RF03-RF05).

Nao envia senhas prontas nem armazena senhas/codigos em texto. Links de acao sao
gerados com o Admin SDK no momento do envio. Falhas sao registradas com estado
visivel ao administrador. Nenhum e-mail e enviado a pessoas reais sem SMTP
configurado.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.clients import get_auth_client
from app.config import get_settings


class EmailNotConfigured(Exception):
    pass


def _action_code_settings():
    from firebase_admin import auth as fb_auth

    settings = get_settings()
    return fb_auth.ActionCodeSettings(
        url=f"{settings.app_base_url.rstrip('/')}/auth/action",
        handle_code_in_app=False,
    )


def generate_password_reset_link(email: str) -> str:
    auth = get_auth_client()
    return auth.generate_password_reset_link(email, _action_code_settings())


def _send_smtp(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailNotConfigured("SMTP nao configurado.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    if settings.smtp_use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls(context=context)
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)


def send_welcome_email(name: str, email: str) -> None:
    """Boas-vindas com link de definicao da primeira senha."""
    link = generate_password_reset_link(email)
    subject = "Bem-vindo(a) ao KanbaLeiando"
    text = (
        f"Ola, {name}.\n\n"
        "Sua conta no KanbaLeiando foi criada. Defina sua primeira senha pelo link abaixo:\n"
        f"{link}\n\n"
        "Se voce nao reconhece este registro, ignore este e-mail."
    )
    html = (
        f"<p>Ola, {name}.</p>"
        "<p>Sua conta no <strong>KanbaLeiando</strong> foi criada. "
        "Defina sua primeira senha pelo botao abaixo:</p>"
        f'<p><a href="{link}">Definir minha senha</a></p>'
        "<p>Se voce nao reconhece este registro, ignore este e-mail.</p>"
    )
    _send_smtp(email, subject, html, text)


def send_password_reset_email(name: str, email: str) -> None:
    link = generate_password_reset_link(email)
    subject = "Redefinicao de senha - KanbaLeiando"
    text = (
        f"Ola, {name}.\n\n"
        "Recebemos uma solicitacao para redefinir sua senha. Use o link abaixo:\n"
        f"{link}\n\n"
        "Se nao foi voce, ignore este e-mail."
    )
    html = (
        f"<p>Ola, {name}.</p>"
        "<p>Recebemos uma solicitacao para redefinir sua senha no "
        "<strong>KanbaLeiando</strong>.</p>"
        f'<p><a href="{link}">Redefinir minha senha</a></p>'
        "<p>Se nao foi voce, ignore este e-mail.</p>"
    )
    _send_smtp(email, subject, html, text)
