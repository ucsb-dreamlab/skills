# Rclone Google Drive - Common Workflows

## Backup & Sync Workflows

### Simple Backup (One-Way Copy)
Upload your important local folders to Google Drive:

```bash
# Backup entire Documents folder
rclone copy ~/Documents gdrive:Backups/Documents

# Backup with progress
rclone copy --progress ~/Documents gdrive:Backups/Documents

# Backup with log file
rclone copy --log-file=backup.log ~/Documents gdrive:Backups/Documents
```

**Key differences:**
- `copy` - Adds new files, updates changed files, keeps remote files
- `sync` - Makes remote identical to local (DELETES files not in local!)
- `move` - Moves files instead of copying

### Two-Way Sync (Bidirectional)
Keep local and remote folders synchronized:

```bash
# Sync local to remote (remote becomes copy of local)
rclone sync ~/Documents gdrive:Documents

# Sync remote to local (local becomes copy of remote)
rclone sync gdrive:Documents ~/Documents

# Dry run to preview what would happen
rclone sync --dry-run ~/Documents gdrive:Documents
```

⚠️ **WARNING**: `sync` deletes files! Use `--dry-run` first to preview changes.

### Incremental Backup (Only New/Changed Files)
```bash
# After first backup, only updated files are transferred
rclone copy --verbose ~/Documents gdrive:Backups/Documents

# Show what changed (without uploading)
rclone check ~/Documents gdrive:Backups/Documents
```

### Smart Backup Strategy
```bash
#!/bin/bash

# Define backup locations
LOCAL_PATH="$HOME/Documents"
REMOTE_PATH="gdrive:Backups/Documents"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="backup-$TIMESTAMP.log"

# Create dated backup
rclone copy \
  --progress \
  --log-file="$LOG_FILE" \
  --exclude=".*" \
  --exclude="*.tmp" \
  "$LOCAL_PATH" "$REMOTE_PATH"

echo "Backup complete: $REMOTE_PATH"
echo "Log saved: $LOG_FILE"
```

## Download & Recovery Workflows

### Download a Specific Google Drive Folder
```bash
# Download a specific folder
rclone copy gdrive:MyFolder ~/Downloads/MyFolder

# Or download a specific folder by ID
rclone copy gdrive: ~/Downloads/MyFolder --drive-root-folder-id="FOLDER_ID"

# Show what will be downloaded (dry-run)
rclone copy --dry-run gdrive:MyFolder ~/Downloads/MyFolder
```

### Selective Download (Large Folders)
```bash
# Only download PDFs
rclone copy --include="*.pdf" gdrive:Documents ~/Downloads/

# Only download files smaller than 100MB
rclone copy --max-size=100M gdrive:Documents ~/Downloads/

# Download only recent files (modified in last 7 days)
rclone copy --min-age=0 --max-age=7d gdrive:Documents ~/Downloads/
```

### Recovery from Trash
```bash
# Google Drive trash is automatically cleaned after 30 days
# Use this to recover recent deletions

# First, check what's in trash
rclone lsd gdrive:/.Trash

# Copy back from trash
rclone copy gdrive:/.Trash ~/recovered_files/
```

**Note**: Permanent deletes cannot be recovered. Always maintain backups.

## Organization & Management Workflows

### Move Files Between Folders
```bash
# Move locally first, then sync
# Or use rclone move to move directly in Google Drive
rclone move gdrive:OldFolder gdrive:NewFolder

# Rename file
rclone move gdrive:OldName.txt gdrive:NewName.txt
```

### Organize by Extension (Scoped to a Folder)
```bash
# Copy all PDFs from a folder to a dedicated folder
rclone copy --include="*.pdf" gdrive:MyFolder gdrive:PDFs_Only

# Copy images from a folder
rclone copy --include="*.{jpg,png,gif}" gdrive:MyFolder gdrive:Images_Only
```

