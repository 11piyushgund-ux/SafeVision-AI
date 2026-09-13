import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    for val in ["failed", "delivered", "retrying"]:
        try:
            conn.execute(text(f"ALTER TYPE notification_status ADD VALUE IF NOT EXISTS '{val}'"))
            print(f"[OK] Added '{val}' to notification_status enum")
        except Exception as e:
            print(f"[FAIL] Error adding '{val}': {e}")

    for val in ["in_app", "webhook", "sms"]:
        try:
            conn.execute(text(f"ALTER TYPE notification_channel ADD VALUE IF NOT EXISTS '{val}'"))
            print(f"[OK] Added '{val}' to notification_channel enum")
        except Exception as e:
            print(f"[FAIL] Error adding '{val}': {e}")
