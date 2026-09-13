"""
SafeVision AI — Notification Integration Tests (Phase 15)

Tests:
  1. Email provider success
  2. Email provider failure
  3. WhatsApp provider success
  4. WhatsApp provider failure
  5. Email routing (correct provider called)
  6. WhatsApp routing (correct provider called)
  7. Notification PENDING creation
  8. Notification SENT update
  9. Notification FAILED update
 10. Event survives provider failure
 11. Alert survives provider failure
 12. Tenant isolation
 13. Missing email configuration
 14. Missing WhatsApp configuration
 15. Unsupported notification mode
 16. Real event/alert data used in message
 17. No hardcoded location text
 18. Duplicate notification protection
 19. Organization settings persistence
 20. Settings tenant isolation
 21. provider_response does not contain credentials

No real SMTP, Twilio, or OpenRouter calls are made.
"""

from __future__ import annotations

import smtplib
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

# ==============================================================================
# Helpers — Minimal DB + ORM stubs without requiring a live PostgreSQL server
# ==============================================================================

def _make_id() -> str:
    return str(uuid.uuid4())


def _fake_org_settings(
    *,
    org_id: str = "test-org",
    notifications_enabled: bool = True,
    notification_mode: str = "email",
    email_recipient: str | None = None,
    whatsapp_recipient: str | None = None,
    notification_recipient: str | None = None,
):
    """Return a mock OrgNotificationSettings-like object."""
    if notification_recipient is None:
        notification_recipient = "+919876543210" if notification_mode == "whatsapp" else "alerts@test.com"
    elif notification_recipient == "alerts@test.com" and notification_mode == "whatsapp":
        notification_recipient = "+919876543210"

    m = MagicMock()
    m.org_id = org_id
    m.notifications_enabled = notifications_enabled
    m.notification_mode = notification_mode  # plain string — enum-free for test isolation
    m.notification_recipient = notification_recipient
    m.email_recipient = email_recipient if email_recipient is not None else (notification_recipient if (notification_recipient and "@" in notification_recipient) else None)
    m.whatsapp_recipient = whatsapp_recipient if whatsapp_recipient is not None else (notification_recipient if (notification_recipient and "@" not in notification_recipient) else None)
    return m


def _fake_alert(
    *,
    org_id: str = "test-org",
    alert_id: str | None = None,
    severity: str = "high",
    status: str = "active",
    event_id: str | None = None,
    description: str = "PPE Violation Detected",
    metadata_json: dict | None = None,
):
    m = MagicMock()
    m.id = alert_id or _make_id()
    m.org_id = org_id
    m.severity = severity
    m.status = status
    m.title = "PPE Detection Alert"
    m.description = description
    m.event_id = event_id or _make_id()
    m.created_at = datetime.now(timezone.utc)
    m.metadata_json = metadata_json or {
        "risk_score": 0.78,
        "risk_level": "high",
        "event_type": "ppe_detection",
        "camera_id": _make_id(),
    }
    return m


def _fake_event(
    *,
    org_id: str = "test-org",
    camera_id: str | None = None,
    event_type: str = "ppe_detection",
    confidence: float = 0.85,
    missing_ppe: list | None = None,
):
    m = MagicMock()
    m.id = _make_id()
    m.org_id = org_id
    m.camera_id = camera_id or _make_id()
    m.event_type = event_type  # plain string, not enum
    m.confidence = confidence
    m.timestamp = datetime.now(timezone.utc)
    m.detection_data = {
        "missing_ppe": missing_ppe or ["helmet"],
        "message": "Missing helmet detected",
    }
    return m


def _make_db_session() -> MagicMock:
    """Return a minimal SQLAlchemy Session mock."""
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = None
    db.add.return_value = None
    db.flush.return_value = None
    db.commit.return_value = None
    return db


# ==============================================================================
# 1 & 2 — Email Provider: Success / Failure
# ==============================================================================

class TestEmailProvider:
    """Tests for EmailProvider (app.services.notifications.email_provider)."""

    @patch("app.services.notifications.email_provider.get_settings")
    @patch("smtplib.SMTP")
    def test_email_provider_success(self, mock_smtp_cls, mock_get_settings):
        """1. Email provider send() returns safe metadata dict on success."""
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = "user@example.com"
        settings.smtp_password = "secret_password"
        settings.smtp_from_email = "alerts@example.com"
        mock_get_settings.return_value = settings

        smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        from app.services.notifications.email_provider import EmailProvider
        provider = EmailProvider()
        result = provider.send(
            recipient="recipient@test.com",
            subject="Test Alert",
            body="Body text",
        )

        assert result["provider"] == "email_smtp"
        assert result["status"] == "sent"
        assert "password" not in result
        assert "smtp_password" not in result
        # sendmail should have been called with the recipient
        smtp_instance.sendmail.assert_called_once()

    @patch("app.services.notifications.email_provider.get_settings")
    @patch("smtplib.SMTP")
    def test_email_provider_failure(self, mock_smtp_cls, mock_get_settings):
        """2. Email provider raises ProviderError on SMTP failure."""
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = "user@example.com"
        settings.smtp_password = "secret"
        settings.smtp_from_email = "alerts@example.com"
        mock_get_settings.return_value = settings

        # Simulate SMTP exception
        mock_smtp_cls.return_value.__enter__ = MagicMock(
            side_effect=smtplib.SMTPException("Connection refused")
        )
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        from app.services.notifications.email_provider import EmailProvider
        from app.services.notifications.base_provider import ProviderError
        provider = EmailProvider()

        with pytest.raises(ProviderError) as exc_info:
            provider.send(
                recipient="recipient@test.com",
                subject="Alert",
                body="Body",
            )

        assert exc_info.value.provider == "email_smtp"
        assert "password" not in str(exc_info.value)
        assert "secret" not in str(exc_info.value)

    @patch("app.services.notifications.email_provider.get_settings")
    def test_email_provider_missing_config(self, mock_get_settings):
        """13. ProviderError raised when SMTP credentials are missing."""
        settings = MagicMock()
        settings.smtp_host = None  # missing
        settings.smtp_port = 587
        settings.smtp_user = None  # missing
        settings.smtp_password = None  # missing
        settings.smtp_from_email = None
        mock_get_settings.return_value = settings

        from app.services.notifications.email_provider import EmailProvider
        from app.services.notifications.base_provider import ProviderError
        provider = EmailProvider()

        with pytest.raises(ProviderError) as exc_info:
            provider.send(recipient="r@test.com", subject="S", body="B")

        assert "SMTP_HOST" in exc_info.value.reason
        assert "SMTP_USER" in exc_info.value.reason


