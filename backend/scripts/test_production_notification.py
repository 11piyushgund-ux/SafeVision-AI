"""
SafeVision AI — Production Notification Flow Test (Phase 15)

Tests the COMPLETE production pipeline:
  Alert → NotificationService.dispatch → WhatsAppProvider → Twilio
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from datetime import datetime, timezone
from app.database import SessionLocal
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.notification import Notification, NotificationStatus
from app.services.notification_service import NotificationService

ORG_ID = "eb849dc2-e7db-4cb4-b532-702ee94b8a2d"

print("=" * 60)
print("  SafeVision AI — Production Notification Flow Test")
print("=" * 60)

# 1. Verify org settings
db = SessionLocal()
settings = NotificationService.get_org_settings(db, ORG_ID)
if not settings:
    print("[FAIL] No org notification settings found")
    sys.exit(1)
mode_val = settings.notification_mode.value if hasattr(settings.notification_mode, 'value') else str(settings.notification_mode)
print(f"\n1. Org Settings: Enabled={settings.notifications_enabled}, Mode={mode_val}, Recipient={settings.notification_recipient}")

# 2. Create a test alert via ORM
alert_id = str(uuid.uuid4())
print(f"\n2. Creating test alert: {alert_id[:8]}...")
alert = Alert(
    id=alert_id,
    org_id=ORG_ID,
    title="PPE Violation - Production Notification Test",
    description="Worker detected without hard hat and safety vest. Controlled test of Phase 15 notification pipeline.",
    severity=AlertSeverity.HIGH,
    status=AlertStatus.NEW,
    metadata_json={
        "event_type": "ppe_violation",
        "risk_score": 0.85,
        "risk_level": "high",
        "camera_name": "Main Entrance Gate",
        "zone_name": "Zone A - Loading Dock",
    },
)
db.add(alert)
db.commit()
print("   [OK] Alert created via ORM and committed to DB.")
print(f"   Alert ID: {alert.id}")
print(f"   Severity: {alert.severity}")

# 3. Dispatch notification via production path
print(f"\n3. Dispatching notification via NotificationService...")
notification = NotificationService.dispatch(alert=alert, event=None, db=db)

# 4. Results
print(f"\n4. Results:")
if notification is None:
    print("   [FAIL] dispatch() returned None")
    db.close()
    sys.exit(1)

status_val = notification.status.value if hasattr(notification.status, 'value') else str(notification.status)
channel_val = notification.channel.value if hasattr(notification.channel, 'value') else str(notification.channel)

print(f"   Notification ID: {notification.id[:8]}...")
print(f"   Channel: {channel_val}")
print(f"   Status: {status_val}")
print(f"   Recipient: {notification.recipient_address}")
print(f"   Body:\n---\n{notification.body}\n---")

if notification.provider_response:
    pr = notification.provider_response
    print(f"   Provider: {pr.get('provider', 'N/A')}")
    if 'message_sid' in pr:
        print(f"   Message SID: {pr['message_sid']}")
    if 'smtp_host' in pr:
        print(f"   SMTP Host: {pr['smtp_host']}")
    if 'recipient_domain' in pr:
        print(f"   Recipient Domain: {pr['recipient_domain']}")
    if 'status' in pr:
        print(f"   Provider Status: {pr['status']}")
    if 'error' in pr:
        print(f"   Error: {pr['error']}")
    # Security check: ensure no secrets stored in DB
    for key in pr:
        assert 'token' not in key.lower(), f"Credential leak: {key}"
        assert 'password' not in key.lower(), f"Credential leak: {key}"
    print(f"   [OK] No credentials leaked in provider_response")

# 5. Failure isolation: check alert still exists
alert_check = db.query(Alert).filter(Alert.id == alert_id).first()
print(f"\n5. Failure Isolation: Alert exists in DB: {alert_check is not None}")

# 6. Duplicate protection: second dispatch must not send another message
print(f"\n6. Duplicate Protection:")
dup = NotificationService.dispatch(alert=alert, event=None, db=db)
if dup and dup.id == notification.id:
    print(f"   [OK] Duplicate dispatch returned existing notification (ID: {dup.id[:8]}...) without re-sending.")
elif dup is None:
    print(f"   [OK] Duplicate returned None (skipped)")
else:
    print(f"   [WARN] Unexpected new notification: {dup.id}")

print(f"\n{'=' * 60}")
if status_val == "sent":
    print("  RESULT: PRODUCTION NOTIFICATION FLOW — PASSED")
    print(f"  Check {channel_val.upper()} inbox/device ({notification.recipient_address}) for the alert notification.")
elif status_val == "failed":
    print("  RESULT: FAILED (provider error)")
    print(f"  Error details: {notification.provider_response}")
else:
    print(f"  Status: {status_val}")

print("=" * 60)
db.close()
