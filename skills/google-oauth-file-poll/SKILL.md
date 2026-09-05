---
name: google-oauth-file-poll
description: Use when Google API OAuth needs a headless file-poll flow.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [google, oauth, headless, api, token]
    category: devops
---


# Google API OAuth: Headless File-Poll Flow

## Overview

Authorize Google API clients (YouTube, Drive, Gmail, Sheets, …) on machines
with **no browser**: a script writes the consent URL to a file, the user opens
it on ANY device, pastes the code into another file, and the script polls
until it arrives, then stores the refreshable token. No browser on the box,
no port forwarding, no interactive prompts. Works identically on headless
servers, CI runners, and USB-portable environments.

Ships `scripts/oauth_file_poll.py` — a complete, configurable implementation.

## When to Use

- Automating Google APIs from servers/containers without a display.
- Recurring upload/new-scope automation where the token expires and the
  re-auth dance happens repeatedly.
- **Don't use for:** interactive local development where a browser is fine —
  `InstalledAppFlow.run_local_server()` is easier there.

## The Flow

1. Have a Google Cloud OAuth **desktop client** (`client_secret.json`) with
   the needed scopes enabled.
2. Run the script: it builds an `InstalledAppFlow`, sets the out-of-band
   redirect URI (`urn:ietf:wg:oauth:2.0:oob`), writes `auth_url.txt`, and
   prints the path. No browser is opened.
3. The user opens the URL anywhere (phone/laptop), consents, and pastes the
   code into `auth_code.txt`.
4. The script polls `auth_code.txt` (default 600s), exchanges the code,
   saves `token.json`, and deletes both temp files.
5. Next runs reuse `token.json` and refresh automatically when expired:

```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
creds = Credentials.from_authorized_user_file("token.json", SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
```

Then build the API service: `googleapiclient.discovery.build("youtube", "v3", credentials=creds)`.

## Script Configuration

Edit the top of `scripts/oauth_file_poll.py`:

- `CLIENT_SECRET` / `TOKEN_FILE` — paths (keep OUT of version control).
- `SCOPES` — the exact scopes for the API you automate.
- `TIMEOUT` — seconds to wait for the paste-back code (default 600).

## Common Pitfalls

1. **PKCE handshake is finicky across separate processes** — run the
   generate/URL + poll + exchange in ONE long-lived script, not in separate
   invocations with hand-carried state.
2. **`oob` redirect deprecation** — some client types reject `oob`; if so,
   use a loopback redirect and read the code from the localhost URL.
3. **Never commit `token.json` / `client_secret.json`** — add both to
   `.gitignore`; a leaked client secret lets anyone mint tokens.
4. **Expired refresh flow** — a token whose refresh token is gone (revoked
   consent, scope change) requires a full re-consent; detect and restart the
   file-poll flow instead of erroring.
5. **Timeout hygiene** — always clean up `auth_url.txt`/`auth_code.txt` on
   success and on timeout; stale code files break the next attempt.

## Verification Checklist

- [ ] First run writes `auth_url.txt` and prints its path
- [ ] After code paste, `token.json` exists and temp files are deleted
- [ ] A second run completes WITHOUT prompting (token reuse/refresh)
- [ ] API call succeeds with the stored credentials