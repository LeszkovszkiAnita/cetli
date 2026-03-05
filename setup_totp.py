"""
CETLI TOTP Setup — Google Authenticator configuration

This script:
1. Generates a shared secret key
2. Displays a QR code in the terminal (ASCII format)
3. Updates config.json with the secret key

Usage:
    pip install pyotp qrcode
    python setup_totp.py

Then scan the QR code with the Google Authenticator app.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")


def main():
    # --- Check dependencies ---
    try:
        import pyotp
    except ImportError:
        print("ERROR: pyotp is not installed.")
        print("Run: pip install pyotp")
        sys.exit(1)

    try:
        import qrcode
    except ImportError:
        print("ERROR: qrcode is not installed.")
        print("Run: pip install qrcode")
        sys.exit(1)

    # --- Load existing config ---
    if not os.path.exists(CONFIG_FILE):
        print(f"ERROR: config.json not found at: {CONFIG_FILE}")
        print("Create config.json first before running TOTP setup.")
        sys.exit(1)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    # --- Check if TOTP is already configured ---
    if config.get("totp_secret"):
        print("WARNING: TOTP is already configured in config.json!")
        print(f"Current secret: {config['totp_secret'][:6]}...")
        response = input("Overwrite with a new secret? (y/N): ").strip().lower()
        if response != "y":
            print("Cancelled.")
            return

    # --- Generate secret ---
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)

    # --- Generate provisioning URI ---
    # This is what the QR code encodes
    uri = totp.provisioning_uri(
        name="Cetli",
        issuer_name="Cetli Remote Control"
    )

    # --- Display QR code in terminal ---
    print("\n" + "=" * 50)
    print("  CETLI TOTP SETUP — Google Authenticator")
    print("=" * 50)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    print("\nScan this QR code with Google Authenticator:\n")
    qr.print_ascii(invert=True)

    print(f"\nManual entry code (if QR doesn't work): {secret}")
    print(f"Account name: Cetli")
    print(f"Type: Time-based (TOTP)")

    # --- Test the code ---
    print("\n" + "-" * 50)
    print("Let's verify it works!")
    print("Open Google Authenticator and enter the 6-digit code.\n")

    test_code = input("Enter code: ").strip()

    if totp.verify(test_code, valid_window=1):
        print("\n✓ Code is valid! TOTP is working correctly.")
    else:
        print("\n✗ Code is INVALID. Please try again.")
        print("Make sure your phone's time is synchronized.")
        retry = input("Try another code? (y/N): ").strip().lower()
        if retry == "y":
            test_code = input("Enter code: ").strip()
            if totp.verify(test_code, valid_window=2):
                print("\n✓ Code is valid!")
            else:
                print("\n✗ Still invalid. Setup cancelled.")
                print("Check your phone's time settings and try again.")
                return
        else:
            print("Setup cancelled.")
            return

    # --- Update config.json ---
    config["totp_enabled"] = True
    config["totp_secret"] = secret
    if "totp_valid_window" not in config:
        config["totp_valid_window"] = 6  # ±3 minutes

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    print("\n" + "=" * 50)
    print("  SETUP COMPLETE!")
    print("=" * 50)
    print(f"\n✓ config.json updated with TOTP secret")
    print(f"✓ totp_enabled = true")
    print(f"✓ totp_valid_window = {config['totp_valid_window']} (±{config['totp_valid_window'] * 30} sec)")
    print(f"\nFrom now on, Cetli will require a TOTP code with every command.")
    print(f"The code changes every 30 seconds in your Authenticator app.")
    print(f"\nIMPORTANT: Keep your config.json safe — it contains your TOTP secret!")


if __name__ == "__main__":
    main()
