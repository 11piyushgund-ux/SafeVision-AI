"""
SafeVision AI — Phase 15 Database Synchronization Script

Creates the MISSING org_notification_settings table.

Background:
  Alembic migration c3f5d89e1a2b was stamped BEFORE the
  org_notification_settings DDL was appended to the migration file.
  The `notifications` table exists; `org_notification_settings` does not.

This script:
  1. Checks if org_notification_settings already exists (idempotent).
  2. Creates the notification_mode enum type IF NOT EXISTS.
  3. Creates the org_notification_settings table with exact schema
     matching the ORM model and migration DDL.
  4. Creates the required unique index on org_id.
  5. Does NOT touch Alembic version — it is already at head.
  6. Does NOT modify any existing tables or data.

Run:
  cd d:\SafeVision-AI\backend
  python scripts/sync_org_notification_settings.py
"""

import sys
import os

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text, inspect


def main() -> None:
    insp = inspect(engine)
    existing_tables = insp.get_table_names()

    if "org_notification_settings" in existing_tables:
        print("[OK] org_notification_settings already exists — no action needed.")
        return

    print("[INFO] org_notification_settings table is MISSING. Creating...")

    with engine.begin() as conn:
        # 1. Create notification_mode enum (idempotent)
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE notification_mode AS ENUM ('email','whatsapp');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """))
        print("  [OK] notification_mode enum ensured.")

        # 2. Create the table with exact schema from migration/model
        conn.execute(text("""
            CREATE TABLE org_notification_settings (
                id              VARCHAR(36) NOT NULL,
                org_id          VARCHAR(36) NOT NULL,
                notifications_enabled BOOLEAN NOT NULL DEFAULT false,
                notification_mode     notification_mode NOT NULL DEFAULT 'email',
                notification_recipient VARCHAR(500),
                created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                PRIMARY KEY (id),
                CONSTRAINT uq_org_notification_settings_org_id UNIQUE (org_id),
                FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
            );
        """))
        print("  [OK] org_notification_settings table created.")

        # 3. Create the unique index on org_id (matching migration)
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_org_notification_settings_org_id
            ON org_notification_settings (org_id);
        """))
        print("  [OK] ix_org_notification_settings_org_id index created.")

    # 4. Verify
    insp2 = inspect(engine)
    if "org_notification_settings" in insp2.get_table_names():
        cols = [c["name"] for c in insp2.get_columns("org_notification_settings")]
        print(f"\n[VERIFIED] Table exists with columns: {cols}")
    else:
        print("\n[FAIL] Table was NOT created — check errors above.")
        sys.exit(1)

    # 5. Verify Alembic version is unchanged
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        versions = [r[0] for r in result]
        print(f"[VERIFIED] Alembic version unchanged: {versions}")

    print("\n[DONE] Database synchronized. org_notification_settings is ready.")


if __name__ == "__main__":
    main()
