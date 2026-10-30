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
| `skip_gdocs` | Skip Google Docs in transfers | `false` |
| `skip_shortcuts` | Skip shortcut links | `false` |
| `team_drive` | Shared Drive (Team Drive) ID | empty (My Drive) |
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

### Token Expired or Missing `drive` Scope
**Symptom**: `401 Unauthorized` or `403 Insufficient Permission`

**Fix**: Re-authenticate and update `rclone` via the **`google_oauth`** skill:
```bash
uv run skills/google_oauth/scripts/google_oauth.py status
uv run skills/google_oauth/scripts/google_oauth.py url --scopes drive
uv run skills/google_oauth/scripts/google_oauth.py exchange '<REDIRECT_URL>'
uv run skills/google_oauth/scripts/google_oauth.py configure-rclone --remote gdrive
```

### Shared Drive Access
**Symptom**: Shared Drive files do not appear in `gdrive:`

**Fix**: Bind the remote (or a dedicated remote) to the Shared Drive using `--shared-drive`:
```bash
uv run skills/google_oauth/scripts/google_oauth.py configure-rclone --list-shared-drives
uv run skills/google_oauth/scripts/google_oauth.py configure-rclone --remote gdrive --shared-drive "Shared Drive Name"
```
This sets `team_drive = <DRIVE_ID>` in `~/.config/rclone/rclone.conf`.

## Multiple Remotes

Configure multiple Google Drive remotes (e.g., My Drive plus one or more Shared Drives) from the same credential:

```bash
uv run skills/google_oauth/scripts/google_oauth.py configure-rclone --remote mydrive
uv run skills/google_oauth/scripts/google_oauth.py configure-rclone --remote carpentry --shared-drive "Carpentry"
```

Use them independently:
```bash
rclone lsd mydrive:
rclone lsd carpentry:
```

## Advanced Options

### Skip Google Docs
Google Docs can't be downloaded normally. Skip them:
```bash
rclone copy --exclude="**" gdrive: /local/backup
# Or configure in rclone.conf:
skip_gdocs = true
```

### Deduplicate Files
If a Google Drive folder has duplicate filenames:
```bash
# Interactive deduplication on a specific folder
rclone dedupe gdrive:"MyFolder" --dedupe-mode interactive

# Auto mode (keeps newest) on a specific folder
rclone dedupe gdrive:"MyFolder" --dedupe-mode newest
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

## Structured File Metadata & Search (`rclone lsjson` + `jq`)

*(Note: `rclone backend query` is not supported by standard rclone Google Drive backends. Use `rclone lsjson` scoped to a specific folder instead.)*

```bash
# List JSON metadata (ID, Name, MimeType, ModTime, Size) in a folder
rclone lsjson gdrive:"MyFolder"

# Recursive search within a specific folder
rclone lsjson -R gdrive:"MyFolder" | jq '.[] | select(.Name | test("invoice"; "i"))'

# Extract ID and Name for matching files
rclone lsjson gdrive:"MyFolder" | jq -r '.[] | select(.MimeType == "application/pdf") | "\(.ID) \(.Name)"'

# Combine with backend copyid to download directly by ID
FILE_ID=$(rclone lsjson gdrive:"MyFolder" | jq -r '.[] | select(.Name == "target.pdf") | .ID' | head -1)
rclone backend copyid gdrive: "$FILE_ID" ~/Downloads/target.pdf
```

## Reference Links

- [Rclone Official Google Drive Documentation](https://rclone.org/drive/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Workspace Admin Console](https://admin.google.com/)
- [Rclone Command Reference](https://rclone.org/commands/)