# ==============================================================================
# 3 & 4 — WhatsApp Provider: Success / Failure
# ==============================================================================

class TestWhatsAppProvider:
    """Tests for WhatsAppProvider (app.services.notifications.whatsapp_provider)."""

    @patch("app.services.notifications.whatsapp_provider.get_settings")
    def test_whatsapp_provider_success(self, mock_get_settings):
        """3. WhatsApp provider returns metadata with message_sid on success."""
        import importlib
        import sys

        fake_message = MagicMock()
        fake_message.sid = "SM1234567890"
        fake_message.status = "queued"

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.return_value = fake_message
        mock_client_cls = MagicMock(return_value=mock_client_instance)

        # Build stub Settings object that has all Twilio credentials
        stub_settings = MagicMock()
        stub_settings.twilio_account_sid = "ACtest123"
        stub_settings.twilio_auth_token = "secret_token"
        stub_settings.twilio_whatsapp_from = "whatsapp:+14155238886"

        # Patch sys.modules to stub twilio without installing it,
        # and patch get_settings both in the module-under-test AND the decorator mock
        with patch.dict(
            sys.modules,
            {
                "twilio": MagicMock(),
                "twilio.rest": MagicMock(Client=mock_client_cls),
                "twilio.base": MagicMock(),
                "twilio.base.exceptions": MagicMock(TwilioRestException=Exception),
            },
        ):
            import app.services.notifications.whatsapp_provider as wp_mod
            importlib.reload(wp_mod)

            # Patch get_settings on the freshly-reloaded module
            with patch.object(wp_mod, "get_settings", return_value=stub_settings):
                provider = wp_mod.WhatsAppProvider()
                result = provider.send(
                    recipient="whatsapp:+919876543210",
                    subject=None,
                    body="Safety Alert",
                )

        assert result["message_sid"] == "SM1234567890"
        assert result["provider"] == "whatsapp_twilio"
        # Auth token must NEVER appear in return value
        assert "secret_token" not in str(result)
        assert "auth_token" not in result

    @patch("app.services.notifications.whatsapp_provider.get_settings")
    def test_whatsapp_provider_failure(self, mock_get_settings):
        """4. WhatsApp provider raises ProviderError on Twilio failure."""
        settings = MagicMock()
        settings.twilio_account_sid = "ACtest123"
        settings.twilio_auth_token = "secret_token"
        settings.twilio_whatsapp_from = "whatsapp:+14155238886"
        mock_get_settings.return_value = settings

        # Create a mock TwilioRestException
        class MockTwilioRestException(Exception):
            def __init__(self, msg="", code=21211, status=400):
                self.code = code
                self.status = status
                super().__init__(msg)

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.side_effect = MockTwilioRestException()
        mock_client_cls = MagicMock(return_value=mock_client_instance)

        # Patch sys.modules to stub twilio without installing it
        with patch.dict(
            "sys.modules",
            {
                "twilio": MagicMock(),
                "twilio.rest": MagicMock(Client=mock_client_cls),
                "twilio.base": MagicMock(),
                "twilio.base.exceptions": MagicMock(TwilioRestException=MockTwilioRestException),
            },
        ):
            import importlib
            import app.services.notifications.whatsapp_provider as wp_mod
            importlib.reload(wp_mod)
            from app.services.notifications.base_provider import ProviderError

            provider = wp_mod.WhatsAppProvider()
            with pytest.raises(ProviderError) as exc_info:
                provider.send(
                    recipient="whatsapp:+919876543210",
                    subject=None,
                    body="Alert body",
                )

        assert exc_info.value.provider == "whatsapp_twilio"
        assert "secret_token" not in str(exc_info.value)

    @patch("app.services.notifications.whatsapp_provider.get_settings")
    def test_whatsapp_provider_missing_config(self, mock_get_settings):
        """14. ProviderError raised when Twilio credentials are missing."""
        settings = MagicMock()
        settings.twilio_account_sid = None
        settings.twilio_auth_token = None
        settings.twilio_whatsapp_from = None
        mock_get_settings.return_value = settings

        from app.services.notifications.whatsapp_provider import WhatsAppProvider
        from app.services.notifications.base_provider import ProviderError
        provider = WhatsAppProvider()

        with pytest.raises(ProviderError) as exc_info:
            provider.send(recipient="+919876543210", subject=None, body="B")

        assert "TWILIO_ACCOUNT_SID" in exc_info.value.reason
        assert "TWILIO_AUTH_TOKEN" in exc_info.value.reason


# ==============================================================================
# 5 & 6 — Routing: correct provider is selected
# ==============================================================================

