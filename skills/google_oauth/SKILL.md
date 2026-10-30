---
name: google_oauth
description: Authenticate with Google OAuth 2.0 in a remote workspace using ~/.config/dreamlab/google_client.json and uv/Python for arbitrary scopes (Drive, Sheets, Docs, Calendar, Gmail, etc.). Saves unified Application Default Credentials to ~/.config/gcloud/application_default_credentials.json and configures rclone.
---

# Google OAuth 2.0 Authentication

Use this skill to authenticate with Google services (Drive, Sheets, Docs, Calendar, Gmail, etc.) with arbitrary OAuth scopes in a remote workspace where `uv` (Python) is available and `gcloud` CLI is not required.

## Standard File Locations

1. **OAuth Client Secret (Input):**
   `~/.config/dreamlab/google_client.json`
   *(Google Cloud OAuth 2.0 "Desktop / Installed App" JSON containing `client_id` and `client_secret`.)*

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

Pass one or more scope aliases (`drive`, `drive.readonly`, `drive.file`, `spreadsheets`, `documents`, `calendar`, `calendar.readonly`, `gmail.readonly`, `gmail.modify`) or full `https://www.googleapis.com/auth/...` URLs:

```bash
uv run scripts/google_oauth.py url --scopes drive
```

*(Example with multiple services)*:
```bash
uv run scripts/google_oauth.py url --scopes drive calendar.readonly gmail.readonly
```

### 2. Have the User Authorize in Their Browser

Give the printed URL to the user and instruct them to:
1. Open the link in their browser, sign in, and click **Allow**.
2. Their browser will redirect to `http://127.0.0.1:53682/?state=...&code=...` and show **"This site can't be reached"** (expected, since `127.0.0.1` is the user's laptop rather than the remote workspace).
3. Copy that full `http://127.0.0.1:53682/...` URL from the browser's address bar and paste it back into chat.

*(Never fetch or open the authorization URL yourself.)*

### 3. Exchange the Redirect URL for Credentials

```bash
uv run scripts/google_oauth.py exchange 'PASTE_REDIRECT_URL_HERE'
```

This saves the unified credential to `~/.config/gcloud/application_default_credentials.json` (`0600`).

---

## Step 2: Configure `rclone` Using the Saved Credential

If the token includes a Drive scope (`drive`, `drive.readonly`, or `drive.file`), configure `rclone` directly from `~/.config/gcloud/application_default_credentials.json` without a second OAuth prompt:

```bash
# Install rclone if needed
which rclone >/dev/null || (curl -fsSL https://rclone.org/install.sh | sudo bash)

# Create/update the 'gdrive:' remote non-interactively
uv run scripts/google_oauth.py configure-rclone --remote gdrive

# Verify access
rclone about gdrive:
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
