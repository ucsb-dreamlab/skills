---
name: rclone-google-drive
description: Access and manage Google Drive (My Drive and Shared Drives) via rclone CLI. Uses the google-oauth skill to authenticate and configure remotes, and provides safe patterns for searching, exporting/importing Google Docs/Sheets/Slides, and transferring files without full-drive scans.
license: MIT
---

# Rclone Google Drive Guide

Use this skill to interact with Google Drive (including Shared Drives) via `rclone`. For OAuth2 authentication and creating/updating `rclone` remotes, use the **`google-oauth`** skill.

## ⚠️ Critical Usage Guidelines

**NEVER download or sync the entire Google Drive.** Always specify a limited set of files:

```bash
❌ UNACCEPTABLE:
rclone copy gdrive: ~/backup              # Entire drive!
rclone sync gdrive: ~/backup              # Entire drive!
rclone ls gdrive:                         # List entire drive recursively!

✅ ACCEPTABLE:
rclone lsd gdrive:                        # List top-level folders only (non-recursive)
rclone copy gdrive:"MyFolder" ~/backup --drive-export-formats pdf    # Specific folder by name
rclone copy gdrive: ~/backup --drive-root-folder-id="FOLDER_ID" --drive-export-formats pdf  # Entire folder by ID
rclone copy gdrive:"Document" ~/context/ --drive-export-formats pdf  # Specific file
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats pdf  # Specific file by ID
```

**Safe Limits:**

- ✅ List top-level directories with `rclone lsd gdrive:`
- ✅ Download specific named files/folders
- ✅ Download specific files by ID (`rclone backend copyid`)
- ✅ Download entire folder by ID using `--drive-root-folder-id` flag
- ✅ Download a folder with up to ~50 files
- ✅ Use targeted `lsjson` / folder listings with filters or `jq` to find files and IDs
- ❌ Download entire drive without `--drive-root-folder-id`
- ❌ Run recursive `rclone ls gdrive:` on the drive root
- ❌ Download large folders without checking file count

## Authentication & Remote Setup (via `google-oauth` Skill)

Do **not** use interactive `rclone config` in a remote workspace. Instead, load and follow the **`google-oauth`** skill (`skills/google-oauth/SKILL.md`), which authenticates using `~/.config/dreamlab/google_client.json`, saves unified credentials to `~/.config/gcloud/application_default_credentials.json`, and configures `rclone` non-interactively:

1. **Ensure `rclone` is installed:**
   ```bash
   which rclone >/dev/null || (curl -fsSL https://rclone.org/install.sh | sudo bash)
   ```

2. **Authenticate with `drive` scope (if not already authenticated):**
   Follow the `google-oauth` skill (`uv run skills/google-oauth/scripts/google_oauth.py status` to check existing scopes, then `url --scopes drive` and `exchange`).

3. **Configure the `rclone` remote from saved credentials:**
   ```bash
   # Personal "My Drive" remote:
   uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote gdrive

   # Or list and bind to a Shared Drive (Team Drive):
   uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --list-shared-drives
   uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote gdrive --shared-drive "Carpentry"
   ```

4. **Verify Setup:**
   ```bash
   rclone listremotes
   rclone lsd gdrive:
   rclone about gdrive:
   ```
   *(Or run `bash skills/rclone-google-drive/scripts/check-rclone-setup.sh`.)*

## Essential Commands

### Navigation & Discovery (Limited Scope)

⚠️ **Always use specific folders, not the entire drive.**

```bash
# List directories in a specific folder
rclone lsd gdrive:"MyFolder"

# List files in a specific folder
rclone ls gdrive:"MyFolder"

# List files in specific subfolder only
rclone lsd gdrive:"MyFolder/SubFolder"

# Find files in a specific folder with metadata (including file ID) as JSON
rclone lsjson gdrive:"MyFolder" | jq '.[] | select(.Name | test("document"; "i"))'

# Filter files within a specific folder using glob pattern
rclone ls gdrive:"MyFolder" --include "*document*"
```

### Uploading & Downloading (Limited Scope)

⚠️ **Only upload/download specific files or folders with limited content.**

