# TOTP Setup Guide — Google Authenticator 2FA

This guide walks you through enabling two-factor authentication for Cetli using Google Authenticator.

## What is TOTP?

TOTP (Time-based One-Time Password) is the same technology used by Google Authenticator, Microsoft Authenticator, and similar apps. It generates a 6-digit code that changes every 30 seconds. Only someone with physical access to your phone can provide the current code.

With TOTP enabled, every Cetli command requires **two things**:
1. Your **static secret key** (something you know)
2. A **6-digit TOTP code** from your phone (something you have)

This is true two-factor authentication.

## Prerequisites

- Python 3.x
- Google Authenticator app on your phone ([Android](https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2) / [iOS](https://apps.apple.com/app/google-authenticator/id388497605))

## Step 1: Install dependencies

```bash
pip install pyotp qrcode
```

## Step 2: Run the setup script

```bash
cd C:\Cetli
python setup_totp.py
```

The script will:
1. Generate a random secret key
2. Display a QR code in your terminal

```
==================================================
  CETLI TOTP SETUP — Google Authenticator
==================================================

Scan this QR code with Google Authenticator:

    █▀▀▀▀▀▀▀█ ▄▀ ▄▄▀▄ █▀▀▀▀▀▀▀█
    █ █▀▀▀█ █ ▄▀█▀▀▄  █ █▀▀▀█ █
    ...

Manual entry code (if QR doesn't work): JBSWY3DPEHPK3PXP
Account name: Cetli
Type: Time-based (TOTP)
```

## Step 3: Scan the QR code

1. Open **Google Authenticator** on your phone
2. Tap the **+** button
3. Choose **Scan a QR code**
4. Point your camera at the terminal QR code

If the QR code doesn't scan, tap **Enter a setup key** and type in the manual entry code shown on screen.

## Step 4: Verify

The setup script will ask you to enter the current 6-digit code from your Authenticator app:

```
Let's verify it works!
Open Google Authenticator and enter the 6-digit code.

Enter code: 482951

✓ Code is valid! TOTP is working correctly.
```

## Step 5: Done!

The script automatically updates your `config.json`:

```json
{
    "totp_enabled": true,
    "totp_secret": "JBSWY3DPEHPK3PXP...",
    "totp_valid_window": 6
}
```

From now on, every command sent to Cetli must include a valid TOTP code.

## How the time window works

TOTP codes change every 30 seconds in Google Authenticator. However, the Cetli command chain has delays:

```
You type the code → Claude sends command → Zapier creates file → Drive syncs → cetli.py reads
```

This can take 1–3 minutes. The `totp_valid_window` setting handles this:

| Value | Tolerance | Recommended for |
|-------|-----------|----------------|
| 2 | ±1 minute | Fast local network |
| 4 | ±2 minutes | Typical usage |
| **6** | **±3 minutes** | **Default — covers Drive sync delays** |
| 10 | ±5 minutes | Slow connections |

The default of 6 (±3 minutes) is still much more secure than a static key, because an intercepted code expires within minutes.

## Troubleshooting

### "Invalid TOTP code" error

- **Check your phone's time** — TOTP depends on accurate time. Go to Settings → Date & Time → enable automatic/network time.
- **Code just changed?** — Try the new code. The tolerance window usually handles this, but in edge cases it might help.
- **Wrong account?** — Make sure you're reading the "Cetli" entry in Authenticator, not another service.

### Lost phone / new phone

Your TOTP secret is stored in `config.json` (`totp_secret` field). To recover:
1. Run `setup_totp.py` again to generate a new secret and QR code
2. Scan the new QR code on your new phone
3. The old code will no longer work

### Disabling TOTP

Set `totp_enabled` to `false` in `config.json`:

```json
{
    "totp_enabled": false
}
```

Cetli will revert to static key authentication only.
