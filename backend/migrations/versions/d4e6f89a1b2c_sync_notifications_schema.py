"""sync_notifications_schema

Revision ID: d4e6f89a1b2c
Revises: c3f5d89e1a2b
Create Date: 2026-09-13 12:00:00.000000+00:00

Corrective migration:
  Ensures notifications.event_id, notifications.delivered_at, 
  ix_notifications_event_id, and org_notification_settings 
  are present and synchronized with the current ORM models.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e6f89a1b2c'
down_revision: Union[str, None] = 'c3f5d89e1a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure event_id exists on notifications
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'notifications' AND column_name = 'event_id'
            ) THEN
                ALTER TABLE notifications ADD COLUMN event_id VARCHAR(36);
                ALTER TABLE notifications ADD CONSTRAINT fk_notifications_event_id 
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # 2. Ensure index on event_id exists
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_notifications_event_id ON notifications (event_id);
    """)

    # 3. Ensure delivered_at exists on notifications
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'notifications' AND column_name = 'delivered_at'
            ) THEN
                ALTER TABLE notifications ADD COLUMN delivered_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)

    # 4. Ensure org_notification_settings table exists
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'org_notification_settings'
            ) THEN
                CREATE TABLE org_notification_settings (
                    id VARCHAR(36) PRIMARY KEY,
                    org_id VARCHAR(36) NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
                    notifications_enabled BOOLEAN NOT NULL DEFAULT false,
                    notification_mode notification_mode NOT NULL DEFAULT 'email',
                    notification_recipient VARCHAR(500),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
                );
                CREATE UNIQUE INDEX IF NOT EXISTS ix_org_notification_settings_org_id 
                    ON org_notification_settings (org_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notifications_event_id")
    op.execute("ALTER TABLE notifications DROP COLUMN IF EXISTS event_id")
    op.execute("ALTER TABLE notifications DROP COLUMN IF EXISTS delivered_at")