```bash
# Upload local folder to specific Google Drive folder
rclone copy /local/path gdrive:backup

# Download specific Google Drive folder to local
rclone copy gdrive:MyFolder /local/path

# Sync specific folder (make destination match source)
rclone sync /local/path gdrive:MyFolder

# Move files within specific folders
rclone move gdrive:OldFolder gdrive:NewFolder

# Download specific file by name
rclone copy gdrive:"MyDocument" ./context/

# Download specific file by ID (no directory browsing)
rclone backend copyid gdrive: FILE-ID /local/path/
```

### Maintenance (Specific Operations)

```bash
# View account quota info
rclone about gdrive:

# Check integrity of specific backup folder
rclone check /local/path gdrive:MyBackup

# Deduplicate specific folder (limit to one folder, not entire drive)
rclone dedupe gdrive:MyFolder --dedupe=interactive
```

### Advanced Operations

```bash
# Show configuration for a remote
rclone config show gdrive

# List all configured remotes
rclone listremotes

# Test access without modifying anything (dry-run)
rclone copy --dry-run /local/path gdrive:backup

# Verbose output for debugging
rclone -v copy /local/path gdrive:backup

# Show transfer speed and progress
rclone --progress copy /local/path gdrive:backup
```

## Efficient File Searching & Discovery (Without Full Drive Listing)

**⚠️ IMPORTANT**: Recursively listing an entire Google Drive (`rclone ls gdrive:`) is slow, uses excessive API quota, and violates safety guidelines. 

Use folder-targeted commands like `lsjson`, `lsd`, and `ls` with `--include` or `jq` filters to find files and IDs safely.

*(Note: Older guides mention `rclone backend query`, but this command is not supported by standard rclone Google Drive backends. Use `rclone lsjson` instead.)*

### Search Files in a Specific Folder (`lsjson` + `jq`)

The `lsjson` command lists files and folders with full metadata—including file `ID`, `MimeType`, `Size`, and `ModTime`—as structured JSON:

```bash
# Search for files by name in a specific folder (case-insensitive)
rclone lsjson gdrive:"MyFolder" | jq '.[] | select(.Name | test("budget"; "i"))'

# Search recursively within a folder (safe when scoped to a folder)
rclone lsjson -R gdrive:"MyFolder" | jq '.[] | select(.Name | test("report.*2024"; "i"))'

# Extract only File ID and Name
rclone lsjson gdrive:"MyFolder" | jq -r '.[] | "\(.ID) \(.Name)"'

# Filter by MIME type (e.g., Google Docs only)
rclone lsjson gdrive:"MyFolder" | jq '.[] | select(.MimeType == "application/vnd.google-apps.document")'

# Filter by Google Sheets only
rclone lsjson gdrive:"MyFolder" | jq '.[] | select(.MimeType == "application/vnd.google-apps.spreadsheet")'

# Filter by PDF only
rclone lsjson gdrive:"MyFolder" | jq '.[] | select(.MimeType == "application/pdf")'

# Limit results (first 10 items)
rclone lsjson gdrive:"MyFolder" | jq '.[0:10]'
```

### Search Files Using Patterns (`ls` with `--include`)

```bash
# List matching files within a specific folder
rclone ls gdrive:"MyFolder" --include "*budget*"

# Recursive search within a specific folder
rclone ls gdrive:"MyFolder" --include "*.pdf"
```

**Common MIME Types:**

- `application/vnd.google-apps.document` - Google Docs
- `application/vnd.google-apps.spreadsheet` - Google Sheets
- `application/pdf` - PDFs
- `text/plain` - Text files
- `image/jpeg` - JPEG images
- `video/mp4` - MP4 videos

### Access Files by ID (Direct Operations)

Once you have a file ID (e.g. from `lsjson`), use `backend copyid` directly without browsing directories:

```bash
# Copy file by ID to local location
rclone backend copyid gdrive: FILE-ID /local/path/filename.txt

# Copy multiple files by ID (multiple ID-path pairs)
rclone backend copyid gdrive: ID1 /path1 ID2 /path2

# Copy to folder (preserves original filename with trailing /)
rclone backend copyid gdrive: FILE-ID /local/folder/

# Move file by ID to new location
rclone backend moveid gdrive: FILE-ID /local/path/newname.txt

# Preview changes without executing
rclone backend copyid --dry-run gdrive: FILE-ID /local/path/

# Interactive mode (ask for confirmation)
rclone backend copyid -i gdrive: FILE-ID /local/path/
```