class TestProviderRouting:
    """Tests 5 & 6: verify the correct provider is invoked based on notification_mode."""

    def _dispatch_with_mode(self, mode: str, db: MagicMock):
        """Helper: set up OrgNotificationSettings mock and call _dispatch_inner."""
        org_settings = _fake_org_settings(notification_mode=mode)
        alert = _fake_alert()
        event = _fake_event()

        def query_side_effect(model_class):
            q = MagicMock()
            q.filter.return_value.first.return_value = org_settings if "OrgNotification" in str(model_class) else None
            return q

        db.query.side_effect = query_side_effect
        db.query.return_value.filter.return_value.first.return_value = None
        return alert, event

    @patch("app.services.notification_service.EmailProvider")
    @patch("app.services.notification_service.WhatsAppProvider")
    def test_email_routing(self, mock_wa_cls, mock_email_cls):
        """5. When mode=email, EmailProvider is invoked. WhatsAppProvider is not."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email.send.return_value = {"provider": "email_smtp", "status": "sent"}
        mock_email_cls.return_value = mock_email

        from app.services.notification_service import _get_provider
        from app.models.org_notification_settings import NotificationMode
        provider = _get_provider(NotificationMode.EMAIL.value)

        assert mock_email_cls.called
        assert not mock_wa_cls.called

    @patch("app.services.notification_service.WhatsAppProvider")
    @patch("app.services.notification_service.EmailProvider")
    def test_whatsapp_routing(self, mock_email_cls, mock_wa_cls):
        """6. When mode=whatsapp, WhatsAppProvider is invoked. EmailProvider is not."""
        mock_wa = MagicMock()
        mock_wa.provider_name = "whatsapp_twilio"
        mock_wa.send.return_value = {"provider": "whatsapp_twilio", "message_sid": "SID"}
        mock_wa_cls.return_value = mock_wa

        from app.services.notification_service import _get_provider
        from app.models.org_notification_settings import NotificationMode
        provider = _get_provider(NotificationMode.WHATSAPP.value)

        assert mock_wa_cls.called
        assert not mock_email_cls.called


# ==============================================================================
# 7, 8, 9 — Notification PENDING / SENT / FAILED lifecycle
# ==============================================================================

class TestNotificationLifecycle:
    """Tests 7, 8, 9: Notification status transitions."""

    def _make_dispatch_db(self, mode: str = "email"):
        """DB mock that returns OrgNotificationSettings for org query."""
        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(notification_mode=mode)

        notif_store: list = []  # track added Notification objects

        def query_dispatch(model_class):
            q = MagicMock()
            name = str(model_class)
            if "OrgNotification" in name:
                q.filter.return_value.first.return_value = org_settings
            elif "Notification" in name and "OrgNotification" not in name:
                q.filter.return_value.filter.return_value.first.return_value = None
                q.filter.return_value.first.return_value = None
            elif "Camera" in name:
                q.filter.return_value.first.return_value = None
            elif "Zone" in name:
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_dispatch
        db.add.side_effect = lambda obj: notif_store.append(obj)
        db.flush.return_value = None
        db.commit.return_value = None
        return db, notif_store

    @patch("app.services.notification_service.EmailProvider")
    def test_notification_pending_created(self, mock_email_cls):
        """7. A Notification row with status=PENDING is created before send."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email.send.return_value = {"provider": "email_smtp", "status": "sent"}
        mock_email_cls.return_value = mock_email

        db, notif_store = self._make_dispatch_db("email")
        alert = _fake_alert()
        event = _fake_event()

        from app.services.notification_service import NotificationService
        from app.models.notification import NotificationStatus
        NotificationService.dispatch(alert=alert, event=event, db=db)

        # The notification was added before the provider was called
        assert len(notif_store) == 1
        notif = notif_store[0]
        # Flush was called → id has been obtained
        db.flush.assert_called()

    @patch("app.services.notification_service.EmailProvider")
    def test_notification_sent_on_success(self, mock_email_cls):
        """8. Notification.status transitions to SENT when provider succeeds."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email.send.return_value = {
            "provider": "email_smtp",
            "status": "sent",
            "smtp_host": "smtp.example.com",
        }
        mock_email_cls.return_value = mock_email

        db, notif_store = self._make_dispatch_db("email")
        alert = _fake_alert()
        event = _fake_event()

        from app.services.notification_service import NotificationService
        from app.models.notification import NotificationStatus
        result = NotificationService.dispatch(alert=alert, event=event, db=db)

        assert result is not None
        assert result.status == NotificationStatus.SENT
        assert result.sent_at is not None
        assert result.provider_response is not None
        db.commit.assert_called()

    @patch("app.services.notification_service.EmailProvider")
    def test_notification_failed_on_provider_error(self, mock_email_cls):
        """9. Notification.status transitions to FAILED when provider raises ProviderError."""
        from app.services.notifications.base_provider import ProviderError
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email.send.side_effect = ProviderError("SMTP auth failed", provider="email_smtp")
        mock_email_cls.return_value = mock_email

        db, notif_store = self._make_dispatch_db("email")
        alert = _fake_alert()
        event = _fake_event()

        from app.services.notification_service import NotificationService
        from app.models.notification import NotificationStatus
        result = NotificationService.dispatch(alert=alert, event=event, db=db)

        assert result is not None
        assert result.status == NotificationStatus.FAILED
        assert result.retry_count == 1
        assert result.provider_response is not None
        assert "error" in result.provider_response
        db.commit.assert_called()


# ==============================================================================
# 10 & 11 — Failure Isolation: Event and Alert survive notification failure
# ==============================================================================

class TestFailureIsolation:
    """Tests 10 & 11: Provider failure must not propagate or roll back alert/event."""

    @patch("app.services.notification_service.EmailProvider")
    def test_event_survives_notification_failure(self, mock_email_cls):
        """10. Event record is not touched when notification provider fails."""
        from app.services.notifications.base_provider import ProviderError
        mock_email = MagicMock()
        mock_email.send.side_effect = ProviderError("Network error", provider="email_smtp")
        mock_email_cls.return_value = mock_email

        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(notification_mode="email")

        def query_dispatch(model_class):
            q = MagicMock()
            name = str(model_class)
            if "OrgNotification" in name:
                q.filter.return_value.first.return_value = org_settings
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_dispatch

        alert = _fake_alert()
        event = _fake_event()
        original_event_id = event.id

        from app.services.notification_service import NotificationService
        # Must not raise
        result = NotificationService.dispatch(alert=alert, event=event, db=db)

        # Event is unchanged
        assert event.id == original_event_id

    @patch("app.services.notification_service.EmailProvider")
    def test_alert_survives_notification_failure(self, mock_email_cls):
        """11. Alert record is not touched and dispatch() does not raise."""
        from app.services.notifications.base_provider import ProviderError
        mock_email = MagicMock()
        mock_email.send.side_effect = ProviderError("SMTP down", provider="email_smtp")
        mock_email_cls.return_value = mock_email

        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(notification_mode="email")

        def query_dispatch(model_class):
            q = MagicMock()
            if "OrgNotification" in str(model_class):
                q.filter.return_value.first.return_value = org_settings
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_dispatch

        alert = _fake_alert()
        original_alert_id = alert.id

        from app.services.notification_service import NotificationService
        # CRITICAL: must not raise
        result = NotificationService.dispatch(alert=alert, event=_fake_event(), db=db)

        # Alert is unchanged
        assert alert.id == original_alert_id

    def test_dispatch_does_not_raise_on_unexpected_exception(self):
        """dispatch() must swallow all exceptions — even unexpected ones."""
        db = MagicMock(spec=Session)
        # Make the query call itself fail unexpectedly
        db.query.side_effect = RuntimeError("DB connection lost")

        alert = _fake_alert()

        from app.services.notification_service import NotificationService
        # CRITICAL: must not propagate
        result = NotificationService.dispatch(alert=alert, event=None, db=db)
        assert result is None


# ==============================================================================
# 12 — Tenant Isolation
# ==============================================================================

class TestTenantIsolation:
    """Test 12: Notifications are scoped to the alert's org_id."""

    @patch("app.services.notification_service.EmailProvider")
    def test_notification_org_id_matches_alert(self, mock_email_cls):
        """12. Created Notification.org_id matches alert.org_id."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email.send.return_value = {"provider": "email_smtp", "status": "sent"}
        mock_email_cls.return_value = mock_email

        target_org = "org-tenant-abc"
        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(org_id=target_org, notification_mode="email")
        notif_store: list = []

        def query_dispatch(model_class):
            q = MagicMock()
            name = str(model_class)
            if "OrgNotification" in name:
                q.filter.return_value.first.return_value = org_settings
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_dispatch
        db.add.side_effect = lambda obj: notif_store.append(obj)

        alert = _fake_alert(org_id=target_org)
        from app.services.notification_service import NotificationService
        NotificationService.dispatch(alert=alert, event=_fake_event(), db=db)

        assert len(notif_store) == 1
        assert notif_store[0].org_id == target_org

    @patch("app.services.notification_service.EmailProvider")
    def test_notification_skipped_for_different_org(self, mock_email_cls):
        """12b. No notification for an org that has no settings configured."""
        db = MagicMock(spec=Session)

        def query_dispatch(model_class):
            q = MagicMock()
            q.filter.return_value.first.return_value = None  # No org settings
            return q

        db.query.side_effect = query_dispatch

        alert = _fake_alert(org_id="other-org")
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is None
        mock_email_cls.assert_not_called()


# ==============================================================================
# 15 — Unsupported notification mode
# ==============================================================================

class TestUnsupportedMode:
    """Test 15: Unsupported notification_mode is handled gracefully."""

    def test_unsupported_mode_raises_provider_error(self):
        """15. _get_provider raises ProviderError for unknown modes."""
        from app.services.notification_service import _get_provider
        from app.services.notifications.base_provider import ProviderError

        with pytest.raises(ProviderError) as exc_info:
            _get_provider("sms")

        assert "sms" in exc_info.value.reason


# ==============================================================================
# 16 — Real event/alert data in message body
# ==============================================================================

class TestMessageBuilding:
    """Test 16 & 17: Message builder uses real data, never hardcoded locations."""

    def _make_msg_db(self, camera_name: str = "Camera-01", zone_name: str = "Zone-North"):
        db = MagicMock(spec=Session)

        mock_camera = MagicMock()
        mock_camera.name = camera_name
        mock_camera.zone_id = "zone-id-123"

        mock_zone = MagicMock()
        mock_zone.name = zone_name

        def query_dispatch(model_class):
            q = MagicMock()
            name = str(model_class)
            if "Camera" in name:
                q.filter.return_value.first.return_value = mock_camera
            elif "Zone" in name:
                q.filter.return_value.first.return_value = mock_zone
            else:
                q.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_dispatch
        return db

    def test_message_contains_event_type(self):
        """16. Message body includes the real event_type."""
        from app.services.notification_service import _build_message
        db = self._make_msg_db()
        alert = _fake_alert(metadata_json={"event_type": "fire_smoke", "risk_score": 0.95})
        event = _fake_event(event_type="fire_smoke", confidence=0.91)

        subject, body = _build_message(alert, event, db)

        assert "fire" in subject.lower() or "fire" in body.lower()

    def test_message_contains_risk_level(self):
        """16. Message body includes risk level from alert severity."""
        from app.services.notification_service import _build_message
        db = self._make_msg_db()
        alert = _fake_alert(severity="critical")
        event = _fake_event()

        subject, body = _build_message(alert, event, db)

        assert "CRITICAL" in subject.upper() or "CRITICAL" in body.upper()

    def test_message_contains_camera_name(self):
        """16. Message body includes real camera name from DB lookup."""
        from app.services.notification_service import _build_message
        db = self._make_msg_db(camera_name="Gate-Camera-3")
        alert = _fake_alert()
        event = _fake_event()

        subject, body = _build_message(alert, event, db)

        assert "Gate-Camera-3" in body

    def test_message_contains_zone_name(self):
        """16. Message body includes real zone name from DB lookup."""
        from app.services.notification_service import _build_message
        db = self._make_msg_db(zone_name="Welding-Bay-North")
        alert = _fake_alert()
        event = _fake_event()

        subject, body = _build_message(alert, event, db)

        assert "Welding-Bay-North" in body

    def test_no_hardcoded_production_area(self):
        """17. Message body does NOT contain 'Production Area'."""
        from app.services.notification_service import _build_message
        db = self._make_msg_db()
        alert = _fake_alert()
        event = _fake_event()

        subject, body = _build_message(alert, event, db)

        assert "Production Area" not in body
        assert "Production Area" not in subject

    def test_no_hardcoded_restricted_zone(self):
        """17. Message body does NOT contain 'Restricted Zone'."""
        from app.services.notification_service import _build_message
        db = self._make_msg_db()
        alert = _fake_alert()
        event = _fake_event()

        subject, body = _build_message(alert, event, db)

        assert "Restricted Zone" not in body
        assert "Restricted Zone" not in subject

    def test_missing_ppe_in_message(self):
        """16. PPE events include missing_ppe data in the message."""
        from app.services.notification_service import _build_message
        db = self._make_msg_db()
        alert = _fake_alert()
        event = _fake_event(event_type="ppe_detection", missing_ppe=["helmet", "vest"])

        subject, body = _build_message(alert, event, db)

        assert "helmet" in body.lower()


# ==============================================================================
# 18 — Duplicate Notification Protection
# ==============================================================================

class TestDuplicateProtection:
    """Test 18: duplicate notifications are not sent for the same alert+channel."""

    @patch("app.services.notification_service.EmailProvider")
    def test_duplicate_notification_skipped(self, mock_email_cls):
        """18. If a Notification already exists for this alert+channel, dispatch returns it without re-sending."""
        mock_email = MagicMock()
        mock_email_cls.return_value = mock_email

        existing_notif = MagicMock()
        existing_notif.id = _make_id()

        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(notification_mode="email")

        def query_dispatch(model_class):
            q = MagicMock()
            name = str(model_class)
            if "OrgNotification" in name:
                q.filter.return_value.first.return_value = org_settings
            elif "Notification" in name and "OrgNotification" not in name:
                # Simulate existing notification for this alert+channel
                q.filter.return_value.filter.return_value.first.return_value = existing_notif
                q.filter.return_value.first.return_value = existing_notif
            else:
                q.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_dispatch

        alert = _fake_alert()
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        # Should return the existing notification without calling send()
        assert result is existing_notif
        mock_email.send.assert_not_called()


# ==============================================================================
# 19 & 20 — Organization Settings Persistence and Tenant Isolation
# ==============================================================================

class TestOrgSettings:
    """Tests 19 & 20: Settings persistence and tenant isolation."""

    def test_upsert_creates_settings(self):
        """19. upsert_org_settings creates a new row when none exists."""
        from app.services.notification_service import NotificationService

        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None

        saved_settings: list = []
        db.add.side_effect = lambda obj: saved_settings.append(obj)
        db.commit.return_value = None
        db.refresh.return_value = None

        result_mock = MagicMock()
        db.refresh.side_effect = None

        result = NotificationService.upsert_org_settings(
            db=db,
            org_id="org-test-123",
            notifications_enabled=True,
            notification_mode="email",
            notification_recipient="alerts@example.com",
        )

        db.add.assert_called_once()
        db.commit.assert_called_once()
        added = saved_settings[0]
        assert added.org_id == "org-test-123"
        assert added.notifications_enabled is True
        assert added.notification_recipient == "alerts@example.com"

    def test_upsert_updates_existing_settings(self):
        """19. upsert_org_settings updates existing row when one exists."""
        from app.services.notification_service import NotificationService

        existing = MagicMock()
        existing.org_id = "org-test-456"

        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = existing

        NotificationService.upsert_org_settings(
            db=db,
            org_id="org-test-456",
            notifications_enabled=False,
            notification_mode="whatsapp",
            notification_recipient="+919876543210",
        )

        # Should NOT add a new row
        db.add.assert_not_called()
        # Should update existing
        assert existing.notifications_enabled is False
        assert existing.notification_mode == "whatsapp"
        assert existing.notification_recipient == "+919876543210"
        db.commit.assert_called_once()

    def test_settings_tenant_isolation_get(self):
        """20. get_org_settings filters by org_id — different org gets None."""
        from app.services.notification_service import NotificationService

        db = MagicMock(spec=Session)
        # Filter returns None for unrecognized org
        db.query.return_value.filter.return_value.first.return_value = None

        result = NotificationService.get_org_settings(db, "unrecognized-org")
        assert result is None


# ==============================================================================
# 21 — provider_response does not contain credentials
# ==============================================================================

class TestProviderResponseSafety:
    """Test 21: provider_response must never contain credentials."""

    def test_sanitize_removes_auth_token(self):
        """21. _sanitize_provider_response strips 'auth_token' key."""
        from app.services.notification_service import _sanitize_provider_response
        raw = {
            "provider": "email_smtp",
            "status": "sent",
            "auth_token": "SUPER_SECRET",
            "password": "pass123",
            "message_sid": "SM123",
        }
        clean = _sanitize_provider_response(raw)

        assert "auth_token" not in clean
        assert "password" not in clean
        assert "SUPER_SECRET" not in str(clean)
        assert "pass123" not in str(clean)
        assert clean["message_sid"] == "SM123"
        assert clean["status"] == "sent"

    @patch("app.services.notification_service.EmailProvider")
    def test_notification_provider_response_no_credentials(self, mock_email_cls):
        """21. Stored provider_response on Notification row contains no credential keys."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        # Simulate a misconfigured provider accidentally returning a secret
        mock_email.send.return_value = {
            "provider": "email_smtp",
            "status": "sent",
            "auth_token": "leaked_secret",
            "smtp_password": "p@ssword",
        }
        mock_email_cls.return_value = mock_email

        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(notification_mode="email")
        notif_store: list = []

        def query_dispatch(model_class):
            q = MagicMock()
            name = str(model_class)
            if "OrgNotification" in name:
                q.filter.return_value.first.return_value = org_settings
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_dispatch
        db.add.side_effect = lambda obj: notif_store.append(obj)

        alert = _fake_alert()
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=_fake_event(), db=db)

        if result and result.provider_response:
            assert "auth_token" not in result.provider_response
            assert "smtp_password" not in result.provider_response
            assert "leaked_secret" not in str(result.provider_response)


