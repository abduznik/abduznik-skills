---
name: docker-container-update-check
description: "Use when checking Docker containers for newer images."
metadata:
  hermes:
    tags: [docker, containers, updates]
    category: devops
version: 1.0.0
author: Hermes Agent
license: MIT
---




# Docker Container Update Check

## When to Use

- User asks "do any containers need updating?" on a Docker host (homelab, VPS, desktop)
- Need a read-only update audit: which running containers have a newer image upstream
- Must NOT pull images or restart containers (a pure audit)

## Core Approach

Compare the **digest the running container was created from** (local `RepoDigests`)
against the **registry's current digest** for the same tag (`manifest inspect`).
No `docker pull`, no layer downloads, no container lifecycle impact.

```bash
# Per-container:
iid=$(docker inspect --format "{{.Image}}" "$c")          # image ID of running container
cur=$(docker image inspect --format "{{range .RepoDigests}}{{.}}{{end}}" "$iid" | sed "s/.*@//")
latest=$(docker manifest inspect --verbose "$img" | python3 -c "...parse digest...")
# cur == latest  -> CURRENT ; differ -> UPDATE
```

Run in parallel — a serial loop over 40+ containers times out (>420s):
```bash
docker ps -q | xargs -P 10 -I {} /tmp/check_container_updates.sh {}
```

## Pitfalls

- **Cron Python scripts must pin Git's ssh.exe on exFAT drives**: the target drive may be exFAT (no ACLs). Windows OpenSSH (`C:\Windows\System32\OpenSSH\ssh.exe`, first on system PATH) **refuses any private key on exFAT/FAT** with `UNPROTECTED PRIVATE KEY FILE / permissions too open`, while Git-bash's ssh works fine. A script that shells out to `ssh` by name → cron no_agent runs resolve to System32 OpenSSH → setup fails. Fix: `SSH = r"C:/Program Files/Git/usr/bin/ssh.exe"` and use `[SSH, "-i", KEY, ...]` in every subprocess call. Apply the same pattern to any watchdog script that needs ssh.
- **CRLF corrupts scripts deployed via SSH stdin**: writing `check_container_updates.sh` through `ssh host "cat > /tmp/..."` from Windows adds `\r`, producing `Syntax error: end of file unexpected (expecting "fi")` and a SILENTLY BROKEN watchdog (all outputs empty). Fix on host: `sed -i 's/\r$//' /tmp/check_container_updates.sh && bash -n ...` — always verify with `bash -n` after deploy.
- **Multi-arch manifest shape**: `docker manifest inspect --verbose` returns a **LIST** of
  per-platform descriptors for multi-arch images, but a **DICT** `{"Descriptor": {...}}`
  for single-arch images. A parser that only handles one shape mislabels every result of
  the other kind. Handle both: `d[0]['Descriptor']['digest']` if list, `d['Descriptor']['digest']` if dict.
- **Docker Hub anonymous rate limit**: 100 pulls/6h per IP. When exhausted, `manifest
  inspect` fails with `toomanyrequests: You have reached your unauthenticated pull rate
  limit` and every docker.io image shows as CHECK_FAIL. **ghcr.io and lscr.io are NOT
  affected** — split results by registry to isolate the rate-limited ones, and re-check
  docker.io images after the window resets. A mass update the day before typically burns
  the quota.
- **`latest`-tag churn is normal**: linuxserver-style images rebuild daily. Containers
  updated 23h ago can already show a newer digest. Report it, don't treat it as an alarm.
- **Per-image timeout**: wrap manifest inspect in `timeout 25` so one slow registry
  doesn't stall the batch.
- **Locally built images** (no registry reference, e.g. `python_stack-bingbong`) and
  images with no `RepoDigests` show as CHECK_FAIL / DIGEST_UNKNOWN — they have no
  upstream to compare against; note them as "local build, update = rebuild".

## Verification

- Cross-check a couple of results: `docker manifest inspect --verbose <img>` for one
  UPDATE and one CURRENT confirms the parser is comparing real digests, not garbage.
- `unbound`-style single-arch images are a good CURRENT control (dict shape path).

## Support Files

- `scripts/check_container_updates.sh` — the full per-container checker with the
  dual-shape parser baked in. Deploy to the host and run via xargs as above.
