"""
SafeVision AI — Email Notification Provider (Phase 15)

Implements BaseNotificationProvider using Python smtplib.

Credentials are read exclusively from app.config.Settings, which loads
them from environment variables (.env file).  NO credentials are ever
hardcoded in this file.

Supported configuration (via .env / environment):
  SMTP_HOST          — SMTP server hostname  (e.g. smtp.gmail.com)
  SMTP_PORT          — SMTP port             (default 587)
  SMTP_USER          — SMTP login username   (e.g. alerts@example.com)
  SMTP_PASSWORD      — SMTP login password   (app password for Gmail)
  SMTP_FROM_EMAIL    — From address          (defaults to SMTP_USER)

Gmail setup:
  Use an App Password (Google Account → Security → 2-Step Verification → App passwords).
  SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_USER=<gmail>, SMTP_PASSWORD=<app_password>
"""

from __future__ import annotations

import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.config import get_settings
from app.services.notifications.base_provider import BaseNotificationProvider, ProviderError

log = structlog.get_logger()


class EmailProvider(BaseNotificationProvider):
    """
    SMTP-based email notification provider.

    Reads all credentials from Settings (loaded from .env).
    Raises ProviderError when configuration is missing or delivery fails.
    Never exposes credentials in exceptions, logs, or return values.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._host: str | None = settings.smtp_host
        self._port: int = settings.smtp_port
        self._user: str | None = settings.smtp_user
        # Store password reference but never expose it in repr/logs
        self._password: str | None = settings.smtp_password
        self._from_email: str = settings.smtp_from_email or settings.smtp_user or ""

    @property
    def provider_name(self) -> str:
        return "email_smtp"

    def _check_config(self) -> None:
        """Validate that required SMTP credentials are present."""
        missing: list[str] = []
        if not self._host:
            missing.append("SMTP_HOST")
        if not self._user:
            missing.append("SMTP_USER")
        if not self._password:
            missing.append("SMTP_PASSWORD")
        if missing:
            raise ProviderError(
                f"SMTP not configured — missing: {', '.join(missing)}",
                provider=self.provider_name,
            )

    def send(
        self,
        recipient: str,
        subject: str | None,
        body: str,
        attachment_bytes: bytes | None = None,
        attachment_filename: str | None = None,
    ) -> dict:
        """
        Send an email via SMTP TLS with optional evidence image attachment.

        Returns safe provider metadata dict (no credentials).
        Raises ProviderError on configuration error or delivery failure.
        """
        self._check_config()

        msg = MIMEMultipart("mixed" if attachment_bytes else "alternative")
        msg["Subject"] = subject or "SafeVision AI — Safety Alert"
        msg["From"] = self._from_email
        msg["To"] = recipient
        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_bytes:
            filename = attachment_filename or "evidence.jpg"
            try:
                img_part = MIMEImage(attachment_bytes, name=filename)
            except Exception:
                img_part = MIMEImage(attachment_bytes, _subtype="jpeg", name=filename)
            img_part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(img_part)

        try:
            with smtplib.SMTP(self._host, self._port, timeout=30) as server:  # type: ignore[arg-type]
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._user, self._password)  # type: ignore[arg-type]
                server.sendmail(self._from_email, recipient, msg.as_string())

            log.info(
                "email_notification_sent",
                recipient_domain=recipient.split("@")[-1] if "@" in recipient else "unknown",
                subject=subject,
                provider=self.provider_name,
                has_attachment=bool(attachment_bytes),
            )
            return {
                "provider": self.provider_name,
                "status": "sent",
                "smtp_host": self._host,
                "recipient_domain": recipient.split("@")[-1] if "@" in recipient else "unknown",
                "has_attachment": bool(attachment_bytes),
            }

        except smtplib.SMTPAuthenticationError as exc:
            log.warning(
                "email_auth_failed",
                provider=self.provider_name,
                smtp_host=self._host,
                error_code=exc.smtp_code,
            )
            raise ProviderError(
                f"SMTP authentication failed (code {exc.smtp_code}) — check SMTP_USER/SMTP_PASSWORD",
                provider=self.provider_name,
            ) from None

        except smtplib.SMTPRecipientsRefused as exc:
            log.warning(
                "email_recipient_refused",
                provider=self.provider_name,
                error=str(exc)[:100],
            )
            raise ProviderError(
                "SMTP recipient refused — check recipient address format",
                provider=self.provider_name,
            ) from None

        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            log.warning(
                "email_send_failed",
                provider=self.provider_name,
                error_type=type(exc).__name__,
                error=str(exc)[:100],
            )
            raise ProviderError(
                f"SMTP delivery failed: {type(exc).__name__}",
                provider=self.provider_name,
            ) from None
