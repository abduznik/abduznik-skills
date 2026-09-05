---
name: windows-crash-forensics
description: "PC crash/freeze forensics via event logs, blame attribution."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [Windows, Crash, Event-Log, Kernel-Power, BSOD, Troubleshooting, Forensics]
    related_skills: [windows-environment, systematic-debugging]
---


# Windows Crash Forensics

Diagnose a "my PC crashed / froze / rebooted" report BEFORE blaming anything.
Goal: classify the failure (BSOD vs hard freeze vs power loss), find the
trigger, and attribute it correctly (our cron/scripts vs Windows apps vs
hardware). Real case: the user reported "you somehow crashed my PC" —
forensics showed a Google Drive File Stream shutdown hang minutes after the
last scheduled job finished; attributing it wrong would have damaged trust.

Real case detail + full query reference: see `references/crash-attribution-case.md`.

## Step 1 — Was it a crash? What kind?

```bash
# Kernel-Power 41 events (unexpected reboot/shutdown) — these carry the verdict
powershell.exe -NoProfile -Command 'Get-WinEvent -FilterHashtable @{LogName="System"; Id=41} -MaxEvents 8 2>$null | ForEach-Object { "{0} | Bugcheck {1} | PowerButton {2}" -f $_.TimeCreated, $_.Properties[0].Value, $_.Properties[6].Value }'
# Last boot time (did it come back on its own?):
powershell.exe -NoProfile -Command '(Get-CimInstance Win32_OperatingSystem).LastBootUpTime'
```

Interpretation of Event 41 (Kernel-Power) properties:
- **Bugcheck 0 + PowerButton 0** → hard freeze / system hang, NOT a BSOD
  (no bugcheck code) and NOT a power-button press. The system stopped
  responding and was rebooted.
- **Bugcheck != 0** → real BSOD; the value is the stop code (0x1E, 0x133, ...).
- **PowerButton != 0** → user or watchdog pressed power / reset.

Corroborating evidence (query the same System log):
- **Event 6008** → "The previous system shutdown at <time> was unexpected."
  The timestamp IN THE MESSAGE is the exact freeze moment (event's own
  TimeCreated is AFTER reboot).
- **Minidump dir** (`C:\Windows\Minidump`) — non-empty = BSOD dumps; empty +
  event 41 = hang, not BSOD.
- **WHEA-Logger** (`ProviderName="Microsoft-Windows-WHEA-Logger"`) — any
  hardware errors (PCIe/CPU/memory)? Empty = no hardware fault signal.
  `Get-WinEvent -FilterHashtable @{LogName="System"; ProviderName="Microsoft-Windows-WHEA-Logger"}`

## Step 2 — What happened in the minutes before? (the attribution window)

Pull ALL System events between the last healthy activity and the 6008
timestamp. Filter for the high-signal IDs: `1,41,6008,1001,4101,6006,1074,7000`.

```bash
powershell.exe -NoProfile -Command 'Get-WinEvent -FilterHashtable @{LogName="System"; StartTime="<DATE> <HH:MM>"; EndTime="<DATE> <HH:MM>"} -ErrorAction SilentlyContinue | Where-Object {$_.Id -in 1,41,6008,1001,4101,6006,1074,7000} | ForEach-Object { "{0} | ID {1} | {2} | {3}" -f $_.TimeCreated, $_.Id, $_.ProviderName, ($_.Message -split "`n")[0] }'
```

Key signals and what they mean:

| Signal | Meaning |
|--------|---------|
| **Event 1074 (User32 / RuntimeBroker)** | Something *initiated* the restart. Full message names the process: `RuntimeBroker.exe ... reason: Other (Unplanned)` = a Windows/UWP app flow requested restart — NOT an agent, NOT the user clicking. `Explorer.exe`/user-initiated = a person did it. |
| **googledrivefs* flood: "Unmounting due to keepalive close", G: mount-entry removal, CldFlt filter events** | **Google Drive File Stream** disconnecting. Known Win10 hang trigger — its cloud-filter driver deadlocks during unmount/shutdown. Strongest single suspect when present. |
| **COM+ Event System "timed out firing the Logoff method" (180s timeout)** | Shutdown started but a subscriber (often Explorer) hung — system is STUCK IN shutdown, not crashed mid-work. |
| **Winlogon "notification subscriber <Sens> taking long (Logoff)"** | Same shutdown hang, logoff phase. |
| **Windows Search protocol host force-terminated** | SearchIndexer wedged — secondary contributor. |
| **ID 10010 DistributedCOM** | A COM server didn't register in time — part of the hang pattern. |
| **DNS-Client 1014, SCM 7040** | Normal teardown noise — ignore. |

A shutdown hang reads as: 1074/initiator → unmount/teardown storm → COM+/Sens
timeouts → 6008 (dead) → 41 on boot. If most of the window is normal activity
then a dead stop with NO shutdown sequence, that's a different animal (watchdog,
power, or a kernel deadlock).

## Step 3 — Check OUR side before claiming innocence

Never tell the user "not ours" without running this checklist:

1. **Our scheduled jobs**: `cronjob action=list` — what ran in the window?
   Check `last_run_at`; verify heavy jobs (TTS servers, encodes, video
   downloads) FINISHED before the freeze, not during it.
2. **No shutdown commands in our code**: grep the script dir for
   `shutdown|Restart-Computer|Stop-Computer|reboot` — expect zero matches.
3. **No lingering heavy processes**: `netstat -ano | findstr ":9872"`
   (GPT-SoVITS TTS server must be killed after use — VRAM) and
   `Get-Process python*,ffmpeg*` for strays.
4. **Session correlation**: `session_search` for what we were doing that hour
   and what commands ran.

Only when 1-3 are clean do you present "not ours" — with the evidence trail.

## Step 4 — Report

Compact summary (~150-200 words): freeze timestamp, event-41 classification,
the 1074 initiator, the hang sequence (e.g. googledrivefs → Explorer/Sens
logoff timeout), our-jobs-were-idle evidence, and the practical fix suggestion
(e.g. update/pause Google Drive File Stream). State what the log proves and
what it doesn't — don't over-claim.

## Pitfalls

- **PowerShell one-liners from Git Bash get mangled** (`terminal()` runs bash):
  - `$_` → bash expands it to the previous command's last arg
  - `2>$null` → bash eats the redirect → "Missing file specification"
  - `-f` format strings → MSYS path-mangles `/c/Users/...` tokens
  **Fix: wrap the entire `powershell.exe -NoProfile -Command` payload in
  SINGLE quotes** so bash passes it verbatim. Never double-quote PS payloads
  from bash.
- **Event 6008's TimeCreated is post-reboot** — read the timestamp inside the
  message for the actual freeze moment. Getting this wrong misleads the whole
  window search.
- **Don't conflate "crash while I was working" with "crash caused by me"** —
  correlation by clock is not causation; the 1074 initiator + our-job idle
  times are what actually attribute.
- **No minidump ≠ no crash** — hangs leave no dump. Event 41 + empty Minidump +
  bugcheck 0 IS the hang signature.