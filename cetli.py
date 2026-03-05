"""
CETLI v2.1 - Secure remote control script via Google Drive
Claude leaves messages on Google Drive, this script executes them.

Usage: python cetli.py
Stop: Ctrl+C

Security features (v2.1):
- Secret key authentication (stored in separate config.json)
- Optional TOTP two-factor authentication (Google Authenticator)
- Timestamp validation: rejects commands older than max_age_minutes
- Dangerous command blacklist: blocks destructive patterns
- Startup grace period: waits before processing to allow manual intervention
- Double read: ensures file sync is complete before processing

How it works:
1. Claude (via Zapier) creates a parancs.json file in your Google Drive folder
2. Google Drive for Desktop syncs the file to your computer
3. This script detects the file and runs security checks
4. If all checks pass, it executes the PowerShell command inside
5. The script deletes parancs.json and logs the result to naplo.txt
6. Claude reads back the result from naplo.txt

Setup:
1. Copy cetli.py and config.json to a LOCAL folder (e.g. C:\\Cetli\\)
   DO NOT put them in a cloud-synced folder!
2. Edit config.json — set your Drive path and secret key
3. Optional: run setup_totp.py to enable Google Authenticator 2FA
4. Run: python cetli.py

Requirements:
- Python 3.x
- Google Drive for Desktop installed and syncing
- Windows (PowerShell commands)
- pyotp (only if TOTP is enabled): pip install pyotp
"""

import json
import subprocess
import time
import os
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════════════════
#  CONFIG FILE — all settings are in config.json (same folder as this script)
# ═══════════════════════════════════════════════════════════════════════

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    """Load configuration from config.json."""
    if not os.path.exists(CONFIG_FILE):
        print(colored(f"\n!!! config.json not found at: {CONFIG_FILE}", "red"))
        print(colored("!!! Copy config.example.json to config.json and edit it.", "red"))
        return None

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(colored(f"\n!!! config.json is not valid JSON: {e}", "red"))
        return None

    # Check required fields
    missing = []
    if not config.get("drive_path") or "<" in config.get("drive_path", "<"):
        missing.append("drive_path")
    if not config.get("secret_key") or "<" in config.get("secret_key", "<"):
        missing.append("secret_key")

    if missing:
        print(colored(f"\n!!! config.json is missing: {', '.join(missing)}", "red"))
        print(colored("!!! Edit config.json before running Cetli.", "red"))
        return None

    # Check TOTP config consistency
    if config.get("totp_enabled", False):
        if not config.get("totp_secret"):
            print(colored("\n!!! totp_enabled is true but totp_secret is missing!", "red"))
            print(colored("!!! Run setup_totp.py first, or set totp_enabled to false.", "red"))
            return None
        # Check if pyotp is installed
        try:
            import pyotp
        except ImportError:
            print(colored("\n!!! totp_enabled is true but pyotp is not installed!", "red"))
            print(colored("!!! Run: pip install pyotp", "red"))
            return None

    return config


# ╔══════════════════════════════════════════════════════════════════════╗
# ║                    DANGEROUS COMMAND BLACKLIST                      ║
# ║                                                                     ║
# ║  Commands matching these patterns will NEVER be executed.           ║
# ║  Add your own patterns if needed.                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝
BLACKLIST_PATTERNS = [
    # --- File/disk destruction ---
    "remove-item.*-recurse",
    "format-volume",
    "format-disk",
    "clear-disk",
    "remove-partition",

    # --- System tampering ---
    "bcdedit",
    "reg delete",
    "reg add",
    "set-executionpolicy",
    "disable-netadapter",
    "stop-service",
    "remove-service",
    "set-mppreference.*-disablerealtimemonitoring",

    # --- User/access manipulation ---
    "new-localuser",
    "add-localgroupmember",
    "net user ",
    "net localgroup ",

    # --- Remote code execution ---
    "invoke-webrequest.*\\.exe",
    "invoke-restmethod.*\\.exe",
    "start-bitstransfer.*\\.exe",
    "downloadstring",
    "downloadfile",
    "invoke-expression",
    "iex ",
    "iex(",

    # --- System directory writes ---
    "c:\\\\windows\\\\system32",
    "c:/windows/system32",
    "$env:systemroot",

    # --- Credential theft ---
    "get-credential",
    "convertfrom-securestring",
    "mimikatz",
    "sekurlsa",

    # --- Event log tampering ---
    "clear-eventlog",
    "remove-eventlog",
    "wevtutil cl",

    # --- Obfuscation / hidden code execution ---
    "-encodedcommand",         # Base64 encoded PowerShell (full)
    "-enc ",                   # Abbreviated form
    "-en ",                    # Shorter abbreviation
    "powershell.*-e ",         # Shortest form, only when calling powershell
    "frombase64string",        # [Convert]::FromBase64String()
    "tobase64string",          # Encoding to Base64
    "&(",                      # Dynamic command invocation &("cmd")
    "&{",                      # Dynamic scriptblock invocation
    ".invoke(",                # Method-based command invocation
    "new-object.*net.webclient",  # .NET webclient for downloads
    "fulllanguage",                # Attempt to exit Constrained Language Mode

    # --- Cetli self-protection ---
    "c:\\cetli",                    # Prevent access to script/config directory
    "c:/cetli",                    # Forward slash variant
    "config.json",                 # Prevent access to config by name
    "cetli.py",                    # Prevent access to script by name
]