### Download File by ID in Different Formats

Export Google Docs to different formats using file ID without browsing directories:

**Get File ID First:**

```bash
# Find file in folder and get its ID
FILE_ID=$(rclone lsjson gdrive:"MyFolder" | jq -r '.[] | select(.Name == "My Document") | .ID')
echo "File ID: $FILE_ID"
```

**Download File by ID as PDF (recommended):**

```bash
# Download as PDF
rclone backend copyid gdrive: FILE-ID ~/downloads/ --drive-export-formats pdf

# Download with specific filename
rclone backend copyid gdrive: FILE-ID ~/downloads/document.pdf --drive-export-formats pdf
```

**Download File by ID as Markdown:**

```bash
# Export Google Doc to Markdown for version control
# NOTE: Use "md" not "markdown" with backend copyid (see Known Gotchas below)
rclone backend copyid gdrive: FILE-ID ~/docs/ --drive-export-formats md

# Download with specific filename
rclone backend copyid gdrive: FILE-ID ~/docs/document.md --drive-export-formats md
```

**Download File by ID as DOCX:**

```bash
# Download Google Doc as editable Word document
rclone backend copyid gdrive: FILE-ID ~/downloads/ --drive-export-formats docx
```

**Download File by ID as CSV (Sheets):**

```bash
# Download Google Sheet as CSV (universal spreadsheet format)
rclone backend copyid gdrive: FILE-ID ~/data/ --drive-export-formats csv

# Download as CSV with specific filename
rclone backend copyid gdrive: FILE-ID ~/data/budget.csv --drive-export-formats csv

# Download as TSV (tab-separated values)
rclone backend copyid gdrive: FILE-ID ~/data/ --drive-export-formats tsv

# Download as XLSX (Excel format, editable)
rclone backend copyid gdrive: FILE-ID ~/data/ --drive-export-formats xlsx

# Download as ODS (LibreOffice Calc, editable)
rclone backend copyid gdrive: FILE-ID ~/data/ --drive-export-formats ods
```

**Download Google Sheets - Complete Examples:**

```bash
# Example: Download budget sheet as CSV
# File ID: 1BxiMVs0XRYVgYb_y_etc_etc
rclone backend copyid gdrive: 1BxiMVs0XRYVgYb_y_etc_etc ./ --drive-export-formats csv

# Example: Download quarterly report sheet as XLSX
# File ID: 1AbCdEfGhIjKlMnOpQrStUvWxYz_abc
rclone backend copyid gdrive: 1AbCdEfGhIjKlMnOpQrStUvWxYz_abc ~/reports/ --drive-export-formats xlsx

# Example: Download data sheet as CSV for data analysis
# File ID: 1XyZ1234567890AbCdEfGhIjKlMnOpQr
rclone backend copyid gdrive: 1XyZ1234567890AbCdEfGhIjKlMnOpQr ~/analysis/data.csv --drive-export-formats csv

# Example: Download sheet as PDF (read-only snapshot)
# File ID: 1BxiMVs0XRYVgYb_y_etc_etc
rclone backend copyid gdrive: 1BxiMVs0XRYVgYb_y_etc_etc ~/reports/ --drive-export-formats pdf

# Example: Get sheet ID from folder and download as CSV
SHEET_ID=$(rclone lsjson gdrive:"Finance" | jq -r '.[] | select(.Name | test("Q1 Budget")) | .ID')
rclone backend copyid gdrive: "$SHEET_ID" ~/data/ --drive-export-formats csv
```

**Google Sheets Format Comparison:**

```bash
# CSV - Universal, plain text, no formatting
rclone backend copyid gdrive: 1BxiMVs0XRYVgYb_y_etc_etc ./ --drive-export-formats csv
# Result: spreadsheet.csv (best for data analysis, imports, version control)

# XLSX - Microsoft Excel, editable, formatted
rclone backend copyid gdrive: 1BxiMVs0XRYVgYb_y_etc_etc ./ --drive-export-formats xlsx
# Result: spreadsheet.xlsx (best for editing, sharing with Excel users)

# TSV - Tab-separated, plain text
rclone backend copyid gdrive: 1BxiMVs0XRYVgYb_y_etc_etc ./ --drive-export-formats tsv
# Result: spreadsheet.tsv (alternative to CSV, better for tabs in data)

# ODS - LibreOffice/OpenOffice format, editable
rclone backend copyid gdrive: 1BxiMVs0XRYVgYb_y_etc_etc ./ --drive-export-formats ods
# Result: spreadsheet.ods (best for LibreOffice/OpenOffice users)

# PDF - Read-only snapshot with formatting
rclone backend copyid gdrive: 1BxiMVs0XRYVgYb_y_etc_etc ./ --drive-export-formats pdf
# Result: spreadsheet.pdf (best for sharing, archival, printing)
```

