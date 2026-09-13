"""
Configure test org notification settings for Email or WhatsApp.
Supports CLI arguments:
  python configure_test_org_notifications.py --mode email --recipient user@example.com
  python configure_test_org_notifications.py --mode whatsapp --recipient +1234567890
Defaults to 'email' using SMTP_FROM_EMAIL / SMTP_USER if not specified.
"""
import sys, os, uuid, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app.database import engine
from app.config import get_settings
from sqlalchemy import text

parser = argparse.ArgumentParser(description="Configure test org notification settings.")
parser.add_argument("--mode", choices=["email", "whatsapp"], default="email", help="Notification channel mode")
parser.add_argument("--recipient", default=None, help="Recipient address (email or E.164 phone)")
parser.add_argument("--org-id", default=None, help="Target org ID (defaults to first org / demo org)")
args = parser.parse_args()

settings = get_settings()

mode = args.mode.lower()
recipient = args.recipient

if not recipient:
    if mode == "email":
        recipient = settings.smtp_from_email or settings.smtp_user or ""
        if not recipient:
            print("[FAIL] No email recipient provided and SMTP_FROM_EMAIL / SMTP_USER not found in settings.")
            sys.exit(1)
    elif mode == "whatsapp":
        to_number = os.environ.get("TWILIO_WHATSAPP_TO", "")
        if not to_number:
            print("[FAIL] No WhatsApp recipient provided and TWILIO_WHATSAPP_TO not set in .env")
            sys.exit(1)
        recipient = to_number if not to_number.startswith("whatsapp:") else to_number[len("whatsapp:"):]

print(f"Configuring Notification Settings:")
print(f"  Mode:      {mode}")
print(f"  Recipient: {recipient}")

with engine.begin() as conn:
    if args.org_id:
        row = conn.execute(
            text("SELECT id, name FROM organizations WHERE id = :oid"),
            {"oid": args.org_id}
        ).fetchone()
    else:
        row = conn.execute(text("SELECT id, name FROM organizations ORDER BY created_at LIMIT 1")).fetchone()

    if not row:
        print("[FAIL] Target organization not found.")
        sys.exit(1)

    org_id = row[0]
    org_name = row[1]
    print(f"  Org Name:  {org_name} (ID: {org_id})")

    existing = conn.execute(
        text("SELECT id FROM org_notification_settings WHERE org_id = :oid"),
        {"oid": org_id}
    ).fetchone()

    if existing:
        conn.execute(text("""
            UPDATE org_notification_settings 
            SET notifications_enabled = true,
                notification_mode = :mode,
                notification_recipient = :recipient,
                updated_at = now()
            WHERE org_id = :oid
        """), {"mode": mode, "recipient": recipient, "oid": org_id})
        print(f"  [OK] Updated existing settings (ID: {existing[0]})")
    else:
        new_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO org_notification_settings 
                (id, org_id, notifications_enabled, notification_mode, notification_recipient, created_at, updated_at)
            VALUES 
                (:id, :oid, true, :mode, :recipient, now(), now())
        """), {"id": new_id, "oid": org_id, "mode": mode, "recipient": recipient})
        print(f"  [OK] Inserted new settings (ID: {new_id})")

    verify = conn.execute(text("""
        SELECT id, org_id, notifications_enabled, notification_mode, notification_recipient
        FROM org_notification_settings WHERE org_id = :oid
    """), {"oid": org_id}).fetchone()

    if verify:
        print(f"\n[VERIFIED] Read-back from PostgreSQL:")
        print(f"  ID:        {verify[0]}")
        print(f"  Org ID:    {verify[1]}")
        print(f"  Enabled:   {verify[2]}")
        print(f"  Mode:      {verify[3]}")
        print(f"  Recipient: {verify[4]}")
    else:
        print("[FAIL] Read-back failed")
        sys.exit(1)

print(f"\n[DONE] Test org notification settings configured for {mode.upper()}.")