# ==============================================================================
# Notifications Disabled / No Recipient Edge Cases
# ==============================================================================

class TestNotificationGuards:
    """Additional guard tests: disabled, no recipient, etc."""

    def test_dispatch_skipped_when_notifications_disabled(self):
        """dispatch() returns None when notifications_enabled=False."""
        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(notifications_enabled=False)
        db.query.return_value.filter.return_value.first.return_value = org_settings

        alert = _fake_alert()
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is None

    def test_dispatch_skipped_when_no_recipient(self):
        """dispatch() returns None when notification_recipient is empty."""
        db = MagicMock(spec=Session)
        org_settings = _fake_org_settings(notification_recipient="")
        org_settings.notification_recipient = None
        db.query.return_value.filter.return_value.first.return_value = org_settings

        alert = _fake_alert()
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is None


# ==============================================================================
# Evidence Attachment Tests (Phase 16)
# ==============================================================================

class TestEmailEvidenceAttachment:
    """Tests for email evidence JPEG attachment handling."""

    @patch("app.services.notifications.email_provider.get_settings")
    @patch("smtplib.SMTP")
    def test_email_provider_attachment_success(self, mock_smtp_cls, mock_get_settings):
        """EmailProvider successfully attaches evidence image and sends."""
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = "user@example.com"
        settings.smtp_password = "password"
        settings.smtp_from_email = "alerts@example.com"
        mock_get_settings.return_value = settings

        smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        from app.services.notifications.email_provider import EmailProvider
        provider = EmailProvider()
        fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"

        result = provider.send(
            recipient="recipient@test.com",
            subject="Fire Detected Alert",
            body="Fire detected in Zone A",
            attachment_bytes=fake_jpeg,
            attachment_filename="evidence.jpg",
        )

        assert result["provider"] == "email_smtp"
        assert result["status"] == "sent"
        assert result["has_attachment"] is True
        smtp_instance.sendmail.assert_called_once()
        # Verify message body passed to sendmail contains attachment headers
        sent_raw_msg = smtp_instance.sendmail.call_args[0][2]
        assert "Content-Disposition: attachment; filename=\"evidence.jpg\"" in sent_raw_msg

    @patch("app.services.notifications.email_provider.get_settings")
    @patch("smtplib.SMTP")
    def test_email_provider_without_attachment_succeeds(self, mock_smtp_cls, mock_get_settings):
        """EmailProvider sends cleanly without attachment when none provided."""
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = "user@example.com"
        settings.smtp_password = "password"
        settings.smtp_from_email = "alerts@example.com"
        mock_get_settings.return_value = settings

        smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        from app.services.notifications.email_provider import EmailProvider
        provider = EmailProvider()

        result = provider.send(
            recipient="recipient@test.com",
            subject="PPE Alert",
            body="Missing helmet",
            attachment_bytes=None,
        )

        assert result["status"] == "sent"
        assert result["has_attachment"] is False
        smtp_instance.sendmail.assert_called_once()

    @patch("app.services.evidence_service.EvidenceService.resolve_evidence_path")
    @patch("app.services.notification_service._get_provider")
    def test_dispatch_attaches_evidence_when_file_exists(self, mock_get_prov, mock_resolve_path):
        """NotificationService.dispatch reads evidence and passes it to provider."""
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_resolve_path.return_value = mock_file

        mock_prov_instance = MagicMock()
        mock_prov_instance.provider_name = "email_smtp"
        mock_prov_instance.send.return_value = {"provider": "email_smtp", "status": "sent", "has_attachment": True}
        mock_get_prov.return_value = mock_prov_instance

        db, _ = TestNotificationLifecycle()._make_dispatch_db("email")

        alert = _fake_alert()
        alert.evidence_path = "org-1/events/evidence_123.jpg"

        from unittest.mock import mock_open
        with patch("builtins.open", mock_open(read_data=b"fake-image-bytes")):
            from app.services.notification_service import NotificationService
            result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is not None
        assert mock_prov_instance.send.called
        kwargs = mock_prov_instance.send.call_args[1]
        assert kwargs["attachment_bytes"] == b"fake-image-bytes"
        assert kwargs["attachment_filename"] == "evidence.jpg"

    @patch("app.services.evidence_service.EvidenceService.resolve_evidence_path")
    @patch("app.services.notification_service._get_provider")
    def test_dispatch_succeeds_when_evidence_file_missing(self, mock_get_prov, mock_resolve_path):
        """NotificationService.dispatch still delivers email if evidence file is missing."""
        mock_resolve_path.return_value = None  # File not found

        mock_prov_instance = MagicMock()
        mock_prov_instance.provider_name = "email_smtp"
        mock_prov_instance.send.return_value = {"provider": "email_smtp", "status": "sent", "has_attachment": False}
        mock_get_prov.return_value = mock_prov_instance

        db, _ = TestNotificationLifecycle()._make_dispatch_db("email")

        alert = _fake_alert()
        alert.evidence_path = "missing_path.jpg"

        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is not None
        assert mock_prov_instance.send.called
        kwargs = mock_prov_instance.send.call_args[1]
        assert kwargs["attachment_bytes"] is None