# ═══════════════════════════════════════════════════════════════════════
#                    FUNCTIONS — no need to edit below
# ═══════════════════════════════════════════════════════════════════════

def colored(text, color):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def validate_key(data, secret_key):
    """Check if the command contains the correct secret key."""
    provided_key = data.get("key", "")

    if provided_key == secret_key:
        return True

    print(colored("SECURITY: Invalid key — command REJECTED.", "red"))
    log_security_event("INVALID_KEY", data.get("command", "???"),
                      f"Provided key does not match", LOG_FILE)
    return False


def validate_timestamp(data, max_age_minutes):
    """Check if the command is fresh enough."""
    timestamp_str = data.get("timestamp", "")

    if not timestamp_str:
        print(colored("SECURITY: Missing timestamp — command REJECTED.", "red"))
        log_security_event("NO_TIMESTAMP", data.get("command", "???"), "", LOG_FILE)
        return False

    try:
        cmd_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        if cmd_time.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()

        age_seconds = (now - cmd_time).total_seconds()
        age_minutes = age_seconds / 60

        if age_minutes > max_age_minutes:
            print(colored(f"SECURITY: Command too old ({age_minutes:.1f} min) — REJECTED.", "red"))
            log_security_event("STALE_COMMAND", data.get("command", "???"),
                             f"Age: {age_minutes:.1f} min (max: {max_age_minutes})", LOG_FILE)
            return False

        if age_seconds < -60:
            print(colored("SECURITY: Command from the future — REJECTED.", "red"))
            log_security_event("FUTURE_COMMAND", data.get("command", "???"),
                             f"Timestamp: {timestamp_str}", LOG_FILE)
            return False

        return True

    except (ValueError, TypeError) as e:
        print(colored(f"SECURITY: Cannot parse timestamp '{timestamp_str}' — REJECTED.", "red"))
        log_security_event("BAD_TIMESTAMP", data.get("command", "???"), str(e), LOG_FILE)
        return False


def validate_command_safety(command_text):
    """Check if the command matches any blacklisted pattern.
    Strips backticks first to defeat PowerShell obfuscation tricks."""
    # Remove backticks — PowerShell uses them for obfuscation: `I`n`v`o`k`e
    cleaned = command_text.replace("`", "")
    command_lower = cleaned.lower()

    for pattern in BLACKLIST_PATTERNS:
        if pattern.lower() in command_lower:
            print(colored(f"SECURITY: Blocked dangerous pattern '{pattern}' — REJECTED.", "red"))
            log_security_event("BLACKLISTED", command_text,
                             f"Matched: '{pattern}'", LOG_FILE)
            return False

    return True


def validate_totp(data, totp_secret, valid_window=6):
    """Check if the TOTP code is valid.
    valid_window=6 means ±3 minutes tolerance (6 × 30 sec)."""
    import pyotp

    provided_code = data.get("totp", "")

    if not provided_code:
        print(colored("SECURITY: Missing TOTP code — command REJECTED.", "red"))
        log_security_event("NO_TOTP", data.get("command", "???"),
                          "TOTP is enabled but no code was provided", LOG_FILE)
        return False

    totp = pyotp.TOTP(totp_secret)

    if totp.verify(str(provided_code), valid_window=valid_window):
        return True

    print(colored("SECURITY: Invalid TOTP code — command REJECTED.", "red"))
    log_security_event("INVALID_TOTP", data.get("command", "???"),
                      f"Provided code: {provided_code}", LOG_FILE)
    return False


