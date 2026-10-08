# Rclone Google Drive - Advanced Configuration Details

## Configuration File Locations

```
Linux/macOS:  ~/.config/rclone/rclone.conf
Windows:      %APPDATA%\rclone\rclone.conf
```

## Configuration File Structure

```ini
[gdrive]
type = drive
client_id = your-client-id.apps.googleusercontent.com
client_secret = your-client-secret
scope = drive
token = {"access_token":"...", "token_type":"Bearer", ...}
root_folder_id = [optional folder ID to restrict access]
```

## All OAuth2 Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `client_id` | OAuth2 Client ID | rclone default (shared rate limit) |
| `client_secret` | OAuth2 Client Secret | rclone default |
| `scope` | Permission scope | `drive` |
| `root_folder_id` | Limit to specific folder (get from URL) | root of Drive |
| `export_formats` | Preferred download formats for Google Docs | `docx,xlsx,pptx,svg` |
| `import_formats` | Preferred formats to auto-convert to Google Docs on upload | empty (upload as binary) |
| `allow_import_name_change` | Allow file extension to change on doc import | `false` |
| `use_trash` | Use trash instead of permanent delete | `true` |
| `skip_gdocs` | Skip Google Docs in transfers | `true` |
| `skip_shortcuts` | Skip shortcut links | `false` |
| `shared_drive_support` | Enable shared drives | `false` |
| `chunk_size` | Upload chunk size | `8Mi` |
| `upload_cutoff` | Size threshold for resumable uploads | `8Mi` |
| `keep_revision_names` | Keep file revision history | `false` |
| `list_chunk` | Items per list request | `1000` |
| `impersonate` | Service account: user to impersonate | empty |

## Scope Definitions

### Full Access (Default)
```
drive
```
- Read/write all files in Drive
- Recommended for personal accounts
- Cannot access Application Data folder

### Read-Only
```
drive.readonly
```
- Read-only access to all files
- Safe for backup/sync scenarios where you won't modify Drive
- Cannot upload or delete files

### Rclone-Created Files Only
```
drive.file
```
- Access only to files created by rclone
- Useful for limiting permissions in shared accounts
- Good for application-specific storage

### Private Rclone Folder
```
drive.appfolder
```
- Private folder for rclone (hidden from user)
- Isolated storage for each application
- Useful for application data isolation

### Metadata Only
```
drive.metadata.readonly
```
- File names and metadata only
- Cannot download files
- Useful for indexing/cataloging

## Root Folder ID Configuration

Restrict rclone to a specific folder:

1. Open the folder in Google Drive web interface
2. Look at the URL: `https://drive.google.com/drive/folders/FOLDER-ID-HERE`
3. Copy the folder ID
4. Run `rclone config edit`
5. Add the line: `root_folder_id = FOLDER-ID-HERE`

This limits all operations to that folder and subfolders.

## Service Account Configuration

For unattended/automated access:

### Full Configuration Example
```ini
[gdrive-service]
type = drive
service_account_file = /path/to/service-account.json
```

Or embed the JSON directly:
```ini
[gdrive-service]
type = drive
service_account_string = {
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  ...
}
```

### Workspace (G Suite) Domain-Wide Delegation

For service accounts accessing user drives in a Workspace domain:

1. Get the service account email: `service-account@project.iam.gserviceaccount.com`
2. In Google Workspace Admin Console:
   - Security → API Controls → Domain-wide Delegation
   - Add scope: `https://www.googleapis.com/auth/drive`
3. In rclone config, add:
   ```ini
   impersonate = user@yourdomain.com
   ```

## Rate Limit Configuration

### Default Limits
- Transfer rate: ~2 files/second
- Download: 10 TiB/day
- Upload: 750 GiB/day
- All users share rclone's default client

### With Your Own Client ID
- Same rate limits apply
- But not shared with other rclone users
- Better performance when running multiple instances

### Rclone Configuration Options to Manage Limits
```bash
# Limit transfers to 1 file/second
rclone copy --transfers=1 /local gdrive:backup

# Limit bandwidth to 10MB/s
rclone copy --bwlimit=10M /local gdrive:backup

# Check current limits
rclone about gdrive:
```

## Environment Variables

Set rclone behavior via environment variables:

```bash
# Use custom config location
export RCLONE_CONFIG=~/.config/rclone/custom.conf

# Enable debug logging
export RCLONE_VERBOSE=1

# Set default remote
export RCLONE_CONFIG_GDRIVE_TOKEN='{"access_token":"..."}'
```