### Clean Up Duplicates (Scoped to a Folder)
```bash
# Find and remove duplicate files in a folder
rclone dedupe gdrive:MyFolder

# Interactive mode (choose which to keep)
rclone dedupe --dedupe-mode interactive gdrive:MyFolder

# Auto-remove, keeping newest version
rclone dedupe --dedupe-mode newest gdrive:MyFolder

# Auto-remove, keeping oldest version
rclone dedupe --dedupe-mode oldest gdrive:MyFolder
```

### Archive Old Files
```bash
# Copy old files to archive folder (dry run first!)
rclone copy \
  --max-age=365d \
  --dry-run \
  gdrive:Documents \
  gdrive:Archive/Documents-2024

# Then actually move them
rclone move \
  --max-age=365d \
  gdrive:Documents \
  gdrive:Archive/Documents-2024
```

## Monitoring & Verification Workflows

### Check Sync Status
```bash
# Compare local and remote (no action taken)
rclone check ~/Documents gdrive:Backups/Documents

# Verbose comparison showing what differs
rclone check -v ~/Documents gdrive:Backups/Documents

# List files that differ
rclone check -vv ~/Documents gdrive:Backups/Documents
```

### Monitor Google Drive Quota
```bash
# Check account quota and usage
rclone about gdrive:

# Get just the used space
rclone about gdrive: | grep Used

# Monitor in real-time during transfer
watch rclone about gdrive:
```

### Verify File Integrity
```bash
# Check all file hashes
rclone check --download ~/Documents gdrive:Backup

# Compare specific file
rclone check ~/Documents/important.txt gdrive:Backup/important.txt

# List mismatches
rclone check -vv ~/Documents gdrive:Backup | grep -i mismatch
```

### List Files with Sizes (Scoped to a Folder)
```bash
# Show files in a specific folder
rclone ls gdrive:MyFolder

# Show top-level folders only
rclone lsd gdrive:

# Show with human-readable sizes in a specific folder
rclone lsf -R -h gdrive:MyFolder | sort
```

## Performance & Bandwidth Workflows

### Limited Bandwidth Backup
```bash
# Limit to 5MB/s
rclone copy --bwlimit=5M ~/Documents gdrive:Backups

# Limit to 10% of available bandwidth
rclone copy --bwlimit=10% ~/Documents gdrive:Backups

# No bandwidth limit (default)
rclone copy ~/Documents gdrive:Backups
```

### Fast Sync (Skip Hashing)
```bash
# Skip hash verification (faster but less safe)
rclone copy --no-check-dest ~/Documents gdrive:Backups

# Use size/modtime instead of hash
rclone copy --use-mmap ~/Documents gdrive:Backups
```

### Parallel Transfers
```bash
# 4 parallel transfers (default)
rclone copy --transfers=4 ~/Documents gdrive:Backups

# More parallel for small files
rclone copy --transfers=8 ~/Documents gdrive:Backups

# Single transfer (slower, more reliable for network issues)
rclone copy --transfers=1 ~/Documents gdrive:Backups
```

### Monitor Transfer Progress
```bash
# Show live progress with stats
rclone copy --progress --stats=10s ~/Documents gdrive:Backups

# Detailed statistics every 5 seconds
rclone copy --progress --stats=5s -vv ~/Documents gdrive:Backups

# Peak speed monitoring
rclone copy --stats=1s ~/Documents gdrive:Backups
```

## Automation Workflows

### Daily Backup Script
```bash
#!/bin/bash

# config
LOCAL_DOCS="$HOME/Documents"
REMOTE_DOCS="gdrive:Backups/Documents"
LOG_DIR="$HOME/.rclone-logs"

# Create log directory
mkdir -p "$LOG_DIR"

# Run backup
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$LOG_DIR/backup-$TIMESTAMP.log"

rclone copy \
  --progress \
  --log-file="$LOG_FILE" \
  --exclude=".*" \
  --exclude=".DS_Store" \
  "$LOCAL_DOCS" "$REMOTE_DOCS"

# Check for errors
if [ $? -eq 0 ]; then
  echo "✅ Backup successful: $TIMESTAMP" >> "$LOG_DIR/backup.log"
else
  echo "❌ Backup failed: $TIMESTAMP" >> "$LOG_DIR/backup.log"
fi
```

