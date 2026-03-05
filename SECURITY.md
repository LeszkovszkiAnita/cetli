# Security Details

## Architecture overview

Cetli uses a layered security model. No single layer is meant to be impenetrable — they work together to make unauthorized command execution as difficult as possible for a personal tool.

```
Command arrives (parancs.json)
    │
    ├─ 1. Key validation ─────── Does the key match config.json?
    ├─ 2. Timestamp validation ── Is the command fresh (< 5 minutes)?
    ├─ 3. Blacklist check ─────── Does it match any dangerous patterns?
    ├─ 4. TOTP verification ──── Is the 6-digit code valid? (optional)
    │
    ▼
    Execute in Constrained Language Mode
```

If any check fails, the command is rejected, logged, and the command file is deleted.

## Layer 1: Secret key

Every command must include a `key` field matching the value in `config.json`. This is the primary security mechanism.

**Strength:** Anyone who doesn't know your key cannot send commands.
**Weakness:** Static — if compromised, the attacker has permanent access until you change it. Mitigated by Layer 4 (TOTP).

## Layer 2: Timestamp validation

Commands include a timestamp. Cetli rejects commands older than `max_age_minutes` (default: 5) and commands with timestamps more than 1 minute in the future.

**Protects against:** Replay attacks (reusing an intercepted command file), stale commands from interrupted sync.

## Layer 3: Command blacklist

A list of 40+ patterns that are always blocked, regardless of key/TOTP validity. Before checking, Cetli strips PowerShell backtick characters to defeat basic obfuscation.

### Blocked categories

- **File/disk destruction** — `Remove-Item -Recurse`, `Format-Volume`, etc.
- **System tampering** — `bcdedit`, `reg delete`, `Set-ExecutionPolicy`, etc.
- **User manipulation** — `New-LocalUser`, `net user`, etc.
- **Remote code execution** — `Invoke-WebRequest *.exe`, `DownloadString`, `IEX`, etc.
- **Credential theft** — `Get-Credential`, `mimikatz`, etc.
- **Event log tampering** — `Clear-EventLog`, `wevtutil cl`, etc.
- **Obfuscation** — `-EncodedCommand`, `FromBase64String`, `&(`, etc.
- **Self-protection** — Blocks access to cetli.py and config.json by path and name

### Known bypass vectors

The blacklist is defense-in-depth, not a security boundary. Known bypasses include:

- **Variable-based obfuscation:** `$p = 'C:/Ce'; Get-Content "$p`tli/config.json"`
- **Wildcard patterns:** `Get-Content C:/Cetl*/con*.*`
- **String manipulation at runtime**
- **Environment variable expansion**

**This is by design.** A whitelist-based approach would be more secure but would eliminate the tool's flexibility. The key + TOTP combination is the real security — the blacklist catches accidents and lazy attacks.

## Layer 4: TOTP (optional)

When enabled, every command must include a valid 6-digit TOTP code from Google Authenticator. Codes change every 30 seconds, with a configurable acceptance window (default: ±3 minutes to accommodate Drive sync delays).

**This is the strongest defense.** Even if an attacker knows your static key, they need physical access to your phone to generate a valid TOTP code.

## Layer 5: Constrained Language Mode

Every PowerShell command executes with CLM (Constrained Language Mode) prepended. This blocks:

- .NET method calls (e.g., `[System.Net.Dns]::GetHostName()`)
- COM object creation
- Win32 API calls
- Type definitions

**Limitation:** CLM can be bypassed without AppLocker/WDAC system policies. The blacklist blocks `fulllanguage` to prevent the most obvious bypass, but this is not a hard security boundary.

## Result reporting security

When Apps Script reporting is enabled:

- Results travel over **HTTPS** (encrypted in transit)
- The Apps Script URL is a long random string (not guessable)
- An **auth token** is required for writes
- The Apps Script can **only append text** to one specific Google Doc
- If reporting fails, it does **not** block command execution

## Recommendations

1. **Use TOTP** — It's the biggest security improvement for the least effort
2. **Protect config.json** — Consider setting file permissions so only your user can read it
3. **Keep Cetli outside Drive sync** — The script and config should never be uploaded to the cloud
4. **Review the blacklist** — Add patterns specific to your setup if needed
5. **Check naplo.txt periodically** — Security events are logged there
6. **Rotate your key** — Change it occasionally, especially if you suspect it may be compromised
