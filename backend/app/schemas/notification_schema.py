"""
SafeVision AI — Notification Pydantic Schemas (Phase 15)

Request/response contracts for the Notifications API.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# Notification Record Schemas
# ==============================================================================

class NotificationResponse(BaseModel):
    """Single notification record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    event_id: str | None = None
    org_id: str
    recipient_user_id: str | None = None
    recipient_address: str | None = None
    channel: str
    status: str
    subject: str | None = None
    body: str | None = None
    # provider_response is exposed but credentials are already stripped at write-time
    provider_response: dict | None = None
    retry_count: int
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated notification list."""

    data: list[NotificationResponse]
    total: int
    page: int
    size: int


# ==============================================================================
# Organization Notification Settings Schemas
# ==============================================================================

class OrgNotificationSettingsResponse(BaseModel):
    """Organization notification settings response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    notifications_enabled: bool
    notification_mode: str
    email_recipient: str | None = None
    whatsapp_recipient: str | None = None
    # Recipient address is returned so the frontend/legacy callers can display it
    # but the API never returns passwords or provider secrets
    notification_recipient: str | None = None
    created_at: datetime
    updated_at: datetime


class OrgNotificationSettingsUpdate(BaseModel):
    """Request body for updating organization notification settings."""

    notifications_enabled: bool = Field(
        ..., description="Whether notifications are enabled for this org",
    )
    notification_mode: Literal["email", "whatsapp"] = Field(
        ..., description="Active notification channel: 'email' or 'whatsapp'",
    )
    email_recipient: str | None = Field(
        default=None,
        description="Recipient email address for safety alerts (e.g. user@example.com)",
    )
    whatsapp_recipient: str | None = Field(
        default=None,
        description=(
            "Recipient phone number for WhatsApp alerts in E.164 format "
            "(e.g. +919876543210)"
        ),
    )
    notification_recipient: str | None = Field(
        default=None,
        description="Legacy recipient field (auto-synced if omitted)",
    )

    @field_validator("email_recipient")
    @classmethod
    def validate_email_recipient(cls, v: str | None) -> str | None:
        if v is not None:
            clean = v.strip()
            if clean:
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean):
                    raise ValueError("Invalid email format")
                return clean
        return None

    @field_validator("whatsapp_recipient")
    @classmethod
    def validate_whatsapp_recipient(cls, v: str | None) -> str | None:
        if v is not None:
            clean = v.strip()
            if clean:
                digits = re.sub(r"[^\d]", "", clean)
                if len(digits) < 10:
                    raise ValueError("WhatsApp phone number must contain at least 10 digits")
                return clean
        return None

    @model_validator(mode="after")
    def validate_active_channel_recipient(self) -> "OrgNotificationSettingsUpdate":
        if self.notifications_enabled:
            if self.notification_mode == "email":
                target = self.email_recipient or (
                    self.notification_recipient.strip()
                    if self.notification_recipient and "@" in self.notification_recipient
                    else None
                )
                if not target:
                    raise ValueError("Email recipient is required when Email notification mode is enabled")
            elif self.notification_mode == "whatsapp":
                target = self.whatsapp_recipient or (
                    self.notification_recipient.strip()
                    if self.notification_recipient and "@" not in self.notification_recipient
                    else None
                )
                if not target:
                    raise ValueError("WhatsApp recipient is required when WhatsApp notification mode is enabled")
        return self
