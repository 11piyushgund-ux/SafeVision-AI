"""
SafeVision AI — Notification Providers Package (Phase 15)

Exports the provider abstraction and both concrete implementations.
"""

from app.services.notifications.base_provider import BaseNotificationProvider, ProviderError
from app.services.notifications.email_provider import EmailProvider
from app.services.notifications.whatsapp_provider import WhatsAppProvider

__all__ = [
    "BaseNotificationProvider",
    "ProviderError",
    "EmailProvider",
    "WhatsAppProvider",
]
