"""
SafeVision AI — Live Email SMTP Test (Phase 16)

Tests live SMTP connectivity, STARTTLS handshake, authentication,
and minimal email dispatch using the credentials configured in Settings (.env).

NEVER logs or prints secrets/passwords.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings


def main() -> int:
    print("=" * 60)
    print("  SafeVision AI — Phase 16 Live Gmail SMTP Test")
    print("=" * 60)

    settings = get_settings()

    host = settings.smtp_host
    port = settings.smtp_port
    user = settings.smtp_user
    password = settings.smtp_password
    from_email = settings.smtp_from_email or user

    # 1. Validate configuration exists
    print("\n1. Validating Configuration:")
    print(f"   SMTP_HOST:       {host}")
    print(f"   SMTP_PORT:       {port}")
    print(f"   SMTP_USER:       {user}")
    print(f"   SMTP_FROM_EMAIL: {from_email}")
    print(f"   SMTP_PASSWORD:   {'[CONFIGURED - HIDDEN]' if password else '[MISSING]'}")

    missing: list[str] = []
    if not host:
        missing.append("SMTP_HOST")
    if not user:
        missing.append("SMTP_USER")
    if not password:
        missing.append("SMTP_PASSWORD")

    if missing:
        print(f"\n[FAIL] Missing required SMTP settings: {', '.join(missing)}")
        return 1

    recipient = sys.argv[1] if len(sys.argv) > 1 else from_email
    print(f"   Target Recipient: {recipient}")

    # 2. Connect & Handshake
    print(f"\n2. Connecting to {host}:{port}...")
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            print("   [OK] TCP connection established.")

            print("3. Sending EHLO...")
            server.ehlo()
            print("   [OK] Initial EHLO accepted.")

            print("4. Initiating STARTTLS...")
            server.starttls()
            print("   [OK] TLS handshake complete.")

            print("5. Sending secondary EHLO over TLS...")
            server.ehlo()
            print("   [OK] Encrypted EHLO accepted.")

            print("6. Authenticating with Gmail SMTP...")
            server.login(user, password)
            print("   [OK] SMTP Authentication successful!")

            # 7. Construct and send test message
            print("7. Dispatching test email...")
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "SafeVision AI — Phase 16 Live SMTP Integration Test"
            msg["From"] = from_email
            msg["To"] = recipient

            body = (
                "SafeVision AI — Live Email Integration Test (Phase 16)\n\n"
                "This is a verified test of the SafeVision AI Gmail SMTP integration.\n"
                f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                "Transport: SMTP over STARTTLS\n"
                f"Host: {host}:{port}\n"
                f"Sender: {from_email}\n"
                f"Recipient: {recipient}\n\n"
                "If you received this message, Google SMTP authentication and email delivery are WORKING."
            )
            msg.attach(MIMEText(body, "plain", "utf-8"))

            server.sendmail(from_email, recipient, msg.as_string())
            print(f"   [OK] Email successfully sent to: {recipient}")

    except smtplib.SMTPAuthenticationError as exc:
        print(f"\n[FAIL] SMTP Authentication Error: code {exc.smtp_code} — {exc.smtp_error}")
        return 1
    except smtplib.SMTPRecipientsRefused as exc:
        print(f"\n[FAIL] Recipient Refused: {exc}")
        return 1
    except Exception as exc:
        print(f"\n[FAIL] Unexpected SMTP Error: {type(exc).__name__} — {exc}")
        return 1

    print("\n" + "=" * 60)
    print("  RESULT: LIVE SMTP TEST PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
