# Apps Script Setup Guide — Two-Way Communication

This guide enables Cetli to report command results back to a Google Docs document that Claude can read remotely. Without this, Cetli is one-way only (commands go down, but results stay on your PC).

## Overview

```
cetli.py executes command
    ↓
HTTP POST (HTTPS) → Google Apps Script webhook
    ↓
Apps Script appends result → Google Docs document (your Drive)
    ↓
Claude reads the document via Google Drive integration
```

## Step 1: Create the result document

Create a new Google Docs document in your Google Drive. This is where command results will be logged. You can name it anything (e.g., "Cetli Results").

**Copy the document ID** from the URL. For example:
```
https://docs.google.com/document/d/1ABCdef_ghiJKLmnoPQRstuVWXyz/edit
                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                     This is the document ID
```

## Step 2: Create the Apps Script

1. Go to [script.google.com](https://script.google.com)
2. Click **New project**
3. Name the project (e.g., "Cetli Results")
4. Delete the default code and paste the following:

```javascript
// Cetli result receiver
// cetli.py POSTs command results here, this script writes them to Google Docs

var DOC_ID = "<YOUR_GOOGLE_DOCS_ID>";     // Paste your document ID here
var AUTH_TOKEN = "<YOUR_AUTH_TOKEN>";       // Choose a token (any passphrase)

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    
    // Token verification
    if (data.token !== AUTH_TOKEN) {
      return ContentService.createTextOutput(
        JSON.stringify({status: "error", message: "Invalid token"})
      ).setMimeType(ContentService.MimeType.JSON);
    }
    
    // Open Google Doc and write result
    var doc = DocumentApp.openById(DOC_ID);
    var body = doc.getBody();
    
    var timestamp = data.timestamp || new Date().toISOString();
    var command = data.command || "(unknown)";
    var result = data.result || "(no output)";
    var success = data.success ? "OK" : "ERROR";
    
    // Append result
    body.appendParagraph("─────────────────────────────────");
    body.appendParagraph("[" + timestamp + "] " + success);
    body.appendParagraph("CMD: " + command);
    body.appendParagraph(">>> " + result);
    body.appendParagraph("");
    
    doc.saveAndClose();
    
    return ContentService.createTextOutput(
      JSON.stringify({status: "ok"})
    ).setMimeType(ContentService.MimeType.JSON);
    
  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({status: "error", message: err.toString()})
    ).setMimeType(ContentService.MimeType.JSON);
  }
}
```

5. Replace `<YOUR_GOOGLE_DOCS_ID>` with your document ID from Step 1
6. Replace `<YOUR_AUTH_TOKEN>` with a passphrase of your choice
7. **Save** (Ctrl+S)

## Step 3: Deploy as Web App

1. Click **Deploy** → **New deployment**
2. Click the gear icon (⚙️) → select **Web app**
3. Fill in:
   - **Description:** Cetli result receiver
   - **Execute as:** Me
   - **Who has access:** Anyone
4. Click **Deploy**

### Authorization prompt

Google will ask you to authorize the script. You may see a warning:

> "This app isn't verified"

This is normal for personal Apps Script projects. To proceed:

1. Click **Advanced** (bottom left)
2. Click **Go to [Your Project Name] (unsafe)**
3. Click **Allow**

After authorization, you'll receive a **Web app URL** like:
```
https://script.google.com/macros/s/AKfycb.../exec
```

**Copy this URL** — you'll need it for the next step.

## Step 4: Configure Cetli

Add these fields to your `config.json`:

```json
{
    "report_url": "https://script.google.com/macros/s/AKfycb.../exec",
    "report_token": "<YOUR_AUTH_TOKEN>"
}
```

Use the same `AUTH_TOKEN` value you set in the Apps Script code.

## Step 5: Test

1. Restart `cetli.py`
2. The banner should show: `Report to Docs: ENABLED`
3. Send a test command (e.g., `Get-Date`)
4. Check the console — you should see: `Result reported to Google Docs.` in green
5. Open your Google Docs document — the result should be there

## Security Considerations

- **The webhook URL is long and random** — not guessable or indexed
- **The auth token** prevents unauthorized writes even if someone finds the URL
- **Data travels over HTTPS** — encrypted in transit
- **The worst-case scenario** if someone gets both URL + token: they can append text to your results document. They cannot read your files, execute commands, or access anything else in your Google account.
- **This is the same trust level** as Google Drive sync, which your commands already travel through

## Troubleshooting

### "Could not report to Docs (non-critical)" warning

- The command still executed successfully — only the reporting failed
- Check your `report_url` in config.json (must be the full URL ending in `/exec`)
- Check your `report_token` matches the `AUTH_TOKEN` in Apps Script
- Make sure the Apps Script is deployed (not just saved)

### 404 error during deployment

If you get a 404 during the authorization step:
1. Go back to the Apps Script editor
2. Click **Deploy** → **New deployment** again
3. During authorization, click **Advanced** → **Go to [Project] (unsafe)**
4. This warning is normal for personal scripts

### Results not appearing in Google Docs

- Verify the `DOC_ID` in your Apps Script matches your document
- Check that you authorized the script to access Google Docs
- Try redeploying: **Deploy** → **Manage deployments** → **Edit** → **New version** → **Deploy**

### Clearing old results

The Google Docs document will grow over time. To clear it:
1. Open the document
2. Select all (Ctrl+A) and delete
3. Optionally add a header like "=== CETLI RESULTS ==="

## Disabling result reporting

Remove or empty the `report_url` field in `config.json`:

```json
{
    "report_url": ""
}
```

The banner will show `Report to Docs: disabled` and Cetli continues to work in one-way mode.