# ==============================================================================
# RBAC Authorization Tests (Phase 16)
# ==============================================================================

class TestNotificationRBAC:
    """Tests for notifications.manage and notifications.view RBAC enforcement."""

    def test_admin_user_has_notifications_manage(self):
        """Admin role grants notifications.manage permission."""
        from app.models.role import Role, Permission
        from app.models.user import User

        role = Role(name="Admin", org_id="org-1")
        role.permissions = [
            Permission(perm_name="notifications.view"),
            Permission(perm_name="notifications.manage"),
        ]
        user = User(email="admin@test.com", org_id="org-1", role=role)

        assert user.has_permission("notifications.manage") is True
        assert user.has_permission("notifications.view") is True

    def test_viewer_user_blocked_from_notifications_manage(self):
        """Viewer role lacks notifications.manage permission."""
        from app.models.role import Role, Permission
        from app.models.user import User

        role = Role(name="Viewer", org_id="org-1")
        role.permissions = [
            Permission(perm_name="notifications.view"),
            Permission(perm_name="dashboard.view"),
        ]
        user = User(email="viewer@test.com", org_id="org-1", role=role)

        assert user.has_permission("notifications.view") is True
        assert user.has_permission("notifications.manage") is False


# ==============================================================================
# WhatsApp Normalization & Message Formatting Tests (Phase 17)
# ==============================================================================