def log_security_event(event_type, command, details, log_file):
    """Log a security event to naplo.txt."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] !!! SECURITY {event_type}: {command[:200]}\n")
            if details:
                f.write(f"  Details: {details}\n")
            f.write("\n")
    except Exception:
        pass


def startup(drive_path, log_file):
    """Create Drive folder and log file if they don't exist."""
    if not os.path.exists(drive_path):
        os.makedirs(drive_path)
        print(colored(f"Folder created: {drive_path}", "green"))

    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"=== CETLI LOG ===\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        print(colored("naplo.txt created.", "green"))


def read_command(command_file):
    """Read parancs.json twice to ensure Drive sync is complete."""
    try:
        with open(command_file, "r", encoding="utf-8") as f:
            first_read = f.read()

        time.sleep(1)

        if not os.path.exists(command_file):
            return None

        with open(command_file, "r", encoding="utf-8") as f:
            second_read = f.read()

        if first_read != second_read:
            print(colored("File still syncing, waiting for next cycle...", "yellow"))
            return None

        return json.loads(second_read)

    except json.JSONDecodeError as e:
        print(colored(f"Error parsing JSON: {e}", "red"))
        log_security_event("BAD_JSON", "(unparseable)", str(e), LOG_FILE)
        try:
            os.remove(command_file)
            print(colored("Corrupt parancs.json deleted.", "yellow"))
        except Exception:
            pass
        return None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(colored(f"Error reading command: {e}", "red"))
        return None


