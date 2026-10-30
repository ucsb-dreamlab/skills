#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "google-auth",
#   "google-auth-oauthlib",
#   "requests",
# ]
# ///
"""Generic Google OAuth 2.0 helper for DREAM Lab Coder Workspaces."""

import argparse
from datetime import timezone
import json
import os
from pathlib import Path
import subprocess
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import requests

DEFAULT_CLIENT_FILE = Path.home() / ".config/dreamlab/google_client.json"
DEFAULT_ADC_FILE = Path.home() / ".config/gcloud/application_default_credentials.json"
STATE_FILE = Path("/tmp/google_oauth_state.json")
REDIRECT_URI = "http://127.0.0.1:53682/"

SCOPE_ALIASES = {
    "drive": "https://www.googleapis.com/auth/drive",
    "drive.readonly": "https://www.googleapis.com/auth/drive.readonly",
    "drive.file": "https://www.googleapis.com/auth/drive.file",
    "drive.metadata.readonly": "https://www.googleapis.com/auth/drive.metadata.readonly",
    "spreadsheets": "https://www.googleapis.com/auth/spreadsheets",
    "spreadsheets.readonly": "https://www.googleapis.com/auth/spreadsheets.readonly",
    "documents": "https://www.googleapis.com/auth/documents",
    "documents.readonly": "https://www.googleapis.com/auth/documents.readonly",
    "presentations": "https://www.googleapis.com/auth/presentations",
    "calendar": "https://www.googleapis.com/auth/calendar",
    "calendar.readonly": "https://www.googleapis.com/auth/calendar.readonly",
    "gmail.readonly": "https://www.googleapis.com/auth/gmail.readonly",
    "gmail.modify": "https://www.googleapis.com/auth/gmail.modify",
    "gmail.send": "https://www.googleapis.com/auth/gmail.send",
}


def resolve_scopes(raw_scopes: list[str]) -> list[str]:
    scopes = []
    for item in raw_scopes:
        for part in item.split(","):
            part = part.strip()
            if not part:
                continue
            resolved = SCOPE_ALIASES.get(part, part)
            if resolved not in scopes:
                scopes.append(resolved)
    return scopes


def load_existing_scopes(adc_file: Path) -> list[str]:
    if not adc_file.exists():
        return []
    try:
        data = json.loads(adc_file.read_text())
        scopes = data.get("scopes", [])
        return [s for s in scopes if isinstance(s, str)]
    except Exception:
        return []


def cmd_url(args: argparse.Namespace) -> None:
    client_file = Path(args.client_file).expanduser()
    if not client_file.exists():
        raise SystemExit(
            f"Error: OAuth client file not found at {client_file}\n"
            "Place your Google OAuth Desktop client JSON at ~/.config/dreamlab/google_client.json"
        )

    adc_file = Path(args.credentials).expanduser()
    requested_scopes = resolve_scopes(args.scopes)
    existing_scopes = [] if args.replace_scopes else load_existing_scopes(adc_file)

    scopes = list(existing_scopes)
    for s in requested_scopes:
        if s not in scopes:
            scopes.append(s)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file),
        scopes=scopes,
        redirect_uri=REDIRECT_URI,
    )
    auth_kwargs = {
        "access_type": "offline",
        "prompt": "consent",
    }
    if args.include_granted_scopes:
        auth_kwargs["include_granted_scopes"] = "true"

    auth_url, state = flow.authorization_url(**auth_kwargs)
    STATE_FILE.write_text(
        json.dumps(
            {
                "client_file": str(client_file),
                "state": state,
                "code_verifier": flow.code_verifier,
                "scopes": scopes,
            }
        )
    )
    STATE_FILE.chmod(0o600)

    if existing_scopes:
        print(f"Existing scopes in {adc_file}:")
        for s in existing_scopes:
            print(f"  - {s}")
    print("Requesting scopes:")
    for s in scopes:
        marker = " (new)" if existing_scopes and s not in existing_scopes else ""
        print(f"  - {s}{marker}")
    print(f"\nAuthorization URL:\n{auth_url}")