**Batch Download Multiple Sheets as CSV:**

```bash
# Download first 5 sheets in a folder as CSV
rclone lsjson gdrive:"MyFolder" | \
  jq -r '.[] | select(.MimeType == "application/vnd.google-apps.spreadsheet") | .ID' | \
  head -5 | \
  while read SHEET_ID; do
    rclone backend copyid gdrive: "$SHEET_ID" ~/sheets/ --drive-export-formats csv
  done
```

**Practical Workflow: Download Spreadsheets as CSV:**

```bash
#!/bin/bash

# Find all matching sheets in a folder and download as CSV
echo "Downloading spreadsheets as CSV..."

# Search for sheets by name within target folder
SHEETS=$(rclone lsjson gdrive:"Reports" | jq -c '.[] | select(.Name | test("report"; "i")) | select(.MimeType == "application/vnd.google-apps.spreadsheet")')

# Loop through results and download each as CSV
echo "$SHEETS" | jq -r '"\(.ID)|\(.Name)"' | while IFS='|' read SHEET_ID SHEET_NAME; do
  echo "Downloading: $SHEET_NAME"

  # Get clean filename
  CLEAN_NAME=$(echo "$SHEET_NAME" | sed 's/[^a-zA-Z0-9._-]/_/g')

  # Download as CSV
  rclone backend copyid gdrive: "$SHEET_ID" ~/data/"$CLEAN_NAME".csv --drive-export-formats csv
done

echo "All sheets downloaded as CSV!"
```

**Download File by ID as HTML:**

```bash
# Download as HTML with all styles
rclone backend copyid gdrive: FILE-ID ~/html-docs/ --drive-export-formats html
```

**Download File by ID with Format Priority:**

```bash
# Try multiple formats (choose first compatible one)
# For Docs: md first, then PDF (use "md" not "markdown" with backend copyid)
# For Sheets: CSV first, then XLSX
rclone backend copyid gdrive: FILE-ID ~/downloads/ --drive-export-formats md,csv,pdf
```

**Batch Download Multiple Files by ID in Same Format:**

```bash
# Download first 5 results in a folder as PDF
rclone lsjson gdrive:"MyFolder" | \
  jq -r '.[0:5][] | .ID' | \
  while read FILE_ID; do
    rclone backend copyid gdrive: "$FILE_ID" ~/downloads/ --drive-export-formats pdf
  done
```

**Practical Workflow Example:**

```bash
#!/bin/bash

# Find documents and download as PDF
echo "Finding 2024 documents in Projects folder..."
DOCS=$(rclone lsjson gdrive:"Projects" | jq -c '.[] | select(.Name | test("2024.*report"; "i"))')

# Loop through each result and download as PDF
echo "$DOCS" | jq -r '"\(.ID)|\(.Name)"' | while IFS='|' read FILE_ID FILE_NAME; do
  echo "Downloading: $FILE_NAME"

  # Get clean filename without special characters
  CLEAN_NAME=$(echo "$FILE_NAME" | sed 's/[^a-zA-Z0-9._-]/_/g')

  # Download as PDF
  rclone backend copyid gdrive: "$FILE_ID" ~/exports/"$CLEAN_NAME".pdf --drive-export-formats pdf
done

echo "All documents downloaded as PDF!"
```

**Format Options for Different File Types:**

```bash
# Google Docs → Text Formats
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats pdf       # Read-only
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats docx      # Editable
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats md        # Version control (use "md" not "markdown")
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats html      # Web format
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats txt       # Plain text
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats odt       # LibreOffice
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats rtf       # Legacy format

# Google Sheets → Data Formats
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats csv       # Universal
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats xlsx      # Excel
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats ods       # LibreOffice
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats tsv       # Tab-separated

# Google Slides → Presentation Formats
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats pptx      # PowerPoint
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats odp       # LibreOffice
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats pdf       # Read-only
```