def execute_command(command_text):
    """Execute a PowerShell command in Constrained Language Mode."""
    print(colored(f"\n>>> EXECUTING: {command_text}", "yellow"))

    # Prepend Constrained Language Mode — blocks .NET methods, COM objects,
    # and other advanced features that could be used for obfuscation attacks.
    # The blacklist also blocks "fulllanguage" to prevent reverting this.
    safe_command = (
        "$ExecutionContext.SessionState.LanguageMode = 'ConstrainedLanguage'; "
        + command_text
    )

    try:
        result = subprocess.run(
            ["powershell", "-Command", safe_command],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace"
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode == 0:
            print(colored("Execution successful!", "green"))
            return {
                "success": True,
                "output": output if output else "(no output)",
                "error": ""
            }
        else:
            print(colored(f"Error occurred: {error}", "red"))
            return {
                "success": False,
                "output": output,
                "error": error if error else f"Exit code: {result.returncode}"
            }

    except subprocess.TimeoutExpired:
        print(colored("Timeout (120 sec)!", "red"))
        return {"success": False, "output": "", "error": "Timeout: 120 seconds."}
    except Exception as e:
        print(colored(f"Unexpected error: {e}", "red"))
        return {"success": False, "output": "", "error": str(e)}


def write_result(command_text, result, command_file, log_file, report_config=None):
    """Log the result to naplo.txt, optionally report to Google Docs, and delete parancs.json."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] COMMAND: {command_text}\n")
        if result["success"]:
            f.write(f"  RESULT: {result['output'][:500]}\n")
        else:
            f.write(f"  ERROR: {result['error'][:500]}\n")
        f.write("\n")

    print(colored("Result logged.", "green"))

    # --- Report to Google Docs via Apps Script ---
    if report_config:
        report_to_docs(command_text, result, timestamp, report_config)

    try:
        os.remove(command_file)
        print(colored("parancs.json deleted.", "green"))
    except Exception as e:
        print(colored(f"Could not delete parancs.json: {e}", "red"))


def report_to_docs(command_text, result, timestamp, report_config):
    """Send command result to Google Docs via Apps Script webhook."""
    import urllib.request

    url = report_config["url"]
    token = report_config["token"]

    payload = json.dumps({
        "token": token,
        "timestamp": timestamp,
        "command": command_text[:500],
        "result": result["output"][:2000] if result["success"] else result["error"][:2000],
        "success": result["success"]
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        # Apps Script redirects, so we need to follow it
        import urllib.request as ur
        opener = ur.build_opener(ur.HTTPRedirectHandler)
        response = opener.open(req, timeout=15)
        print(colored("Result reported to Google Docs.", "green"))
    except Exception as e:
        # Don't fail the whole process if reporting fails
        print(colored(f"Could not report to Docs (non-critical): {e}", "yellow"))


def main_loop():
    """Main polling loop with security checks."""

    # --- Load config ---
    config = load_config()
    if not config:
        return

    drive_path = config["drive_path"]
    secret_key = config["secret_key"]
    max_age = config.get("max_age_minutes", 5)
    polling = config.get("polling_seconds", 10)
    grace = config.get("startup_grace_seconds", 30)
    totp_enabled = config.get("totp_enabled", False)
    totp_secret = config.get("totp_secret", "")
    totp_window = config.get("totp_valid_window", 6)

    # Report config (optional — sends results to Google Docs)
    report_config = None
    if config.get("report_url"):
        report_config = {
            "url": config["report_url"],
            "token": config.get("report_token", "")
        }

    command_file = os.path.join(drive_path, "parancs.json")
    log_file = os.path.join(drive_path, "naplo.txt")

    # Make log_file accessible to validation functions
    global LOG_FILE
    LOG_FILE = log_file

    # --- Banner ---
    print(colored(r"""
    ___       _   _ _
   / __|___ _| |_| (_)
  | |  / -_)  _| | |
  | |__\___|\__|_|_|
   \____/        v2.1
    """, "blue"))
    print(colored("Cetli v2.1 - Secure remote control via Google Drive", "blue"))
    print(colored(f"Watching: {command_file}", "blue"))
    print(colored(f"Polling: every {polling} seconds", "blue"))
    print(colored(f"Max command age: {max_age} minutes", "blue"))
    print(colored(f"Blacklist patterns: {len(BLACKLIST_PATTERNS)}", "blue"))
    print(colored(f"TOTP 2FA: {'ENABLED' if totp_enabled else 'disabled'}", "blue"))
    if totp_enabled:
        print(colored(f"TOTP window: ±{totp_window * 30} seconds", "blue"))
    print(colored(f"Config: {CONFIG_FILE}", "blue"))
    print(colored(f"Report to Docs: {'ENABLED' if report_config else 'disabled'}", "blue"))

    # --- Init ---
    startup(drive_path, log_file)

    # --- Startup grace period ---
    print(colored(f"\nStartup grace period: {grace} seconds...", "magenta"))
    print(colored("(Press Ctrl+C now to cancel if a stale command is waiting)\n", "magenta"))
    try:
        time.sleep(grace)
    except KeyboardInterrupt:
        print(colored("\nCancelled during grace period. Bye!", "yellow"))
        return

    print(colored("Grace period complete. Now watching for commands.\n", "green"))
    print(colored("Stop: Ctrl+C\n", "blue"))

    # --- Main loop ---
    while True:
        try:
            if not os.path.exists(command_file):
                time.sleep(polling)
                continue

            data = read_command(command_file)

            if data and data.get("status") == "new":
                command_text = data.get("command", "")

                if not command_text:
                    print(colored("Empty command received, skipping.", "yellow"))
                    write_result("(empty)", {
                        "success": False, "output": "", "error": "Empty command"
                    }, command_file, log_file, report_config)
                    continue

                # --- SECURITY CHECKS ---
                print(colored("\n--- Security checks ---", "magenta"))

                if not validate_key(data, secret_key):
                    try:
                        os.remove(command_file)
                    except Exception:
                        pass
                    time.sleep(polling)
                    continue

                if not validate_timestamp(data, max_age):
                    try:
                        os.remove(command_file)
                    except Exception:
                        pass
                    time.sleep(polling)
                    continue

                if not validate_command_safety(command_text):
                    try:
                        os.remove(command_file)
                    except Exception:
                        pass
                    time.sleep(polling)
                    continue

                if totp_enabled:
                    if not validate_totp(data, totp_secret, totp_window):
                        try:
                            os.remove(command_file)
                        except Exception:
                            pass
                        time.sleep(polling)
                        continue

                print(colored("All checks passed!", "green"))
                print(colored("---", "magenta"))

                result = execute_command(command_text)
                write_result(command_text, result, command_file, log_file, report_config)

            time.sleep(polling)

        except KeyboardInterrupt:
            print(colored("\n\nCetli stopped. Bye!", "yellow"))
            break
        except Exception as e:
            print(colored(f"Unexpected error in main loop: {e}", "red"))
            time.sleep(polling)


# === START ===
LOG_FILE = ""  # Set by main_loop from config

if __name__ == "__main__":
    main_loop()
