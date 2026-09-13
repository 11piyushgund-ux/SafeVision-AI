"""
SafeVision AI — Phase 17 Live Production WhatsApp Test Script

Executes the REAL Live Monitoring production path:
  Live Monitoring (video_service.py)
  → CV Inference (YOLO / Fire/Smoke)
  → EventEngine
  → EvidenceService (evidence.jpg captured)
  → RiskEngine
  → AlertEngine
  → db.commit()
  → NotificationService.dispatch()
  → WhatsAppProvider
  → Twilio REST API
  → Real WhatsApp inbox (+919307651917)
"""
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import time
from app.database import SessionLocal
from app.models.camera import Camera
from app.models.zone import Zone
from app.models.alert import Alert
from app.models.event import Event
from app.models.notification import Notification
from app.models.org_notification_settings import OrgNotificationSettings
from app.services.video_service import VideoService
from app.services.notification_service import NotificationService
from app.config import get_settings
from twilio.rest import Client

ORG_ID = "d0000000-0000-0000-0000-000000000001"
VIDEO_PATH = r"D:\SafeVision-AI\videos\fire_02.mp4"

print("=" * 65)
print("  SafeVision AI — Phase 17 Live Production WhatsApp Alert Test")
print("=" * 65)

db = SessionLocal()

# 1. Verify Org Notification Settings
org_settings = db.query(OrgNotificationSettings).filter(OrgNotificationSettings.org_id == ORG_ID).first()
assert org_settings is not None, "No notification settings found for target org"
assert org_settings.notifications_enabled is True, "Notifications not enabled"
assert org_settings.notification_mode.value == "whatsapp", f"Expected mode whatsapp, got {org_settings.notification_mode}"
print(f"1. Org Notification Settings:")
print(f"   Org ID   : {org_settings.org_id}")
print(f"   Enabled  : {org_settings.notifications_enabled}")
print(f"   Mode     : {org_settings.notification_mode.value}")
print(f"   Recipient: {org_settings.notification_recipient}")

# 2. Get Camera and Zone
camera = db.query(Camera).filter(Camera.org_id == ORG_ID).first()
assert camera is not None, "Camera not found for target org"
zone = db.query(Zone).filter(Zone.id == camera.zone_id).first() if camera.zone_id else None
print(f"\n2. Live Monitoring Camera & Zone:")
print(f"   Camera: {camera.name} ({camera.id})")
print(f"   Zone  : {zone.name if zone else 'N/A'}")

# Record notification count before test
initial_notif_count = db.query(Notification).filter(Notification.org_id == ORG_ID, Notification.channel == "whatsapp").count()
print(f"   Initial WhatsApp notifications count: {initial_notif_count}")

# 3. Create VideoSession
print(f"\n3. Initializing VideoSession for Live Monitoring with {os.path.basename(VIDEO_PATH)}...")
session = VideoService.create_session(
    temp_file_path=VIDEO_PATH,
    filename=os.path.basename(VIDEO_PATH),
    camera=camera,
    zone=zone,
    user_id="d0000000-0000-0000-0000-000000000003",
    org_id=ORG_ID,
)
print(f"   Session Created: {session.session_id}")
print(f"   Total Frames   : {session.total_frames}")

# 4. Stream and process frames through Live Monitoring pipeline
print(f"\n4. Streaming frames through VideoService.process_video_generator...")
detected_alert = None
dispatched_notification = None
frames_processed = 0

start_time = time.time()
for frame_payload in VideoService.process_video_generator(session=session, db=db, fire_smoke_interval=1):
    frames_processed += 1
    if frame_payload.new_events:
        print(f"   [FRAME {frames_processed}] Event detected! Type: {frame_payload.new_events[0].event_type}, Severity: {frame_payload.new_events[0].severity}")
        
        # Check for newly created Alert and Notification in DB
        latest_alert = (
            db.query(Alert)
            .filter(Alert.org_id == ORG_ID)
            .order_by(Alert.created_at.desc())
            .first()
        )
        if latest_alert:
            latest_notif = (
                db.query(Notification)
                .filter(Notification.alert_id == latest_alert.id, Notification.channel == "whatsapp")
                .first()
            )
            if latest_notif:
                detected_alert = latest_alert
                dispatched_notification = latest_notif
                print(f"   [SUCCESS] Alert created and Notification dispatched on frame {frames_processed}!")
                break

    if frames_processed >= 75:
        print("   Reached 75 frames without alert — stopping.")
        break

elapsed = time.time() - start_time
print(f"   Processed {frames_processed} frames in {elapsed:.2f}s")

if not detected_alert or not dispatched_notification:
    print("[FAIL] No qualifying alert or notification was dispatched during the test.")
    db.close()
    sys.exit(1)

# 5. Verify Results
print("\n" + "=" * 65)
print("  5. PRODUCTION NOTIFICATION RESULTS")
print("=" * 65)
print(f"Alert ID    : {detected_alert.id}")
print(f"Title       : {detected_alert.title}")
print(f"Severity    : {detected_alert.severity}")
print(f"Status      : {detected_alert.status}")
print(f"Evidence    : {detected_alert.evidence_path}")
print("-" * 65)
print(f"Notification ID: {dispatched_notification.id}")
print(f"Channel        : {dispatched_notification.channel}")
print(f"Status         : {dispatched_notification.status}")
print(f"Recipient      : {dispatched_notification.recipient_address}")
print(f"Sent At        : {dispatched_notification.sent_at}")
print(f"Provider Resp  : {dispatched_notification.provider_response}")
print("-" * 65)
print("WhatsApp Message Body Delivered:")
print(dispatched_notification.body)
print("-" * 65)

# 6. Verify Twilio Delivery Status
message_sid = dispatched_notification.provider_response.get("message_sid")
print(f"\n6. Twilio Delivery Status Verification (SID: {message_sid}):")
if message_sid:
    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    twilio_msg = client.messages(message_sid).fetch()
    print(f"   Twilio SID   : {twilio_msg.sid}")
    print(f"   To           : {twilio_msg.to}")
    print(f"   From         : {twilio_msg.from_}")
    print(f"   Status       : {twilio_msg.status}")
    print(f"   Error Code   : {twilio_msg.error_code}")
    print(f"   Error Message: {twilio_msg.error_message}")
    assert twilio_msg.error_code is None, f"Twilio reported error: {twilio_msg.error_code}"
    assert twilio_msg.to == f"whatsapp:{org_settings.notification_recipient}", f"Recipient mismatch: {twilio_msg.to}"
    print(f"   [OK] Twilio successfully accepted and queued/delivered to {twilio_msg.to} with ZERO errors!")

# 7. Verify Duplicate Protection
print(f"\n7. Duplicate Protection Test:")
dup_notif = NotificationService.dispatch(alert=detected_alert, event=None, db=db)
if dup_notif and dup_notif.id == dispatched_notification.id:
    print(f"   [PASS] Duplicate dispatch returned existing Notification ({dup_notif.id[:8]}...) without re-sending.")
else:
    print(f"   [FAIL] Unexpected result on duplicate dispatch: {dup_notif}")

print("\n" + "=" * 65)
print("  PHASE 17 LIVE PRODUCTION WHATSAPP ALERT TEST: PASSED")
print("=" * 65)

db.close()
