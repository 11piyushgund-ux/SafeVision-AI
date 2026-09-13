"""add_notifications_table_and_org_notification_settings

Revision ID: c3f5d89e1a2b
Revises: b7f3a21c90de
Create Date: 2026-09-11 16:00:00.000000+00:00

Creates:
  - notifications table  (Notification ORM model — Phase 15)
  - org_notification_settings table  (OrgNotificationSettings — Phase 15)
  - notification_channel, notification_status, notification_mode PostgreSQL enums

New columns on notifications vs. original model design:
  - event_id FK → events.id ON DELETE SET NULL
  - delivered_at nullable TIMESTAMPTZ
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3f5d89e1a2b'
down_revision: Union[str, None] = 'b7f3a21c90de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Create enum types (idempotent: skip if already exist) ---
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_channel AS ENUM ('email','whatsapp','in_app','webhook','sms');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_status AS ENUM ('pending','sent','delivered','failed','retrying');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_mode AS ENUM ('email','whatsapp');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # --- notifications table ---
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column(
            'alert_id', sa.String(length=36), nullable=False,
        ),
        sa.Column(
            'event_id', sa.String(length=36), nullable=True,
        ),
        sa.Column(
            'org_id', sa.String(length=36), nullable=False,
        ),
        sa.Column(
            'recipient_user_id', sa.String(length=36), nullable=True,
        ),
        sa.Column('recipient_address', sa.String(length=500), nullable=True),
        sa.Column(
            'channel',
            postgresql.ENUM(
                'email', 'whatsapp', 'in_app', 'webhook', 'sms',
                name='notification_channel',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'status',
            postgresql.ENUM(
                'pending', 'sent', 'delivered', 'failed', 'retrying',
                name='notification_status',
                create_type=False,
            ),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column(
            'provider_response',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['alert_id'], ['alerts.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['event_id'], ['events.id'], ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['org_id'], ['organizations.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['recipient_user_id'], ['users.id'], ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_alert_id', 'notifications', ['alert_id'], unique=False)
    op.create_index('ix_notifications_event_id', 'notifications', ['event_id'], unique=False)
    op.create_index('ix_notifications_org_id', 'notifications', ['org_id'], unique=False)

    # --- org_notification_settings table ---
    op.create_table(
        'org_notification_settings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column(
            'notifications_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        ),
        sa.Column(
            'notification_mode',
            postgresql.ENUM(
                'email', 'whatsapp',
                name='notification_mode',
                create_type=False,
            ),
            nullable=False,
            server_default='email',
        ),
        sa.Column('notification_recipient', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['org_id'], ['organizations.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', name='uq_org_notification_settings_org_id'),
    )
    op.create_index(
        'ix_org_notification_settings_org_id',
        'org_notification_settings',
        ['org_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_org_notification_settings_org_id', table_name='org_notification_settings')
    op.drop_table('org_notification_settings')

    op.drop_index('ix_notifications_org_id', table_name='notifications')
    op.drop_index('ix_notifications_event_id', table_name='notifications')
    op.drop_index('ix_notifications_alert_id', table_name='notifications')
    op.drop_table('notifications')

    op.execute("DROP TYPE IF EXISTS notification_mode")
    op.execute("DROP TYPE IF EXISTS notification_status")
    op.execute("DROP TYPE IF EXISTS notification_channel")
