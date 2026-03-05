// ═══════════════════════════════════════════════════════════════════════
//  CETLI — Apps Script Result Receiver
//
//  This script receives command results from cetli.py via HTTP POST
//  and appends them to a Google Docs document.
//
//  Setup:
//  1. Create a Google Docs document for results
//  2. Paste this code into a new Apps Script project (script.google.com)
//  3. Replace DOC_ID with your document ID
//  4. Replace AUTH_TOKEN with a passphrase of your choice
//  5. Deploy as Web App (Execute as: Me, Access: Anyone)
//  6. Copy the deployment URL to your config.json (report_url field)
//
//  See docs/APPS_SCRIPT_SETUP.md for detailed instructions.
// ═══════════════════════════════════════════════════════════════════════

var DOC_ID = "<YOUR_GOOGLE_DOCS_DOCUMENT_ID>";
var AUTH_TOKEN = "<YOUR_AUTH_TOKEN>";

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