## Troubleshooting Configuration Issues

### Token Expired
**Symptom**: `401 Unauthorized`

**Fix**: Re-authenticate
```bash
rclone config edit
# Find the remote and delete it, then reconfigure
```

### Wrong Permissions
**Symptom**: `403 Forbidden` or `permission denied`

**Fix**: Reconfigure with correct scope
```bash
rclone config edit
# Change scope to 'drive' (full access)
```

### Service Account No Access
**Symptom**: Service account can't see shared drives

**Fix**: Enable in config
```ini
shared_drive_support = true
```

### Token Cache Issues
**Symptom**: Changes to credentials don't take effect

**Fix**: Clear token cache
```bash
# Edit config directly
nano ~/.config/rclone/rclone.conf
# Remove the 'token' line for that remote
```

## Creating Your Own Google API Credentials

To avoid shared rate limiting:

### Step 1: Create Project
1. Visit https://console.cloud.google.com/
2. Click "Select a Project" → "New Project"
3. Name it (e.g., "rclone-backup")
4. Click "Create"

### Step 2: Enable Google Drive API
1. Search for "Google Drive API"
2. Click result
3. Click "Enable"

### Step 3: Create OAuth Credentials
1. Go to "Credentials" (left sidebar)
2. Click "Create Credentials" → "OAuth 2.0 Client ID"
3. Application type: "Desktop application"
4. Click "Create"
5. Note the Client ID and Secret

### Step 4: Configure OAuth Consent Screen
1. Go to "OAuth consent screen" (left sidebar)
2. User Type: "External"
3. Click "Create"
4. Fill in app name, user support email
5. Add scopes: search "Google Drive API"
   - Select: `drive`, `drive.readonly`, `drive.appfolder`, etc.
6. Add test users (your email)
7. Click "Save and Continue"

### Step 5: Use in Rclone
```bash
rclone config
# When prompted for Client ID/Secret, paste your credentials
```

## Multiple Remotes

Configure multiple Google Drive accounts:

```ini
[personal]
type = drive
client_id = personal-id.apps.googleusercontent.com
token = {...}

[work]
type = drive
client_id = work-id.apps.googleusercontent.com
token = {...}

[backup]
type = drive
root_folder_id = FOLDER-ID
token = {...}
```

Use them independently:
```bash
rclone ls personal:
rclone ls work:
rclone ls backup:
```

Or in rclone filters/scripts by specifying the remote name.

## Advanced Options

### Skip Google Docs
Google Docs can't be downloaded normally. Skip them:
```bash
rclone copy --exclude="**" gdrive: /local/backup
# Or configure in rclone.conf:
skip_gdocs = true
```

### Deduplicate Files
If Google Drive has duplicates:
```bash
# Interactive deduplication
rclone dedupe gdrive:

# Auto mode (keeps newest)
rclone dedupe --dedupe=newest gdrive:
```

### Verify Transfer Integrity
```bash
# Compare hashes
rclone check /local gdrive:backup

# Verbose comparison
rclone check -vv /local gdrive:backup
```

### Resume Interrupted Transfers
Rclone automatically resumes many operations. Force resumption:
```bash
rclone copy --retries=5 /local gdrive:backup
```

## Performance Tuning

```bash
# More concurrent transfers (up to 8-10 for Google Drive)
rclone copy --transfers=4 /local gdrive:backup

# Larger chunks (16MB-100MB)
rclone copy --drive-chunk-size=50M /local gdrive:backup

# Skip hash verification (faster)
rclone copy --no-check-dest /local gdrive:backup

# Monitor progress
rclone copy --progress --stats=10s /local gdrive:backup
```

## Monitoring and Logging

### Enable Debug Logging
```bash
# Verbose output
rclone -v copy /local gdrive:backup

# Very verbose (debug level)
rclone -vv copy /local gdrive:backup

# Log to file
rclone copy --log-file=rclone.log /local gdrive:backup

# Debug specific issues
rclone -vv --dump headers copy /local gdrive:backup
```

### Monitor Transfers
```bash
# Show live statistics
rclone copy --progress --stats=5s /local gdrive:backup

# Check transfer rate
rclone copy --bwlimit=10M --progress /local gdrive:backup
```

## Backend Query Command - Efficient File Searching