**Key Points for File ID Downloads:**

- ✅ No directory browsing needed - direct by ID
- ✅ Works with all export formats
- ✅ Fast and efficient
- ✅ Can rename on download
- ✅ Preserves original filename with trailing `/`
- ✅ Supports `--dry-run` to preview
- ✅ Supports `--interactive` for confirmation

### Complete Workflow Example

Find and download files efficiently:

```bash
#!/bin/bash

# Step 1: Search for files within target folder
echo "Searching for documents..."
RESULTS=$(rclone lsjson gdrive:"Reports" | jq '.[] | select(.Name | test("2024.*report"; "i"))')

# Step 2: Parse file IDs (jq required: brew install jq)
FILE_ID=$(echo "$RESULTS" | jq -r '.ID' | head -1)
FILENAME=$(echo "$RESULTS" | jq -r '.Name' | head -1)

echo "Found: $FILENAME (ID: $FILE_ID)"

# Step 3: Download using file ID (no directory browsing needed)
rclone backend copyid gdrive: "$FILE_ID" ~/Downloads/"$FILENAME"

echo "Downloaded to ~/Downloads/$FILENAME"
```

### Why This Matters

**Inefficient & Risky:**
```bash
rclone ls gdrive: | grep "filename"        # Lists ALL files on entire drive!
```

**Efficient & Safe:**
```bash
rclone lsjson gdrive:"TargetFolder" | jq '.[] | select(.Name | test("filename"; "i"))'  # Targeted
```

The targeted folder + `lsjson` method:

- ✅ Never traverses or lists the entire drive root unexpectedly
- ✅ Minimal API quota usage
- ✅ Returns structured JSON with IDs and MIME types for reliable scripting
- ✅ Works across all standard rclone versions

## Exporting Google Docs (Multiple Formats)

Google Docs, Sheets, and Slides can't be downloaded directly—they must be exported to standard file formats. Rclone supports multiple export formats.

### Export Formats Overview

| Format      | File Type                | Best For                                    | Extension |
| ----------- | ------------------------ | ------------------------------------------- | --------- |
| **pdf**     | Portable Document        | Read-only archives, sharing, printing       | `.pdf`    |
| **docx**    | Microsoft Word (default) | Editing, Office compatibility               | `.docx`   |
| **markdown** / **md** | Plain text formatting | Version control, README files, publishing | `.md` |
| **html**    | Web format               | Web publishing (unzip after download)       | `.html`   |
| **odt**     | OpenDocument             | LibreOffice/OpenOffice compatibility        | `.odt`    |
| **txt**     | Plain text               | Text extraction, minimal formatting         | `.txt`    |
| **epub**    | E-book format            | E-readers, books                            | `.epub`   |
| **rtf**     | Rich Text Format         | Legacy app compatibility                    | `.rtf`    |

### Downloading with Default Format (PDF - Recommended)

By default, you should use PDF format for archival and compatibility:

```bash
# Download Google Docs as PDF (recommended default)
rclone copy gdrive:"Documents" ~/local-docs --drive-export-formats pdf

# Downloads: "My Document.pdf", "Budget.pdf", etc.
```

If you don't specify `--drive-export-formats`, rclone uses: `docx,xlsx,pptx,svg`

### Downloading with Specific Format

⚠️ **IMPORTANT**: Always specify a limited set of files. Never download the entire drive.

Use `--drive-export-formats` to specify preferred export formats:

```bash
# Download specific folder by name as PDF
rclone copy gdrive:"MyDocuments" ~/backups --drive-export-formats pdf

# Download specific file by name as PDF
rclone copy gdrive:"My Document" ~/context/my-doc.pdf --drive-export-formats pdf

# Download specific folder by ID as PDF (entire folder)
rclone copy gdrive: ./my-pdf-folder --drive-root-folder-id="1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P" --drive-export-formats pdf

# Download folder by ID as Markdown
rclone copy gdrive: ~/markdown-docs --drive-root-folder-id="YOUR_FOLDER_ID" --drive-export-formats markdown

# Download specific folder by name as Markdown
rclone copy gdrive:"ProjectDocs" ~/docs --drive-export-formats markdown

# Download as plain text (specific folder only)
rclone copy gdrive:"Notes" ~/text-only --drive-export-formats txt
```