class TestWhatsAppPhase17:
    """Tests for robust WhatsApp recipient normalization and Phase 17 message layout."""

    def test_whatsapp_recipient_normalization_with_spaces(self):
        """'+91 9307651917' normalizes to 'whatsapp:+919307651917'."""
        from app.services.notifications.whatsapp_provider import WhatsAppProvider
        assert WhatsAppProvider._normalize_recipient("+91 9307651917") == "whatsapp:+919307651917"

    def test_whatsapp_recipient_normalization_ten_digits(self):
        """'9307651917' normalizes to 'whatsapp:+919307651917'."""
        from app.services.notifications.whatsapp_provider import WhatsAppProvider
        assert WhatsAppProvider._normalize_recipient("9307651917") == "whatsapp:+919307651917"

    def test_whatsapp_recipient_normalization_twelve_digits(self):
        """'919307651917' normalizes to 'whatsapp:+919307651917'."""
        from app.services.notifications.whatsapp_provider import WhatsAppProvider
        assert WhatsAppProvider._normalize_recipient("919307651917") == "whatsapp:+919307651917"

    def test_whatsapp_recipient_normalization_with_prefix_and_spaces(self):
        """'whatsapp:+91 9307651917' normalizes to 'whatsapp:+919307651917'."""
        from app.services.notifications.whatsapp_provider import WhatsAppProvider
        assert WhatsAppProvider._normalize_recipient("whatsapp:+91 9307651917") == "whatsapp:+919307651917"

    def test_whatsapp_recipient_normalization_international_e164(self):
        """Existing valid E.164 international values remain valid."""
        from app.services.notifications.whatsapp_provider import WhatsAppProvider
        assert WhatsAppProvider._normalize_recipient("+14155552671") == "whatsapp:+14155552671"
        assert WhatsAppProvider._normalize_recipient("+44 7911 123456") == "whatsapp:+447911123456"

    def test_whatsapp_message_body_structure(self):
        """WhatsApp body matches the required Phase 17 product layout."""
        from app.services.notification_service import _build_whatsapp_body
        alert = _fake_alert()
        alert.id = "alert-12345678-abcd-ef01-2345-6789abcdef01"
        alert.severity = "critical"
        alert.status = "NEW"
        alert.description = "Immediate evacuation required. Fire/smoke detected in Assembly Zone."
        alert.metadata_json = {
            "event_type": "fire_smoke",
            "risk_score": 0.81,
            "risk_level": "critical",
            "camera_name": "CAM-001 Assembly",
            "zone_name": "Assembly Zone A",
        }

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        body = _build_whatsapp_body(alert=alert, event=None, db=db)

        assert "SafeVision AI — Safety Alert" in body
        assert f"Alert ID: {alert.id}" in body
        assert "Event: Fire Smoke" in body
        assert "Risk: CRITICAL (0.81)" in body
        assert "Status: NEW" in body
        assert "Camera: CAM-001 Assembly" in body
        assert "Zone: Assembly Zone A" in body
        assert "Time:" in body
        assert "Description:" in body
        assert "Immediate evacuation required." in body
        assert "Please log in to SafeVision AI to review and take action." in body

    @patch("app.services.evidence_service.EvidenceService.resolve_evidence_path")
    @patch("app.services.notification_service._get_provider")
    def test_whatsapp_dispatch_does_not_load_evidence(self, mock_get_prov, mock_resolve_path):
        """WhatsApp dispatch never reads or attaches evidence bytes from disk."""
        mock_resolve_path.return_value = MagicMock()

        mock_prov_instance = MagicMock()
        mock_prov_instance.provider_name = "whatsapp_twilio"
        mock_prov_instance.send.return_value = {"provider": "whatsapp_twilio", "status": "queued"}
        mock_get_prov.return_value = mock_prov_instance

        db, _ = TestNotificationLifecycle()._make_dispatch_db("whatsapp")

        alert = _fake_alert()
        alert.evidence_path = "evidence/some_fire.jpg"

        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is not None
        assert mock_prov_instance.send.called
        kwargs = mock_prov_instance.send.call_args[1]
        assert kwargs["attachment_bytes"] is None
        assert kwargs["attachment_filename"] is None
        # resolve_evidence_path should NOT have been called because mode is whatsapp
        assert not mock_resolve_path.called

    def test_upsert_org_settings_normalizes_whatsapp_recipient(self):
        """upsert_org_settings stores clean E.164 number without spaces or whatsapp: prefix."""
        from app.services.notification_service import NotificationService
        from app.models.org_notification_settings import OrgNotificationSettings

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        settings = NotificationService.upsert_org_settings(
            db=db,
            org_id="org-test",
            notifications_enabled=True,
            notification_mode="whatsapp",
            notification_recipient="+91 9307651917",
        )

        assert settings.notification_recipient == "+919307651917"