The `rclone backend query` command searches Google Drive without listing the entire drive. Uses Google Drive's native search language.

### Command Syntax

```bash
rclone backend query remote: "query-expression" [options]
```

### Available Flags

```text
-n, --dry-run              Do a trial run with no permanent changes
-i, --interactive          Enable interactive mode
-v, --verbose              Print lots more stuff (repeat for more)
--json                     Always output in JSON format (default)
-o, --option NAME=VALUE    Pass option to backend
```

### Query Expressions

Query uses Google Drive Search operators:

```bash
# Name matching
"name = 'exact-filename.txt'"
"name contains 'partial'"

# MIME type filtering
"mimeType = 'application/pdf'"
"mimeType contains 'spreadsheet'"

# Parent folder
"'FOLDER-ID' in parents"
"'FOLDER-ID' in parents and name contains 'invoice'"

# Trash status
"trashed = false"
"trashed = true"

# Owner/sharing
"owners contains 'user@example.com'"
"sharedWithMe = true"

# Size filtering
"fileSize > 1000000"
"fileSize < 10000000"

# Date filtering
"modifiedTime > '2024-01-01T00:00:00'"
"createdTime < '2025-01-01T00:00:00'"

# Logical operators
"(name contains 'report') and (mimeType = 'application/pdf')"
"(name contains '2024' or name contains '2025') and not trashed"
```

### Output Format

Results are returned as JSON array with file metadata:

```json
[
  {
    "createdTime": "2024-01-15T10:30:00.000Z",
    "id": "1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P",
    "md5Checksum": "abc123...",
    "mimeType": "application/pdf",
    "modifiedTime": "2024-02-10T15:45:00.000Z",
    "name": "annual-report-2024.pdf",
    "parents": ["PARENT-FOLDER-ID"],
    "sha1Checksum": "def456...",
    "size": "2500000",
    "webViewLink": "https://drive.google.com/file/d/.../view"
  }
]
```

### Limiting Results

Since `--limit` flag is not available, limit results after retrieval:

```bash
# First 10 results using jq
rclone backend query gdrive: "name contains 'invoice'" | jq '.[0:10]'

# First 20 results
rclone backend query gdrive: "name contains 'receipt'" | jq '.[0:20]'

# First result only
rclone backend query gdrive: "name = 'specific-file.pdf'" | jq '.[0]'

# Extract just file IDs (requires jq)
rclone backend query gdrive: "name contains 'report'" | jq -r '.[].id'

# Extract names and IDs
rclone backend query gdrive: "name contains 'document'" | jq -r '.[] | "\(.id) \(.name)"'

# Count results
rclone backend query gdrive: "mimeType = 'application/pdf'" | jq 'length'

# Using head command (first 10 JSON lines, not entries)
rclone backend query gdrive: "name contains 'file'" | head -10
```

### Practical Examples

```bash
# Find all PDFs in a folder
rclone backend query gdrive: "'FOLDER-ID' in parents and mimeType = 'application/pdf'"

# Find recent modifications (last 7 days)
rclone backend query gdrive: "modifiedTime > '$(date -d '7 days ago' -Iseconds)' and trashed = false"

# Find large files (over 100MB)
rclone backend query gdrive: "fileSize > 104857600"

# Find files shared with you
rclone backend query gdrive: "sharedWithMe = true and trashed = false"

# Find duplicates (same name in same folder)
# Note: This requires parsing and comparing results with jq

# Count PDFs in Drive
rclone backend query gdrive: "mimeType = 'application/pdf'" | jq 'length'
```

### Combining with copyid/moveid

```bash
# Get file ID from query
FILE_ID=$(rclone backend query gdrive: "name = 'target.pdf'" | jq -r '.[0].id')

# Use ID for direct copy (no directory browsing)
rclone backend copyid gdrive: "$FILE_ID" ~/Downloads/target.pdf
```

### Important Notes

- Queries must be properly quoted (use double quotes, escape internal quotes)
- Results are JSON by default; `--json` flag is implicit
- Query language follows [Google Drive API search terms](https://developers.google.com/drive/api/guides/ref-search-terms)
- No recursion needed; search is performed server-side
- Much faster and more efficient than listing entire Drive

## Reference Links

- [Rclone Official Google Drive Documentation](https://rclone.org/drive/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Workspace Admin Console](https://admin.google.com/)
- [Rclone Command Reference](https://rclone.org/commands/)