**Using Folder ID (`--drive-root-folder-id`):**

The `--drive-root-folder-id` flag restricts all operations to a specific folder (by ID), making it safe to download the entire contents:

```bash
# Copy ALL files from a specific folder ID in PDF format
rclone copy gdrive: ./backup --drive-root-folder-id="FOLDER_ID" --drive-export-formats pdf

# This is equivalent to copying the entire folder structure under that folder ID
# Safe because it's limited to a specific folder, not the entire drive
```

### Format Priority with Multiple Options

Specify multiple formats in priority order—rclone chooses the first compatible one. Always limit to specific files or folders:

```bash
# Download specific folder with format priority
# 1. markdown (for docs), 2. csv (for sheets), 3. pdf (fallback)
rclone copy gdrive:"MyDocuments" ~/documents --drive-export-formats markdown,csv,pdf

# Download entire folder by ID with format priority
FOLDER_ID="1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P"
rclone copy gdrive: ~/documents --drive-root-folder-id="$FOLDER_ID" --drive-export-formats markdown,csv,pdf

# Download specific files using lsjson and copyid
FOLDER_NAME="my-folder"
# Find files in folder, then download by ID
rclone lsjson gdrive:"$FOLDER_NAME" | \
  jq -r '.[] | select(.Name | test("report"; "i")) | .ID' | \
  while read FILE_ID; do
    rclone backend copyid gdrive: "$FILE_ID" ~/archive/
  done

# Archive specific folder with format fallback
rclone copy gdrive:"2024-Archive" ~/archive/2024 --drive-export-formats pdf,docx
```

### Export Formats by Document Type

**Google Docs → Documents:**

```bash
# PDF (read-only, universal)
--drive-export-formats pdf

# DOCX (Microsoft Word, editable)
--drive-export-formats docx

# Markdown (version control, minimal formatting)
--drive-export-formats markdown

# HTML (web format, unzip if needed)
--drive-export-formats html

# OpenDocument (LibreOffice)
--drive-export-formats odt

# Plain text (extract text only)
--drive-export-formats txt
```

**Google Sheets → Spreadsheets:**

```bash
# Excel (Microsoft, editable)
--drive-export-formats xlsx

# CSV (plain text table, universal)
--drive-export-formats csv

# OpenDocument (LibreOffice)
--drive-export-formats ods

# Tab-separated values
--drive-export-formats tsv
```

**Google Slides → Presentations:**

```bash
# PowerPoint (Microsoft)
--drive-export-formats pptx

# PDF (read-only slides)
--drive-export-formats pdf

# OpenDocument (LibreOffice)
--drive-export-formats odp
```

### Practical Examples

**Download Entire Folder by ID as PDF:**

```bash
# Export entire folder (by ID) to PDF format
FOLDER_ID="1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P"
rclone copy gdrive: ~/my-pdf-folder --drive-root-folder-id="$FOLDER_ID" --drive-export-formats pdf

# All files in folder become: "Return.pdf", "Receipts.pdf", "Budget.pdf", etc.
```

**Download Specific Folder by Name as PDF:**

```bash
# Export specific folder to PDF
# Only downloads files in "2024-Reports" folder
rclone copy gdrive:"2024-Reports" ~/Backups/Reports-2024-PDF --drive-export-formats pdf

# Files become: "Report.pdf", "Summary.pdf", etc.
```

**Download Specific Document as Markdown:**

```bash
# Export one specific document for version control
rclone copy gdrive:"Project-README" ~/project-docs/ --drive-export-formats markdown

# Creates: Project-README.md (can be tracked in Git)
```

**Download Specific Spreadsheet as CSV:**

```bash
# Export one budget spreadsheet as CSV
rclone copy gdrive:"Q1-Budget" ~/csv-exports/budget-q1.csv --drive-export-formats csv

# Use in any spreadsheet app or data analysis tool
```

**Download Multiple Specific Files by ID:**

