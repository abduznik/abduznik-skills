#!/usr/bin/env python3
"""Headless Google API OAuth via file polling — no browser on the box.

Flow:
  1. Run this script -> it writes auth_url.txt and prints its path.
  2. Open auth_url.txt's URL on ANY device, consent, copy the code.
  3. Paste the code into auth_code.txt next to the script.
  4. The script polls (default 600s), exchanges the code, saves token.json,
     and deletes both temp files. Reuse token.json on later runs.

Configure CLIENT_SECRET, TOKEN_FILE and SCOPES below. Never commit
client_secret.json or token.json.
"""
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_SECRET = Path("client_secret.json")  # Google Cloud OAuth desktop client
TOKEN_FILE = Path("token.json")
URL_FILE = Path("auth_url.txt")
CODE_FILE = Path("auth_code.txt")
SCOPES = ["https://www.googleapis.com/auth/API_SCOPE_PLACEHOLDER"]  # set yours
TIMEOUT = 600  # seconds to wait for the paste-back code


def load_or_refresh() -> Credentials | None:
    if not TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def main() -> int:
    creds = load_or_refresh()
    if creds and creds.valid:
        print(f"TOKEN_OK:{TOKEN_FILE}")
        return 0

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    flow.oauth2session.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url, _ = flow.authorization_url(
        prompt="consent select_account",
        access_type="offline",
        include_granted_scopes="true",
    )
    URL_FILE.write_text(auth_url)
    print(f"AUTH_URL_WRITTEN:{URL_FILE}")

    if CODE_FILE.exists():
        CODE_FILE.unlink()

    for _ in range(TIMEOUT):
        if CODE_FILE.exists():
            code = CODE_FILE.read_text(encoding="utf-8").strip()
            if code:
                flow.fetch_token(code=code)
                TOKEN_FILE.write_text(flow.credentials.to_json())
                CODE_FILE.unlink(missing_ok=True)
                URL_FILE.unlink(missing_ok=True)
                print(f"TOKEN_SAVED:{TOKEN_FILE}")
                return 0
        time.sleep(1)

    print(f"TIMEOUT: no auth code within {TIMEOUT}s")
    return 1


if __name__ == "__main__":
    sys.exit(main())