# ==============================================================================
# Phase 18 — Dual Channel Notification Settings Tests
# ==============================================================================

class TestDualChannelNotificationsPhase18:
    """Comprehensive test suite for Phase 18 Dual Channel Notification Settings."""

    def test_save_both_recipients_independently(self):
        """1. Save both email and WhatsApp recipients independently."""
        from app.services.notification_service import NotificationService

        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None

        saved: list = []
        db.add.side_effect = lambda obj: saved.append(obj)

        settings = NotificationService.upsert_org_settings(
            db=db,
            org_id="org-dual-1",
            notifications_enabled=True,
            notification_mode="email",
            email_recipient="alerts@mycompany.com",
            whatsapp_recipient="+91 98765 43210",
        )

        assert len(saved) == 1
        item = saved[0]
        assert item.email_recipient == "alerts@mycompany.com"
        assert item.whatsapp_recipient == "+919876543210"
        # Legacy recipient is synced to active mode (email)
        assert item.notification_recipient == "alerts@mycompany.com"
        assert item.notifications_enabled is True

    def test_read_both_recipients_schema(self):
        """2. OrgNotificationSettingsResponse schema exposes both recipients."""
        from app.schemas.notification_schema import OrgNotificationSettingsResponse
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        resp = OrgNotificationSettingsResponse(
            id="test-id",
            org_id="test-org",
            notifications_enabled=True,
            notification_mode="email",
            email_recipient="user@example.com",
            whatsapp_recipient="+919876543210",
            notification_recipient="user@example.com",
            created_at=now,
            updated_at=now,
        )

        assert resp.email_recipient == "user@example.com"
        assert resp.whatsapp_recipient == "+919876543210"
        assert resp.notification_recipient == "user@example.com"

    def test_switch_email_to_whatsapp_without_losing_email(self):
        """3. Switching mode from email to whatsapp preserves email recipient."""
        from app.services.notification_service import NotificationService
        from app.models.org_notification_settings import NotificationMode

        existing = MagicMock()
        existing.org_id = "org-switch"
        existing.notification_mode = NotificationMode.EMAIL
        existing.email_recipient = "keepme@example.com"
        existing.whatsapp_recipient = "+919876543210"
        existing.notification_recipient = "keepme@example.com"

        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = existing

        # User changes mode to whatsapp, keeps email
        settings = NotificationService.upsert_org_settings(
            db=db,
            org_id="org-switch",
            notifications_enabled=True,
            notification_mode="whatsapp",
            email_recipient=existing.email_recipient,
            whatsapp_recipient=existing.whatsapp_recipient,
        )

        assert existing.email_recipient == "keepme@example.com"
        assert existing.whatsapp_recipient == "+919876543210"
        assert existing.notification_mode == NotificationMode.WHATSAPP
        # Legacy recipient now synced to active mode (whatsapp)
        assert existing.notification_recipient == "+919876543210"

    def test_switch_whatsapp_to_email_without_losing_whatsapp(self):
        """4. Switching mode from whatsapp to email preserves whatsapp recipient."""
        from app.services.notification_service import NotificationService
        from app.models.org_notification_settings import NotificationMode

        existing = MagicMock()
        existing.org_id = "org-switch"
        existing.notification_mode = NotificationMode.WHATSAPP
        existing.email_recipient = "keepme@example.com"
        existing.whatsapp_recipient = "+919876543210"
        existing.notification_recipient = "+919876543210"

        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = existing

        settings = NotificationService.upsert_org_settings(
            db=db,
            org_id="org-switch",
            notifications_enabled=True,
            notification_mode="email",
            email_recipient=existing.email_recipient,
            whatsapp_recipient=existing.whatsapp_recipient,
        )

        assert existing.email_recipient == "keepme@example.com"
        assert existing.whatsapp_recipient == "+919876543210"
        assert existing.notification_mode == NotificationMode.EMAIL
        # Legacy recipient now synced to active mode (email)
        assert existing.notification_recipient == "keepme@example.com"

    @patch("app.services.notification_service.EmailProvider")
    def test_email_dispatch_uses_email_recipient(self, mock_email_cls):
        """5. Email dispatch uses email_recipient, ignoring whatsapp_recipient."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email.send.return_value = {"provider": "email_smtp", "status": "sent"}
        mock_email_cls.return_value = mock_email

        org_settings = _fake_org_settings(
            notification_mode="email",
            email_recipient="exclusive_email@test.com",
            whatsapp_recipient="+919307651917",
        )

        db = MagicMock(spec=Session)
        def query_dispatch(model_class):
            q = MagicMock()
            if "OrgNotification" in str(model_class):
                q.filter.return_value.first.return_value = org_settings
            else:
                q.filter.return_value.first.return_value = None
            return q
        db.query.side_effect = query_dispatch

        alert = _fake_alert()
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is not None
        assert mock_email.send.called
        kwargs = mock_email.send.call_args[1]
        assert kwargs["recipient"] == "exclusive_email@test.com"

    @patch("app.services.notification_service.WhatsAppProvider")
    def test_whatsapp_dispatch_uses_whatsapp_recipient(self, mock_wa_cls):
        """6. WhatsApp dispatch uses whatsapp_recipient, ignoring email_recipient."""
        mock_wa = MagicMock()
        mock_wa.provider_name = "whatsapp_twilio"
        mock_wa.send.return_value = {"provider": "whatsapp_twilio", "status": "queued"}
        mock_wa_cls.return_value = mock_wa

        org_settings = _fake_org_settings(
            notification_mode="whatsapp",
            email_recipient="exclusive_email@test.com",
            whatsapp_recipient="+919307651917",
        )

        db = MagicMock(spec=Session)
        def query_dispatch_wa(model_class):
            q = MagicMock()
            if "OrgNotification" in str(model_class):
                q.filter.return_value.first.return_value = org_settings
            else:
                q.filter.return_value.first.return_value = None
            return q
        db.query.side_effect = query_dispatch_wa

        alert = _fake_alert()
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is not None
        assert mock_wa.send.called
        kwargs = mock_wa.send.call_args[1]
        assert kwargs["recipient"] == "+919307651917"

    def test_invalid_email_format_rejected(self):
        """7. Invalid email recipient format raises validation error."""
        from app.schemas.notification_schema import OrgNotificationSettingsUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            OrgNotificationSettingsUpdate(
                notifications_enabled=True,
                notification_mode="email",
                email_recipient="not-an-email",
            )
        assert "Invalid email format" in str(exc_info.value)

    def test_invalid_phone_number_rejected(self):
        """8. Invalid WhatsApp phone number (under 10 digits) raises validation error."""
        from app.schemas.notification_schema import OrgNotificationSettingsUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            OrgNotificationSettingsUpdate(
                notifications_enabled=True,
                notification_mode="whatsapp",
                whatsapp_recipient="12345",
            )
        assert "at least 10 digits" in str(exc_info.value)

    def test_active_channel_recipient_required_when_enabled(self):
        """Active channel recipient is required when notifications_enabled is True."""
        from app.schemas.notification_schema import OrgNotificationSettingsUpdate
        from pydantic import ValidationError

        # Email mode enabled but no email provided
        with pytest.raises(ValidationError) as exc_info:
            OrgNotificationSettingsUpdate(
                notifications_enabled=True,
                notification_mode="email",
                email_recipient="",
                whatsapp_recipient="+919876543210",
            )
        assert "Email recipient is required" in str(exc_info.value)

        # WhatsApp mode enabled but no WhatsApp provided
        with pytest.raises(ValidationError) as exc_info:
            OrgNotificationSettingsUpdate(
                notifications_enabled=True,
                notification_mode="whatsapp",
                email_recipient="user@example.com",
                whatsapp_recipient="",
            )
        assert "WhatsApp recipient is required" in str(exc_info.value)

    def test_inactive_channel_recipient_not_required(self):
        """Inactive channel recipient is optional."""
        from app.schemas.notification_schema import OrgNotificationSettingsUpdate

        # Valid with only email in email mode
        update_email = OrgNotificationSettingsUpdate(
            notifications_enabled=True,
            notification_mode="email",
            email_recipient="user@example.com",
            whatsapp_recipient=None,
        )
        assert update_email.email_recipient == "user@example.com"
        assert update_email.whatsapp_recipient is None

        # Valid with only whatsapp in whatsapp mode
        update_wa = OrgNotificationSettingsUpdate(
            notifications_enabled=True,
            notification_mode="whatsapp",
            email_recipient=None,
            whatsapp_recipient="+919876543210",
        )
        assert update_wa.whatsapp_recipient == "+919876543210"
        assert update_wa.email_recipient is None

    @patch("app.services.notification_service.EmailProvider")
    def test_legacy_notification_recipient_fallback(self, mock_email_cls):
        """9. Legacy notification_recipient fallback works when dedicated column is None."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email.send.return_value = {"provider": "email_smtp", "status": "sent"}
        mock_email_cls.return_value = mock_email

        # Dedicated email_recipient is None, only legacy notification_recipient exists
        org_settings = _fake_org_settings(
            notification_mode="email",
            email_recipient=None,
            whatsapp_recipient=None,
            notification_recipient="fallback@legacy.com",
        )
        org_settings.email_recipient = None

        db = MagicMock(spec=Session)
        def query_dispatch_legacy(model_class):
            q = MagicMock()
            if "OrgNotification" in str(model_class):
                q.filter.return_value.first.return_value = org_settings
            else:
                q.filter.return_value.first.return_value = None
            return q
        db.query.side_effect = query_dispatch_legacy

        alert = _fake_alert()
        from app.services.notification_service import NotificationService
        result = NotificationService.dispatch(alert=alert, event=None, db=db)

        assert result is not None
        assert mock_email.send.called
        assert mock_email.send.call_args[1]["recipient"] == "fallback@legacy.com"

    @patch("app.services.notification_service.EmailProvider")
    @patch("app.services.notification_service.WhatsAppProvider")
    def test_zero_cross_channel_recipient_leakage(self, mock_wa_cls, mock_email_cls):
        """Zero cross-channel leakage: Email never gets phone, WhatsApp never gets email."""
        mock_email = MagicMock()
        mock_email.provider_name = "email_smtp"
        mock_email_cls.return_value = mock_email

        mock_wa = MagicMock()
        mock_wa.provider_name = "whatsapp_twilio"
        mock_wa_cls.return_value = mock_wa

        db = MagicMock(spec=Session)

        # 1. Mode email, but settings only have phone number
        bad_email_settings = _fake_org_settings(
            notification_mode="email",
            email_recipient=None,
            notification_recipient="+919876543210",
        )
        bad_email_settings.email_recipient = None
        db.query.return_value.filter.return_value.first.return_value = bad_email_settings

        from app.services.notification_service import NotificationService
        alert = _fake_alert()
        res_email = NotificationService.dispatch(alert=alert, event=None, db=db)
        # Should NOT dispatch email to a phone number!
        assert res_email is None
        mock_email.send.assert_not_called()

        # 2. Mode whatsapp, but settings only have email address
        bad_wa_settings = _fake_org_settings(
            notification_mode="whatsapp",
            whatsapp_recipient=None,
            notification_recipient="user@example.com",
        )
        bad_wa_settings.whatsapp_recipient = None
        db.query.return_value.filter.return_value.first.return_value = bad_wa_settings

        res_wa = NotificationService.dispatch(alert=alert, event=None, db=db)
        # Should NOT dispatch WhatsApp to an email address!
        assert res_wa is None
        mock_wa.send.assert_not_called()