```bash
# Find files matching criteria within folder
FOLDER_NAME="2024-Reports"

# Search for PDF files in folder
rclone lsjson gdrive:"$FOLDER_NAME" | jq '.[] | select(.MimeType == "application/pdf")'

# Get first file ID
FILE_ID=$(rclone lsjson gdrive:"$FOLDER_NAME" | jq -r '.[] | select(.MimeType == "application/pdf") | .ID' | head -1)

# Download using ID (no directory browsing)
rclone backend copyid gdrive: "$FILE_ID" ~/downloads/ --drive-export-formats pdf

# For multiple files, loop through results (limit to 5)
rclone lsjson gdrive:"$FOLDER_NAME" | \
  jq -r '.[0:5][] | .ID' | \
  xargs -I {} rclone backend copyid gdrive: {} ~/downloads/ --drive-export-formats pdf
```

**Download Recent Documents (Last 7 Days):**

```bash
# Find and export documents modified in last 7 days from a folder
CUTOFF_DATE=$(date -d '7 days ago' -Iseconds)
FOLDER_NAME="WorkDocs"

rclone lsjson gdrive:"$FOLDER_NAME" | \
  jq -r --arg cutoff "$CUTOFF_DATE" '.[] | select(.ModTime > $cutoff) | .ID' | \
  head -20 | \
  xargs -I {} rclone backend copyid gdrive: {} ~/recent-docs/ --drive-export-formats pdf
```

### Handling HTML Exports

HTML exports can include nested files and styles. They may download as `.zip` files. Always limit to specific folders:

```bash
# Download specific folder as HTML
rclone copy gdrive:"MyDocumentation" ~/html-docs --drive-export-formats html

# Or download entire folder by ID as HTML
FOLDER_ID="your-folder-id"
rclone copy gdrive: ~/html-docs --drive-root-folder-id="$FOLDER_ID" --drive-export-formats html

# If downloaded as .zip, unzip to access content
unzip ~/html-docs/*.zip -d ~/html-docs-extracted/

# View in browser
open ~/html-docs-extracted/index.html
```

### Configuration in rclone.conf

Set default export and import formats in your remote configuration:

```ini
[gdrive]
type = drive
...
export_formats = pdf
import_formats = docx,xlsx,pptx,csv
```

This makes `rclone copy gdrive:"MyFolder" /local/` default to PDF exports, and automatically converts uploaded Office files into native Google Docs/Sheets without specifying flags each time.

⚠️ **Remember**: Always specify the folder or file, never use `gdrive:` alone.

### Importing & Creating Native Google Docs (Uploading)

By default, uploading a `.docx`, `.xlsx`, or `.csv` stores it on Google Drive as a binary file. To automatically convert uploaded files into native, editable Google Docs, Sheets, or Slides, use `--drive-import-formats`:

```bash
# Upload and convert a Word document into a native Google Doc
rclone copy "document.docx" gdrive:"MyFolder" --drive-import-formats docx

# Upload and convert an Excel spreadsheet into a native Google Sheet
rclone copy "budget.xlsx" gdrive:"MyFolder" --drive-import-formats xlsx

# Upload and convert a CSV file into a native Google Sheet
rclone copy "data.csv" gdrive:"MyFolder" --drive-import-formats csv

# Upload multiple formats with automatic conversion
rclone copy ./docs/ gdrive:"MyFolder" --drive-import-formats docx,xlsx,pptx,csv
```

**Key Points for Imported Google Docs:**

- ✅ Converted native files appear with `Size: -1` in rclone listings (like all native Google Docs).
- ✅ Native files open directly in Google Docs/Sheets for online collaborative editing.
- ✅ Optional flag `--drive-allow-import-name-change` allows Google Drive to change the file extension upon import if needed.
- ❌ Do not use `--drive-allow-import-name-change` with `rclone sync` as the altered file extension causes sync to re-upload files repeatedly.

### Important Notes on Google Docs Export

**What Gets Exported:**

- ✅ Google Docs → Documents (docx, pdf, markdown, etc.)
- ✅ Google Sheets → Spreadsheets (xlsx, csv, ods, etc.)
- ✅ Google Slides → Presentations (pptx, pdf, odp, etc.)
- ❌ Google Forms → Cannot be exported (only responses)

**File Names:**

- Rclone appends the appropriate extension automatically
- "My Document" → "My Document.pdf" or "My Document.docx"

**Quality Considerations:**

- **PDF**: Highest fidelity, read-only, universal
- **DOCX**: Fully editable, may lose some advanced formatting
- **Markdown**: Minimal formatting, great for version control
- **HTML**: Full styling, may be complex
- **Plain Text**: Text only, all formatting lost