def cmd_exchange(args: argparse.Namespace) -> None:
    if not STATE_FILE.exists():
        raise SystemExit("Error: No pending OAuth state found. Run the 'url' subcommand first.")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    saved = json.loads(STATE_FILE.read_text())
    client_file = Path(saved.get("client_file", str(DEFAULT_CLIENT_FILE))).expanduser()

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file),
        scopes=saved["scopes"],
        state=saved["state"],
        redirect_uri=REDIRECT_URI,
    )
    flow.code_verifier = saved.get("code_verifier")
    flow.fetch_token(authorization_response=args.redirect_url.strip())
    creds = flow.credentials

    expiry_iso = ""
    if creds.expiry:
        expiry_iso = (
            creds.expiry.replace(tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    granted_scopes = list(creds.granted_scopes or creds.scopes or saved["scopes"])

    # Unified JSON format compatible with:
    # 1. Google Application Default Credentials (google.auth.default())
    # 2. google.oauth2.credentials.Credentials.from_authorized_user_file()
    # 3. rclone drive token format
    unified = {
        "type": "authorized_user",
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "access_token": creds.token,
        "token": creds.token,
        "token_type": "Bearer",
        "token_uri": creds.token_uri or "https://oauth2.googleapis.com/token",
        "scopes": granted_scopes,
        "expiry": expiry_iso,
    }

    adc_file = Path(args.output).expanduser()
    adc_file.parent.mkdir(parents=True, exist_ok=True)
    adc_file.write_text(json.dumps(unified, indent=2) + "\n")
    adc_file.chmod(0o600)
    STATE_FILE.unlink(missing_ok=True)
    print(f"Saved credentials to {adc_file}")
    print("Granted scopes on token:")
    for s in granted_scopes:
        print(f"  - {s}")


def cmd_status(args: argparse.Namespace) -> None:
    adc_file = Path(args.credentials).expanduser()
    if not adc_file.exists():
        print(f"No credentials file found at {adc_file}")
        return
    data = json.loads(adc_file.read_text())
    scopes = data.get("scopes", [])
    print(f"Credentials file: {adc_file}")
    print(f"Has refresh_token: {bool(data.get('refresh_token'))}")
    print(f"Token expiry: {data.get('expiry') or 'unknown'}")
    print(f"Granted scopes ({len(scopes)}):")
    for s in scopes:
        print(f"  - {s}")


def list_shared_drives(adc_file: Path) -> list[dict]:
    creds = Credentials.from_authorized_user_file(str(adc_file))
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    drives = []
    page_token = None
    while True:
        params = {"pageSize": 100}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(
            "https://www.googleapis.com/drive/v3/drives",
            headers={"Authorization": f"Bearer {creds.token}"},
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        drives.extend(body.get("drives", []))
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    return drives


def resolve_shared_drive(adc_file: Path, query: str) -> tuple[str, str]:
    drives = list_shared_drives(adc_file)
    for d in drives:
        if d["id"] == query or d["name"].lower() == query.lower():
            return d["id"], d["name"]
    matches = [d for d in drives if query.lower() in d["name"].lower()]
    if len(matches) == 1:
        return matches[0]["id"], matches[0]["name"]
    if len(matches) > 1:
        lines = "\n".join(f"  - {d['name']} (id: {d['id']})" for d in matches)
        raise SystemExit(
            f"Multiple Shared Drives match '{query}'. Specify a more exact name or ID:\n{lines}"
        )
    lines = "\n".join(f"  - {d['name']} (id: {d['id']})" for d in drives)
    raise SystemExit(f"No Shared Drive matching '{query}'. Available Shared Drives:\n{lines}")


def cmd_configure_rclone(args: argparse.Namespace) -> None:
    adc_file = Path(args.credentials).expanduser()
    if not adc_file.exists():
        raise SystemExit(f"Error: Credentials file not found at {adc_file}. Authenticate first.")

    if args.list_shared_drives:
        drives = list_shared_drives(adc_file)
        if not drives:
            print("No Shared Drives found.")
            return
        print(f"Shared Drives ({len(drives)}):")
        for d in drives:
            print(f"  {d['id']}  {d['name']}")
        return

    data = json.loads(adc_file.read_text())
    rclone_token = json.dumps(
        {
            "access_token": data.get("access_token") or data.get("token"),
            "token_type": data.get("token_type", "Bearer"),
            "refresh_token": data["refresh_token"],
            "expiry": data.get("expiry", ""),
        },
        separators=(",", ":"),
    )

    cmd = [
        "rclone",
        "config",
        "create",
        args.remote,
        "drive",
        "client_id",
        data["client_id"],
        "client_secret",
        data["client_secret"],
        "token",
        rclone_token,
    ]
    shared_info = ""
    if args.shared_drive:
        drive_id, drive_name = resolve_shared_drive(adc_file, args.shared_drive)
        cmd.extend(["team_drive", drive_id])
        shared_info = f" (Shared Drive: '{drive_name}' [{drive_id}])"

    cmd.append("--non-interactive")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    rclone_conf = Path.home() / ".config/rclone/rclone.conf"
    if rclone_conf.exists():
        rclone_conf.chmod(0o600)
    print(f"Configured rclone remote '{args.remote}:'{shared_info} from {adc_file}")


def cmd_revoke(args: argparse.Namespace) -> None:
    adc_file = Path(args.credentials).expanduser()
    if adc_file.exists():
        data = json.loads(adc_file.read_text())
        token = data.get("refresh_token") or data.get("access_token")
        if token:
            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                timeout=10,
            )
        adc_file.unlink()
        print(f"Revoked and removed {adc_file}")
    else:
        print(f"No credentials file at {adc_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic Google OAuth 2.0 helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_url = sub.add_parser("url", help="Generate OAuth 2.0 authorization URL")
    p_url.add_argument(
        "-s",
        "--scopes",
        nargs="+",
        default=["drive"],
        help="Scopes or short aliases (e.g. drive calendar.readonly gmail.readonly)",
    )
    p_url.add_argument(
        "-c",
        "--client-file",
        default=str(DEFAULT_CLIENT_FILE),
        help=f"Path to OAuth client JSON (default: {DEFAULT_CLIENT_FILE})",
    )
    p_url.add_argument(
        "--credentials",
        default=str(DEFAULT_ADC_FILE),
        help=f"Existing credentials file to merge scopes from (default: {DEFAULT_ADC_FILE})",
    )
    p_url.add_argument(
        "--replace-scopes",
        action="store_true",
        help="Do not merge with existing scopes in the saved credentials file",
    )
    p_url.add_argument(
        "--include-granted-scopes",
        action="store_true",
        default=True,
        help="Pass include_granted_scopes=true to Google OAuth (default: True)",
    )
    p_url.add_argument(
        "--no-include-granted-scopes",
        action="store_false",
        dest="include_granted_scopes",
        help="Disable passing include_granted_scopes=true to Google OAuth",
    )
    p_url.set_defaults(func=cmd_url)

    p_ex = sub.add_parser("exchange", help="Exchange redirect URL for credentials")
    p_ex.add_argument(
        "redirect_url",
        help="Full http://127.0.0.1:53682/?... redirect URL copied from browser",
    )
    p_ex.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_ADC_FILE),
        help=f"Output credential path (default: {DEFAULT_ADC_FILE})",
    )
    p_ex.set_defaults(func=cmd_exchange)

    p_st = sub.add_parser("status", help="Show saved credentials and granted scopes")
    p_st.add_argument(
        "--credentials",
        default=str(DEFAULT_ADC_FILE),
        help=f"Credentials file path (default: {DEFAULT_ADC_FILE})",
    )
    p_st.set_defaults(func=cmd_status)

    p_rc = sub.add_parser(
        "configure-rclone",
        help="Configure an rclone Google Drive remote from the saved credentials",
    )
    p_rc.add_argument(
        "-r",
        "--remote",
        default="gdrive",
        help="rclone remote name (default: gdrive)",
    )
    p_rc.add_argument(
        "-s",
        "--shared-drive",
        help="Optional Shared Drive (Team Drive) name or ID to bind the remote to",
    )
    p_rc.add_argument(
        "--list-shared-drives",
        action="store_true",
        help="List available Shared Drives and exit",
    )
    p_rc.add_argument(
        "--credentials",
        default=str(DEFAULT_ADC_FILE),
        help=f"Credentials file path (default: {DEFAULT_ADC_FILE})",
    )
    p_rc.set_defaults(func=cmd_configure_rclone)

    p_rev = sub.add_parser("revoke", help="Revoke and delete saved credentials")
    p_rev.add_argument(
        "--credentials",
        default=str(DEFAULT_ADC_FILE),
        help=f"Credentials file path (default: {DEFAULT_ADC_FILE})",
    )
    p_rev.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
