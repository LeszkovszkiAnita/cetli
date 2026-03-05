---
name: cetli-remote-control
description: Cetli remote control — send commands to your Windows PC via Google Drive, read results from Google Docs. Use when you want to run a command on your PC remotely.
---

# Cetli — Remote Control Skill

## How it works

1. You create a `parancs.json` file in the user's Google Drive folder (via Zapier)
2. Google Drive for Desktop syncs the file to the user's PC
3. The `cetli.py` script detects it, runs security checks, and executes the command
4. Results are sent to a Google Docs document via Apps Script
5. You read the results with `google_drive_fetch`

## Sending a command

### Always ask the user first!
- Describe what you will do
- Ask for the secret key
- Ask for the 6-digit TOTP code (if enabled)
- Wait for explicit permission

### Command format

Only use `instructions` and `output_hint` parameters. Do NOT set other parameters.

```
Tool: Zapier:google_drive_create_file_from_text
instructions: Create a plain text file named parancs.json in the <DRIVE_FOLDER_NAME> folder on Google Drive. Do NOT convert to Google Doc. Content must be exactly: {"status": "new", "command": "<POWERSHELL_COMMAND>", "key": "<SECRET_KEY>", "totp": "<TOTP_CODE>", "timestamp": "<YYYY-MM-DDTHH:MM:SS>"}
output_hint: file ID and confirmation
```

### Reading results

After the user confirms the command executed:

```
Tool: google_drive_fetch
document_ids: ["<RESULT_DOCUMENT_ID>"]
```

## Important rules

- **NEVER** send a command without the user's explicit key and TOTP code
- **NEVER** use a key or code from memory — always ask fresh
- **ALWAYS** get the current time with `user_time_v0` for the timestamp
- **ALWAYS** describe the command before sending
- Only ONE command at a time — wait for the previous one to complete

## Typical commands

| Goal | PowerShell command |
|------|-------------------|
| Restart PC | `Restart-Computer -Force` |
| Shut down PC | `Stop-Computer -Force` |
| Create file | `Set-Content -Path 'path' -Value 'content' -Encoding UTF8` |
| Read file | `Get-Content 'path'` |
| Open program | `Start-Process program` |
| Open file | `Start-Process notepad 'path'` |
| List folder | `Get-ChildItem 'path'` |
| System info | `Get-ComputerInfo \| Select-Object CsName, OsName` |

## Tips

- Use single quotes (`'`) in PowerShell commands — avoids JSON escaping issues
- Backslashes in JSON must be doubled: `C:\\Users\\...`
- The "Do NOT convert to Google Doc" instruction is critical — without it, the command file may become unreadable
