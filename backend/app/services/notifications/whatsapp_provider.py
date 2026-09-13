"""
SafeVision AI — WhatsApp Notification Provider (Phase 15)

Implements BaseNotificationProvider using the Twilio REST API.

Credentials are read exclusively from app.config.Settings, which loads
them from environment variables (.env file).  NO credentials are ever
hardcoded in this file.

Required configuration (via .env / environment):
  TWILIO_ACCOUNT_SID    — Twilio Account SID
  TWILIO_AUTH_TOKEN     — Twilio Auth Token  (NEVER logged or returned)
  TWILIO_WHATSAPP_FROM  — Twilio sender in format "whatsapp:+14155238886"

Recipient:
  Provided per-notification as the recipient argument in E.164 format,
  prefixed with "whatsapp:" (e.g. "whatsapp:+919876543210").
  This is stored in OrgNotificationSettings.notification_recipient — NOT in .env.

Twilio sandbox:
  For testing, use the Twilio WhatsApp Sandbox.
  TWILIO_WHATSAPP_FROM=whatsapp:+14155238886 (sandbox number).
  The recipient must join the sandbox by sending a join code first.
"""

from __future__ import annotations

import re
import structlog

from app.config import get_settings
from app.services.notifications.base_provider import BaseNotificationProvider, ProviderError

log = structlog.get_logger()


class WhatsAppProvider(BaseNotificationProvider):
    """
    Twilio WhatsApp notification provider.

    Reads all credentials from Settings (loaded from .env).
    The recipient address comes from OrgNotificationSettings — never from env.
    Raises ProviderError when configuration is missing or delivery fails.
    Never exposes auth tokens in exceptions, logs, or return values.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._account_sid: str | None = settings.twilio_account_sid
        # Store token reference but never expose it in repr/logs
        self._auth_token: str | None = settings.twilio_auth_token
        self._from_number: str | None = settings.twilio_whatsapp_from
        # Optional Content Template SID (HX...) — required when the Twilio account
        # enforces Content Templates (error 21654 if omitted on those accounts).
        self._content_sid: str | None = settings.twilio_content_sid

    @property
    def provider_name(self) -> str:
        return "whatsapp_twilio"

    def _check_config(self) -> None:
        """Validate that required Twilio credentials are present."""
        missing: list[str] = []
        if not self._account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not self._auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not self._from_number:
            missing.append("TWILIO_WHATSAPP_FROM")
        if missing:
            raise ProviderError(
                f"Twilio not configured — missing: {', '.join(missing)}",
                provider=self.provider_name,
            )

    @staticmethod
    def _normalize_recipient(recipient: str) -> str:
        """
        Normalize recipient phone number to Twilio WhatsApp E.164 format.

        Requirements:
        1. Strip leading/trailing whitespace.
        2. Remove existing leading 'whatsapp:' prefix safely.
        3. Remove internal formatting characters: spaces, dashes, dots, parentheses.
        4. Normalize Indian numbers safely:
           - If already starts with '+': preserve the '+' and digits.
           - If exactly 10 digits: prepend '+91'.
           - If exactly 12 digits and starts with '91': prepend '+'.
           - Else: if starts with digits, prepend '+'.
        5. Return 'whatsapp:+<E164_NUMBER>'.
        """
        cleaned = recipient.strip()
        if cleaned.lower().startswith("whatsapp:"):
            cleaned = cleaned[len("whatsapp:"):].strip()

        # Remove spaces, dashes, dots, parentheses
        has_plus = cleaned.startswith("+")
        cleaned_digits = re.sub(r"[\s\-\(\)\.]", "", cleaned)

        if has_plus:
            # Already starts with '+'
            # Ensure only '+' followed by digits
            num_part = re.sub(r"[^\d]", "", cleaned_digits[1:])
            e164 = f"+{num_part}"
        else:
            digits_only = re.sub(r"[^\d]", "", cleaned_digits)
            if len(digits_only) == 10:
                e164 = f"+91{digits_only}"
            elif len(digits_only) == 12 and digits_only.startswith("91"):
                e164 = f"+{digits_only}"
            else:
                e164 = f"+{digits_only}"

        return f"whatsapp:{e164}"

    def send(
        self,
        recipient: str,
        subject: str | None,  # noqa: ARG002 — WhatsApp has no subject line
        body: str,
        attachment_bytes: bytes | None = None,
        attachment_filename: str | None = None,
    ) -> dict:
        """
        Send a WhatsApp message via Twilio.

        recipient must be a phone number in E.164 format
        (with or without the 'whatsapp:' prefix).

        Returns safe provider metadata dict (no auth tokens).
        Raises ProviderError on configuration error or delivery failure.
        """
        self._check_config()

        # Import here so twilio is optional at module load time
        # (tests can mock before this import runs)
        try:
            from twilio.rest import Client as TwilioClient  # type: ignore[import]
            from twilio.base.exceptions import TwilioRestException  # type: ignore[import]
        except ImportError as exc:
            raise ProviderError(
                "twilio package is not installed — run: pip install twilio",
                provider=self.provider_name,
            ) from exc

        normalized_recipient = self._normalize_recipient(recipient)

        try:
            client = TwilioClient(self._account_sid, self._auth_token)

            if self._content_sid:
                # Account requires Content Templates — send via content_sid, no body=.
                message = client.messages.create(
                    content_sid=self._content_sid,
                    from_=self._from_number,
                    to=normalized_recipient,
                )
            else:
                # Account allows freeform messages — send plain body.
                message = client.messages.create(
                    body=body,
                    from_=self._from_number,
                    to=normalized_recipient,
                )

            log.info(
                "whatsapp_notification_sent",
                message_sid=message.sid,
                provider=self.provider_name,
                status=message.status,
            )
            return {
                "provider": self.provider_name,
                "message_sid": message.sid,
                "status": message.status,
                "error_code": None,
            }

        except TwilioRestException as exc:
            log.warning(
                "whatsapp_send_failed",
                provider=self.provider_name,
                twilio_code=exc.code,
                twilio_status=exc.status,
                # Log only the code/status — not the full message which may contain tokens
            )
            raise ProviderError(
                f"Twilio API error (code={exc.code}, status={exc.status})",
                provider=self.provider_name,
            ) from None

        except Exception as exc:
            log.warning(
                "whatsapp_unexpected_error",
                provider=self.provider_name,
                error_type=type(exc).__name__,
                error=str(exc)[:100],
            )
            raise ProviderError(
                f"WhatsApp delivery failed: {type(exc).__name__}",
                provider=self.provider_name,
            ) from None
