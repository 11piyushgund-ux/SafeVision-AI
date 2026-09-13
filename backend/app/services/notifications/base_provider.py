"""
SafeVision AI — Notification Provider Base Interface (Phase 15)

Defines the minimal contract that every notification provider must implement.
Concrete providers (EmailProvider, WhatsAppProvider) inherit from this class.

Contract:
  send() → dict  on success
  send() → raises ProviderError  on failure

The returned dict is stored verbatim as Notification.provider_response.
It MUST NOT contain secrets (passwords, auth tokens, API keys).
Only safe metadata such as message IDs, status strings, and sanitized
error categories should be included.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """
    Raised by any notification provider when delivery fails.

    Carries a safe, loggable reason (never credentials or PII).
    """

    def __init__(self, reason: str, *, provider: str = "unknown") -> None:
        self.reason = reason
        self.provider = provider
        super().__init__(f"[{provider}] {reason}")


class BaseNotificationProvider(ABC):
    """
    Abstract base class for SafeVision notification providers.

    Subclasses implement send() using their respective delivery mechanism.
    The provider is stateless — credentials are read from Settings at
    construction time, never stored as raw strings beyond __init__.
    """

    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: str | None,
        body: str,
        attachment_bytes: bytes | None = None,
        attachment_filename: str | None = None,
    ) -> dict:
        """
        Deliver a notification to recipient.

        Args:
            recipient:           Delivery address — email address or phone number in
                                 E.164 / WhatsApp format (e.g. "whatsapp:+91XXXXXXXXXX").
            subject:             Optional subject line (used by email, ignored by WhatsApp).
            body:                Message body (plain text).
            attachment_bytes:    Optional file bytes to attach (e.g. evidence JPEG).
            attachment_filename: Optional filename for the attachment (e.g. "evidence.jpg").

        Returns:
            A dict of safe provider metadata to store in Notification.provider_response.
            MUST NOT contain credentials, auth tokens, or passwords.

        Raises:
            ProviderError: On any delivery failure (network error, auth error,
                           config missing, etc.). Never raises other exceptions.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier for logging."""