**Storage Notes:**

- Exported files are created on-the-fly (not stored on Drive)
- No additional Drive storage space used
- Multiple exports of same doc don't consume quota

**Performance:**

- Export happens during download
- Large documents take longer to export
- Use specific format flag for faster transfers

### Quick Reference

⚠️ **Always specify a limited set of files. Never download the entire drive.**

```bash
# PDF (recommended for archival) - specific folder by name
rclone copy gdrive:"MyDocuments" ~/backup --drive-export-formats pdf

# PDF - entire folder by ID
FOLDER_ID="1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P"
rclone copy gdrive: ~/backup --drive-root-folder-id="$FOLDER_ID" --drive-export-formats pdf

# Markdown (version control) - specific document
rclone copy gdrive:"MyDocument" ~/docs --drive-export-formats markdown

# DOCX (editable) - specific folder
rclone copy gdrive:"WorkDocs" ~/local --drive-export-formats docx

# CSV (spreadsheet data) - specific file
rclone copy gdrive:"BudgetSheet" ~/data --drive-export-formats csv

# Multiple formats with priority - specific folder only
rclone copy gdrive:"2024-Archive" ~/archive --drive-export-formats pdf,docx

# Search and download limited results in folder (first 10 files)
FOLDER_NAME="my-folder"
rclone lsjson gdrive:"$FOLDER_NAME" | jq -r '.[0:10][] | .ID' | \
  xargs -I {} rclone backend copyid gdrive: {} ~/downloads/ --drive-export-formats pdf
```

## Configuration Files

Rclone stores configuration in `~/.config/rclone/rclone.conf`.

**View configured remotes (without exposing tokens):**

```bash
rclone listremotes
```

## Important Limitations & Notes

### Rate Limiting

Google Drive enforces rate limits:
- **Transfer rate**: ~2 files per second
- **Download limit**: 10 TiB per day
- **Upload limit**: 750 GiB per day

### Google Docs & Sheets

- Appear as size `-1` in listings
- Cannot be downloaded directly as binary files (use `--drive-export-formats`)

### File Duplication

Google Drive allows multiple files with the same name in the same folder. Use `rclone dedupe` on a specific folder to clean up duplicates:

```bash
rclone dedupe gdrive:"MyFolder" --dedupe-mode interactive
```

## Known Gotchas

### `backend copyid` requires `md` not `markdown` for export format

The `--drive-export-formats markdown` works with `rclone copy` but **fails** with `rclone backend copyid`:

```bash
# FAILS with: "couldn't find MIME type for extension .markdown"
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats markdown

# WORKS
rclone backend copyid gdrive: FILE-ID ./ --drive-export-formats md

# Also WORKS (rclone copy accepts both)
rclone copy gdrive:"MyDoc" ~/docs/ --drive-export-formats markdown
```

Use `md` whenever using `backend copyid`. The `rclone copy` command accepts either `markdown` or `md`.

## Troubleshooting

### "401 Unauthorized" or "403 Insufficient Permission" Error

Re-authenticate or add the `drive` scope using the **`google-oauth`** skill:

```bash
uv run skills/google-oauth/scripts/google_oauth.py status
uv run skills/google-oauth/scripts/google_oauth.py url --scopes drive
# After exchanging the redirect URL:
uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote gdrive
```

### Shared Drive Not Showing Up

`rclone` defaults to "My Drive". To bind a remote to a Google Workspace Shared Drive (Team Drive), use `--shared-drive`:

```bash
uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --list-shared-drives
uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote gdrive --shared-drive "Shared Drive Name"
```

## Next Steps

- See the **`google-oauth`** skill (`skills/google-oauth/SKILL.md`) for OAuth authentication and Shared Drive setup
- See [references/CONFIGURATION_DETAILS.md](references/CONFIGURATION_DETAILS.md) for advanced options
- Check [references/COMMON_WORKFLOWS.md](references/COMMON_WORKFLOWS.md) for practical examples

## Common Commands Cheat Sheet

```bash
# Check installation
rclone version

# Configure Google Drive from google-oauth credentials
uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote gdrive

# List remotes
rclone listremotes

# List top-level Google Drive folders
rclone lsd gdrive:

# Upload/download a specific folder
rclone copy /local gdrive:"MyFolder"

# Monitor quota
rclone about gdrive:
```
