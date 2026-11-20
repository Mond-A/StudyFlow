"""Email delivery for account verification.

Console delivery is a development backend: it records the message in a local
in-memory outbox but never logs the verification URL or token. It must not be
presented as a real SMTP delivery. The SMTP backend uses only environment-backed
configuration.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


class MailDeliveryError(RuntimeError):
    """Raised when a configured mail backend cannot deliver the message."""


def _outbox() -> list[dict]:
    return current_app.extensions.setdefault("studyflow_mail_outbox", [])


def verification_url(token: str) -> str:
    base = current_app.config["PUBLIC_BASE_URL"]
    return f"{base}/verify-email?token={token}"


def send_verification_email(recipient: str, token: str) -> str:
    """Send/record a verification message and return the verification URL."""
    url = verification_url(token)
    backend = current_app.config["MAIL_BACKEND"].strip().lower()
    message = EmailMessage()
    message["Subject"] = "验证你的 StudyFlow 邮箱"
    message["From"] = current_app.config["MAIL_FROM"]
    message["To"] = recipient
    message.set_content(
        "你好：\n\n"
        "请打开下面的链接完成 StudyFlow 邮箱验证：\n"
        f"{url}\n\n"
        "如果这不是你的操作，可以忽略这封邮件。\n"
    )

    if backend == "console":
        # Console is development-only. Production must use SMTP; otherwise
        # fail closed without writing the URL to an outbox or application log.
        environment = os.getenv("FLASK_ENV", "production").strip().lower()
        if environment == "production" and not current_app.config.get("TESTING"):
            raise MailDeliveryError(
                "Console mail backend is disabled in production; configure MAIL_BACKEND=smtp"
            )
        _outbox().append({"recipient": recipient, "verification_url": url})
        current_app.logger.warning(
            "DEV verification email queued for %s; URL omitted from logs",
            recipient,
        )
        return url

    if backend != "smtp":
        raise MailDeliveryError(f"Unsupported MAIL_BACKEND: {backend}")
    host = current_app.config["SMTP_HOST"]
    if not host:
        raise MailDeliveryError("SMTP_HOST is not configured")
    try:
        context = ssl.create_default_context()
        if current_app.config["SMTP_USE_SSL"]:
            with smtplib.SMTP_SSL(
                host,
                current_app.config["SMTP_PORT"],
                timeout=20,
                context=context,
            ) as client:
                if current_app.config["SMTP_USERNAME"]:
                    client.login(
                        current_app.config["SMTP_USERNAME"],
                        current_app.config["SMTP_PASSWORD"],
                    )
                client.send_message(message)
        else:
            with smtplib.SMTP(host, current_app.config["SMTP_PORT"], timeout=20) as client:
                if current_app.config["SMTP_USE_TLS"]:
                    client.starttls(context=context)
                if current_app.config["SMTP_USERNAME"]:
                    client.login(
                        current_app.config["SMTP_USERNAME"],
                        current_app.config["SMTP_PASSWORD"],
                    )
                client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailDeliveryError("SMTP delivery failed") from exc
    return url
