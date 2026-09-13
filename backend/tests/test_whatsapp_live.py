"""
SafeVision AI — WhatsApp Notification Live Test Script (Phase 15)

Run this BEFORE starting the full server to confirm your Twilio
credentials and sandbox setup are working.

Usage:
  cd d:\\SafeVision-AI\\backend
  python tests\\test_whatsapp_live.py

Requires:
  - pip install twilio
  - Real TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM in .env
  - Recipient must have joined the Twilio sandbox (see Step 1 in output)
"""

import os
import sys

# ---------------------------------------------------------------------------
# Load .env manually (no app startup needed)
# ---------------------------------------------------------------------------
def load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        print(f"[ERROR] .env not found at: {path}")
        sys.exit(1)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# Read credentials
# ---------------------------------------------------------------------------
ACCOUNT_SID   = os.environ.get("TWILIO_ACCOUNT_SID", "")
AUTH_TOKEN    = os.environ.get("TWILIO_AUTH_TOKEN", "")
FROM_NUMBER   = os.environ.get("TWILIO_WHATSAPP_FROM", "")
TO_NUMBER     = os.environ.get("TWILIO_WHATSAPP_TO", "")
CONTENT_SID   = os.environ.get("TWILIO_CONTENT_SID", "")

print("=" * 60)
print("  SafeVision AI — WhatsApp Notification Live Test")
print("=" * 60)

# ---------------------------------------------------------------------------
# Pre-flight credential check
# ---------------------------------------------------------------------------
errors = []
if not ACCOUNT_SID or "1234567890abcdef" in ACCOUNT_SID:
    errors.append("TWILIO_ACCOUNT_SID is missing or still a placeholder")
if not AUTH_TOKEN or "1234567890abcdef" in AUTH_TOKEN:
    errors.append("TWILIO_AUTH_TOKEN is missing or still a placeholder")
if not FROM_NUMBER:
    errors.append("TWILIO_WHATSAPP_FROM is missing")
if not TO_NUMBER:
    errors.append("TWILIO_WHATSAPP_TO is missing")

if errors:
    print("\n[FAIL] Pre-flight check failed — fix these in .env first:\n")
    for e in errors:
        print(f"  x {e}")
    print()
    print("  TWILIO_ACCOUNT_SID  = your real Account SID from twilio.com/console")
    print("  TWILIO_AUTH_TOKEN   = your real Auth Token from twilio.com/console")
    print("  TWILIO_WHATSAPP_FROM= whatsapp:+14155238886  (sandbox number)")
    print("  TWILIO_WHATSAPP_TO  = whatsapp:+<your_number_in_E164>")
    sys.exit(1)

print(f"\n  Account SID : {ACCOUNT_SID[:10]}...{ACCOUNT_SID[-4:]}")
print(f"  From        : {FROM_NUMBER}")
print(f"  To          : {TO_NUMBER}")
print(f"  Content SID : {CONTENT_SID[:8]}..." if CONTENT_SID else "  Content SID : (not set — freeform body mode)")
print()

# ---------------------------------------------------------------------------
# Check twilio package
# ---------------------------------------------------------------------------
try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
except ImportError:
    print("[FAIL] twilio package not installed.")
    print('  Run: pip install "twilio>=9.0.0,<10.0.0"')
    sys.exit(1)

# ---------------------------------------------------------------------------
# Normalize recipient
# ---------------------------------------------------------------------------
recipient = TO_NUMBER if TO_NUMBER.startswith("whatsapp:") else f"whatsapp:{TO_NUMBER}"

# ---------------------------------------------------------------------------
# TEST 1 — Twilio authentication
# ---------------------------------------------------------------------------
print("TEST 1: Verifying Twilio credentials (account lookup)...")
try:
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    account = client.api.accounts(ACCOUNT_SID).fetch()
    print(f"  PASS - Account: '{account.friendly_name}' | Status: {account.status}")
except TwilioRestException as e:
    print(f"  FAIL - Twilio auth error: code={e.code}, status={e.status}")
    print("       Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
    sys.exit(1)

# ---------------------------------------------------------------------------
# TEST 2 — Send real WhatsApp message
# ---------------------------------------------------------------------------
print(f"\nTEST 2: Sending WhatsApp message to {recipient}...")
body = (
    "SafeVision AI - Test Notification\n\n"
    "This is a Phase 15 integration test.\n"
    "If you received this, WhatsApp notifications are working correctly.\n\n"
    "Test ID: PHASE15-LIVE-TEST"
)

try:
    if CONTENT_SID:
        # Account requires Content Templates
        message = client.messages.create(
            content_sid=CONTENT_SID,
            from_=FROM_NUMBER,
            to=recipient,
        )
    else:
        # Freeform body mode
        message = client.messages.create(
            body=body,
            from_=FROM_NUMBER,
            to=recipient,
        )
    print(f"  PASS - Message sent!")
    print(f"     SID    : {message.sid}")
    print(f"     Status : {message.status}")
    print(f"     To     : {recipient}")
    print(f"     From   : {FROM_NUMBER}")
    if message.status in ("queued", "sent", "delivered"):
        print("\n  Check WhatsApp on the recipient phone now.")
    elif message.status == "undelivered":
        print("\n  WARNING: Status is 'undelivered'")
        print("     Recipient may not have joined the Twilio sandbox.")
        print("     Send 'join <sandbox-keyword>' to +14155238886 on WhatsApp first.")

except TwilioRestException as e:
    print(f"  FAIL - Twilio error: code={e.code}, status={e.status}")
    print(f"         msg   : {e.msg}")
    print(f"         uri   : {getattr(e, 'uri', 'n/a')}")
    print(f"         detail: {getattr(e, 'details', 'n/a')}")
    if e.code == 63007:
        print("\n  Error 63007: Recipient has NOT joined the Twilio sandbox.")
        print("     On the recipient phone, send this WhatsApp message:")
        print(f"     To  : +14155238886")
        print(f"     Text: join <your-sandbox-keyword>")
        print("     (Find keyword at: console.twilio.com > Messaging > Try it out > WhatsApp)")
    elif e.code == 21654:
        print("\n  Error 21654: ContentSid required.")
        print("     Twilio is treating this as a Content Template request.")
        print(f"     Exact body sent: {repr(body)}")
    elif e.code == 21211:
        print("\n  Error 21211: Invalid 'To' phone number format.")
        print(f"     Current value: {recipient}")
    elif e.code == 20003:
        print("\n  Error 20003: Authentication failed.")
        print("     TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN is wrong.")

print("\n" + "=" * 60)
print("  Test complete.")
print("=" * 60)
