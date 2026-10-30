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
            scopes.append(SCOPE_ALIASES.get(part, part))
    return scopes


def cmd_url(args: argparse.Namespace) -> None:
    client_file = Path(args.client_file).expanduser()
    if not client_file.exists():
        raise SystemExit(
            f"Error: OAuth client file not found at {client_file}\n"
            "Place your Google OAuth Desktop client JSON at ~/.config/dreamlab/google_client.json"
        )

    scopes = resolve_scopes(args.scopes)
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file),
        scopes=scopes,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
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
    print(auth_url)


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
        "scopes": list(creds.scopes or saved["scopes"]),
        "expiry": expiry_iso,
    }

    adc_file = Path(args.output).expanduser()
    adc_file.parent.mkdir(parents=True, exist_ok=True)
    adc_file.write_text(json.dumps(unified, indent=2) + "\n")
    adc_file.chmod(0o600)
    STATE_FILE.unlink(missing_ok=True)
    print(f"Saved credentials to {adc_file}")


def cmd_configure_rclone(args: argparse.Namespace) -> None:
    adc_file = Path(args.credentials).expanduser()
    if not adc_file.exists():
        raise SystemExit(f"Error: Credentials file not found at {adc_file}. Authenticate first.")

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
        "--non-interactive",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    rclone_conf = Path.home() / ".config/rclone/rclone.conf"
    if rclone_conf.exists():
        rclone_conf.chmod(0o600)
    print(f"Configured rclone remote '{args.remote}:' from {adc_file}")


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
