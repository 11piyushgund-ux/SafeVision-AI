"""
SafeVision AI — Phase 18 Migration: Dual Channel Notification Recipients

Adds independent email_recipient and whatsapp_recipient columns to
org_notification_settings and safely backfills them from the existing
notification_recipient based on notification_mode.

Idempotent and non-destructive:
- Preserves notification_recipient for backward compatibility.
- Never drops columns or resets tables.
- Does not hardcode recipient values; derives backfill directly from existing DB rows.
"""

import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database import engine, SessionLocal


def run_migration():
    print("=== SafeVision AI: Phase 18 Dual Channel Notification Recipients Migration ===")
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # 1. Add columns if not exists
            print("[1/3] Adding email_recipient and whatsapp_recipient columns if not present...")
            conn.execute(text("""
                ALTER TABLE org_notification_settings
                ADD COLUMN IF NOT EXISTS email_recipient VARCHAR(255),
                ADD COLUMN IF NOT EXISTS whatsapp_recipient VARCHAR(50);
            """))
            print("      Columns verified/added successfully.")

            # 2. Backfill existing rows based on current notification_mode
            print("[2/3] Backfilling existing rows according to notification_mode...")
            
            # If mode == 'email' and email_recipient is NULL, backfill from notification_recipient
            res_email = conn.execute(text("""
                UPDATE org_notification_settings
                SET email_recipient = TRIM(notification_recipient)
                WHERE notification_mode = 'email'
                  AND email_recipient IS NULL
                  AND notification_recipient IS NOT NULL
                  AND TRIM(notification_recipient) != '';
            """))
            print(f"      Rows backfilled for email_recipient: {res_email.rowcount}")

            # If mode == 'whatsapp' and whatsapp_recipient is NULL, backfill from notification_recipient
            res_wa = conn.execute(text("""
                UPDATE org_notification_settings
                SET whatsapp_recipient = TRIM(notification_recipient)
                WHERE notification_mode = 'whatsapp'
                  AND whatsapp_recipient IS NULL
                  AND notification_recipient IS NOT NULL
                  AND TRIM(notification_recipient) != '';
            """))
            print(f"      Rows backfilled for whatsapp_recipient: {res_wa.rowcount}")

            trans.commit()
            print("      Transaction committed successfully.")

        except Exception as e:
            trans.rollback()
            print(f"[ERROR] Migration failed: {e}", file=sys.stderr)
            sys.exit(1)

    # 3. Verify and print current state
    print("[3/3] Verifying current org_notification_settings table state...")
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id, org_id, notifications_enabled, notification_mode,
                   email_recipient, whatsapp_recipient, notification_recipient
            FROM org_notification_settings
        """)).mappings().all()
        for r in rows:
            print(f"  Org: {r['org_id']}")
            print(f"    Mode: {r['notification_mode']} | Enabled: {r['notifications_enabled']}")
            print(f"    Email Recipient: {r['email_recipient']}")
            print(f"    WhatsApp Recipient: {r['whatsapp_recipient']}")
            print(f"    Legacy Recipient: {r['notification_recipient']}")
    finally:
        db.close()

    print("=== Phase 18 Database Migration Completed Successfully ===")


if __name__ == "__main__":
    run_migration()
