---
name: reverse-proxy-websocket-debugging
description: Use when WebSockets die behind a reverse proxy (close 1006).
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [websocket, reverse-proxy, debugging]
    category: devops
---


# Reverse-Proxy WebSocket Debugging

Symptom signature: pages load fine through the proxy, but WS-dependent features are dead. Browser console shows `WebSocket Error` then `Closed WebSocket ... code: 1006` with reconnect loops; apps show banners like "This websocket connection has been closed. Are you using a reverse proxy?" (Crafty) or just silently no live data. Note: dashboard numbers may still appear — they can be server-rendered at page load, not WS evidence.

## Root cause checklist (in order of likelihood)

1. **Upstream Host header rewritten by the proxy** — Caddy's default for `reverse_proxy localhost:8443` is to send `Host: localhost:8443` upstream. Origin-checking backends (Tornado `check_origin`, Django Channels, Flask-SocketIO same-origin) compare the browser's `Origin` (public domain) against the `Host` they see (now the dial address) → upgrade rejected with `403 Cross origin websockets not allowed` (Tornado). The browser turns the failed handshake into close **1006**.
   - Caddy fix: `header_up Host {http.request.host}` inside the `reverse_proxy` block.
   - Nginx fix: `proxy_set_header Host $http_host;` plus the upgrade headers below.
2. **Upgrade headers not forwarded** — Nginx needs explicit `proxy_http_version 1.1;`, `proxy_set_header Upgrade $http_upgrade;` + `Connection "upgrade";` + `X-Forwarded-Proto https;` + `X-Forwarded-For ...;`. Caddy forwards upgrade headers automatically — if it still fails, suspect #1, not this.
3. **Backend auth/origin policy** — some apps validate a WS token cookie or require URL params; read the backend's WS handler source to see exactly what it checks before guessing.

## Diagnosis drill

1. **Get the real WS URL**: open the app in a browser and pull the console (browser_console). Apps often log the target, e.g. Crafty: `new WebSocket('wss://' + location.host + '/ws?...')`. The frontend source is authoritative — grep it before blaming backend config.
2. **Probe the handshake** direct to the backend AND through the proxy with curl (no WS client library needed):
   ```bash
   # direct backend (adjust scheme/port/params): 101 = healthy
   curl -sk -i --max-time 8 -H "Connection: Upgrade" -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" \
     -H "Origin: https://<public-host>" "https://localhost:<backend-port>/ws?<params>"
   ```
   Through-proxy variant: same headers plus `--resolve <public-host>:443:127.0.0.1` with the real URL. **Always `--resolve` the real hostname** — curling `https://localhost` through a vhost-charged proxy dies in TLS (no cert for SNI `localhost`; looks like the proxy ate the request but it never reached HTTP).
3. **Isolate Host-rewrite**: resend through the proxy with `-H "Origin: https://localhost:<backend-port>"`. If THAT returns `101 Switching Protocols`, the proxy is rewriting Host upstream and the real-Origin check is what fails → apply the `header_up Host` fix.
4. **Re-verify after the fix**: real-Origin probe through the proxy → `101`; browser console shows `opened WebSocket connection` and no reconnect spam.

## Pitfalls

- **SPA login forms corrupt automation typing** (React/Vue controlled inputs): browser_type can leave garbage or truncated values (username field ended up holding a framework token, password had 5 of 63 chars). Fix — set values via native setter + dispatch `input`/`change` in one console JS line:
  ```js
  const setVal=(el,v)=>{const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
  ```
  Never treat an automated-browser login as credential proof — verify in a real browser or server-side (e.g. DB hash check).
- **Tornado XSRF on API login** makes curl brute-forcing painful (cookie jar + `_xsrf` token dance); prefer browser or DB-backed verification.
- **Caddyfile edits**: apply via write-through of the bind-mounted inode + `caddy validate` + `caddy reload` (inode trap — see homelab-server-admin).
- **Approval timeouts kill long sudo batches**: if a mutating SSH batch times out at the approval gate, re-present the pending commands as a short plan instead of silently retrying.

## Worked case

Crafty Controller + Caddy (Aug 2026): full capture — commands, outputs, Caddyfile diff — in `references/crafty-caddy-websocket.md`.