### Scheduled Daily Backup (macOS)
```bash
# Save script as ~/backup-gdrive.sh and make executable

# Create LaunchAgent configuration
cat > ~/Library/LaunchAgents/com.backup.gdrive.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.backup.gdrive</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/your-username/backup-gdrive.sh</string>
  </array>
  <key>StartInterval</key>
  <integer>86400</integer> <!-- Run daily (86400 seconds) -->
  <key>StandardErrorPath</key>
  <string>/tmp/backup-gdrive.err</string>
  <key>StandardOutPath</key>
  <string>/tmp/backup-gdrive.log</string>
</dict>
</plist>
EOF

# Load the schedule
launchctl load ~/Library/LaunchAgents/com.backup.gdrive.plist
```

### Scheduled Daily Backup (Linux with Cron)
```bash
# Edit crontab
crontab -e

# Add line for daily 2 AM backup
0 2 * * * /home/user/backup-gdrive.sh >> /home/user/backup.log 2>&1

# Verify
crontab -l
```

## Troubleshooting Workflows

### Diagnose Connection Issues
```bash
# Test basic connectivity
rclone about gdrive:

# Verbose connection test
rclone -vv about gdrive:

# Test specific folder
rclone ls -v gdrive:TestFolder

# Debug HTTP requests
rclone -vv --dump requests copy --dry-run ~/test gdrive:test
```

### Recover from Interrupted Transfer
```bash
# Rclone automatically resumes most operations
# Just run the same command again:
rclone copy ~/Documents gdrive:Backups/Documents

# Force resume with retry limit
rclone copy --retries=10 ~/Documents gdrive:Backups/Documents
```

### Fix Authentication Issues
```bash
# Check saved credentials and scopes via the google_oauth skill
uv run skills/google_oauth/scripts/google_oauth.py status

# Re-authenticate with drive scope and update the rclone remote
uv run skills/google_oauth/scripts/google_oauth.py url --scopes drive
uv run skills/google_oauth/scripts/google_oauth.py exchange '<REDIRECT_URL>'
uv run skills/google_oauth/scripts/google_oauth.py configure-rclone --remote gdrive
```

### Clear Cache and Reset
```bash
# Delete the remote and re-create from saved credentials
rclone config delete gdrive
uv run skills/google_oauth/scripts/google_oauth.py configure-rclone --remote gdrive
```

## Advanced Workflows

### Mirror Folder Structure Locally
```bash
# Copy a specific folder's directory structure (no files)
rclone copy --max-size=0 gdrive:MyFolder ~/MyFolderStructure
```

### Incremental Backups with Dates
```bash
#!/bin/bash

# Create timestamped backup
DATE=$(date +%Y-%m-%d)
LOCAL_PATH="$HOME/Documents"
REMOTE_BASE="gdrive:Backups"

rclone copy \
  --progress \
  "$LOCAL_PATH" \
  "$REMOTE_BASE/Documents-$DATE"

echo "Backup created: Documents-$DATE"
```

### Filter-Based Selective Sync
```bash
# Exclude system files
rclone copy \
  --exclude=".*" \
  --exclude=".DS_Store" \
  --exclude="Thumbs.db" \
  ~/Documents gdrive:Backups

# Include only specific extensions
rclone copy \
  --include="*.{pdf,docx,xlsx}" \
  ~/Documents gdrive:Backups

# Exclude based on size
rclone copy \
  --max-size=1G \
  ~/Documents gdrive:Backups
```

### Compare Multiple Locations
```bash
# Verify backup matches source
rclone check ~/Documents gdrive:Backups/Documents

# Find orphaned files on remote
rclone check gdrive:Backups/Documents ~/Documents

# List only different files
rclone check -vv ~/Documents gdrive:Backups/Documents | grep -E "^-"
```
