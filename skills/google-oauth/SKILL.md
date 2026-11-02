---
name: google-oauth
description: Authenticate with Google OAuth 2.0 in a DREAM Lab Coder remote workspace using ~/.config/dreamlab/google_client.json and uv/Python for arbitrary scopes (Drive, Sheets, Docs, Calendar, Gmail, etc.). Saves unified Application Default Credentials to ~/.config/gcloud/application_default_credentials.json and configures rclone.
---

# Google OAuth 2.0 Authentication (DREAM Lab Coder Remote Workspace)

Use this skill in a **DREAM Lab Coder remote workspace** to authenticate with Google services (Drive, Sheets, Docs, Calendar, Gmail, etc.) with arbitrary OAuth scopes using the pre-provisioned workspace client secret (`~/.config/dreamlab/google_client.json`) and `uv` (Python), without requiring `gcloud` CLI or a local browser on the VM.

## Standard File Locations (DREAM Lab Coder Remote Workspace)

1. **OAuth Client Secret (Input):**
   `~/.config/dreamlab/google_client.json`
   *(Pre-provisioned in DREAM Lab Coder remote workspaces; Google Cloud OAuth 2.0 Web or Installed App JSON containing `client_id`, `client_secret`, and `redirect_uris` such as `https://dreamlab.ucsb.edu/callback.html`.)*

2. **Saved User Credential (Output):**
   `~/.config/gcloud/application_default_credentials.json` (`0600` permissions)
   The helper script writes a unified JSON format to Google's standard **Application Default Credentials (ADC)** path so it works across the widest range of tools:
   - **`google-auth` / `google-api-python-client` / `gspread` / Google Cloud SDKs** auto-discover it via `google.auth.default()` with zero configuration.
   - **`Credentials.from_authorized_user_file()`** can load it directly.
   - **`rclone`** can import the token directly without requiring a second browser login.

---

## Step 1: Authenticate with Google (Any Scopes)

Run the bundled `scripts/google_oauth.py` script via `uv run` in two stateless steps (no background server or `tmux` needed):

### 1. Generate the Consent URL

Pass one or more scope aliases (`drive`, `drive.readonly`, `drive.file`, `spreadsheets`, `documents`, `calendar`, `calendar.readonly`, `gmail.readonly`, `gmail.compose`, `gmail.modify`, `gmail.send`) or full `https://www.googleapis.com/auth/...` URLs:

```bash
uv run scripts/google_oauth.py url --scopes drive
```

*(Example with multiple services)*:
```bash
uv run scripts/google_oauth.py url --scopes drive calendar.readonly gmail.readonly
```

**Scope Accumulation (Incremental Auth):**
- By default, `url` merges any scopes already present in `~/.config/gcloud/application_default_credentials.json` with your newly requested `--scopes` AND passes `include_granted_scopes="true"`, printing out both the existing and newly requested scopes.
- Pass `--replace-scopes --no-include-granted-scopes` if you want to discard previously granted scopes and request only the specified scopes.
- Run `uv run scripts/google_oauth.py status` at any time to inspect the currently saved credential and its full list of granted scopes.

### 2. Have the User Authorize in Their Browser

Give the printed URL to the user and instruct them to:
1. Open the link in their browser, sign in, and click **Allow**.
2. Their browser will redirect to `https://dreamlab.ucsb.edu/callback.html?state=...&code=...` (or `http://127.0.0.1:53682/?...` if using a legacy Desktop client).
3. Click **Copy Callback URL** on the callback page (or copy the full URL from the browser's address bar) and paste it back into chat.

*(Never fetch or open the authorization URL yourself.)*

### 3. Exchange the Redirect URL for Credentials

```bash
uv run scripts/google_oauth.py exchange 'PASTE_REDIRECT_URL_HERE'
```

This saves the unified credential to `~/.config/gcloud/application_default_credentials.json` (`0600`) and prints the full list of granted scopes returned by Google on the token.

---

## Step 2: Configure `rclone` Using the Saved Credential

If the token includes a Drive scope (`drive`, `drive.readonly`, or `drive.file`), configure `rclone` directly from `~/.config/gcloud/application_default_credentials.json` without a second OAuth prompt:

```bash
# Install rclone if needed
which rclone >/dev/null || (curl -fsSL https://rclone.org/install.sh | sudo bash)

# Create/update the 'gdrive:' remote non-interactively (My Drive)
uv run scripts/google_oauth.py configure-rclone --remote gdrive

# Or list and bind to a Shared Drive (Team Drive) by name or ID:
uv run scripts/google_oauth.py configure-rclone --list-shared-drives
uv run scripts/google_oauth.py configure-rclone --remote gdrive --shared-drive "Carpentry"

# Verify access
rclone lsd gdrive:
```

*(Equivalent manual `rclone` command using `jq`)*:
```bash
ADC=~/.config/gcloud/application_default_credentials.json
rclone config create gdrive drive \
  client_id "$(jq -r .client_id "$ADC")" \
  client_secret "$(jq -r .client_secret "$ADC")" \
  token "$(jq -c '{access_token, token_type, refresh_token, expiry}' "$ADC")" \
  --non-interactive
chmod 600 ~/.config/rclone/rclone.conf
```

---

## Step 3: Using the Credentials in Python (`uv`)

Because the credentials are stored at Google's standard ADC path (`~/.config/gcloud/application_default_credentials.json`), Python libraries find them automatically:

```python
# /// script
# dependencies = [
#   "google-auth",
#   "google-api-python-client",
#   "gspread",
# ]
# ///
import google.auth
from googleapiclient.discovery import build
import gspread

# 1. google-api-python-client auto-discovers Application Default Credentials:
drive = build("drive", "v3")
docs = build("docs", "v1")
calendar = build("calendar", "v3")
gmail = build("gmail", "v1")

# 2. gspread (Google Sheets):
creds, _ = google.auth.default()
gc = gspread.authorize(creds)
```

---

## Revoking & Re-authenticating

To revoke the token with Google, delete `~/.config/gcloud/application_default_credentials.json`, and remove the `rclone` remote:

```bash
uv run scripts/google_oauth.py revoke
rclone config delete gdrive 2>/dev/null || true
```
