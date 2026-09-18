---
name: hermes-gateway-supervision
description: "Use when a Hermes gateway goes silent or dies."
license: MIT
version: 1.0.0
author: Hermes Agent
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [hermes, gateway, watchdog, supervision, telegram, failover, reliability]
    related_skills: [hermes-multi-instance, hermes-cron, hermes-verification-gates]
---


# Hermes Gateway Supervision

Keeping one or more Hermes gateways actually running, and **proving** it with live probes instead
of trusting state files. A bot that stops answering is nearly always a dead gateway process, not a
bad command. Covers diagnosis, restart, and failover verification; profile/bot *setup* lives in
`hermes-multi-instance`, scheduler internals in `hermes-cron`.

## When to use

- A bot did not answer (silent `/new`, `/reset`, or any DM) and the command itself is suspect.
- A gateway restarted on its own, or you just restarted one and must confirm it took.
- You changed the watchdog / supervisor and need to prove failover still works.

## Rule 1 — Liveness comes from the process table, never a state file

`gateway_state.json`, `gateway.pid` and `gateway.lock` are **snapshots written by the gateway**.
Nothing rewrites them when it dies, so a dead gateway keeps advertising
`"gateway_state": "running"` with telegram `"state": "connected"` long after the process is gone.

```bash
# liveness — the only truth
tasklist /FI "PID eq <pid>"          # Windows (MSYS: grep on tasklist fails, UTF-16)
# health — the log says what the bot is actually doing
tail -3 <HERMES_HOME>/logs/gateway.log
#   "Telegram polling confirmed healthy: getUpdates progressing" = live and consuming updates
```

**Pitfall — the false-positive recovery poll.** A loop that polls `gateway_state.json` for
`running/connected` reports "recovered" within seconds while the process is still dead, because the
file was never updated to say otherwise. Any restart or failover poll must key on `tasklist` + the
supervisor log, and use the state file only as a *final* confirmation once a fresh process has
rewritten it.

## Rule 2 — Read the death, don't assume it

| Log evidence | Meaning |
|---|---|
| `CRITICAL gateway.shutdown_watchdog: ... missed 3 consecutive liveness probes ... exiting with code 75` | Event loop blocked; the gateway self-killed **expecting a supervisor to restart it**. Find the supervisor before blaming the hang. |
| Log simply stops mid-turn, no shutdown line | Hard kill. A start flagged `stdin_is_tty: true` / `absorb_windows_console_controls: false` in `gateway-exit-diag.log` was **console-attached** and dies with its parent console — relaunch detached. |
| `previous_unclean_exit` in `gateway-exit-diag.log` | An earlier instance also died without saying goodbye; treat it as a pattern, not a one-off. |

A bot being down is usually **two** faults: the gateway died, *and* whatever should have restarted
it was already dead. Check the supervisor before you "fix" the gateway.

## Rule 3 — Supervisors must be crash-resistant by construction

- **Catch `OSError` anywhere a file is read.** `PermissionError` and friends are `OSError`
  subclasses; hand-listing `FileNotFoundError` alone leaves a live bomb. One transient error raised
  out of the check path takes down the whole supervisor.
- **Wrap every per-target check in the loop in a try/except that logs and continues.** A single bad
  check must never end the supervisor; the next cycle is the retry.
- **The scheduled task only fires at logon/startup.** If the supervisor loop dies, nothing restarts
  anything until reboot — a dead supervisor is silent and permanent. Confirm it is alive with
  `tail <HERMES_HOME>/logs/watchdog.log`: a recent `Watchdog starting (... one_shot=False)` and no
  fatal traceback after it.

## Rule 4 — Restart detached, never from inside an agent session

```bash
# One-shot: restarts a downed target, no-ops on a live one with a fresh heartbeat.
# Safe while the default gateway is serving you — VERIFY the default is alive and its heartbeat is
# fresh first, or the one-shot will restart the gateway you are talking through.
"<root>/.cache/runtimes/windows-x64/venv/Scripts/python.exe" "<root>/scripts/gateway-watchdog.py" --once

# Persistent supervisor loop — detached, no console, survives session end:
powershell -NoProfile -Command "Start-Process -FilePath '<venv>\Scripts\pythonw.exe' -ArgumentList '<root>\scripts\gateway-watchdog.py' -WindowStyle Hidden -WorkingDirectory '<root>'"
```

Never hand-launch a gateway attached to your own shell — it dies when that shell does, which is one
of the two ways a bot disappears silently.

## Rule 5 — Prove failover, don't assert it

After any supervisor change, kill the target and watch it come back:

```bash
taskkill /PID <child-pid> /F     # simulate the crash
tail -6 <HERMES_HOME>/logs/watchdog.log
```

Healthy recovery looks like this inside roughly one check interval plus startup (~25s at
`CHECK_INTERVAL=30`):

```
WARNING [<name>] Gateway DOWN (restart #1 of 5)
INFO    [<name>] Starting gateway: ... pythonw.exe -m hermes_cli.main gateway run [--profile <name>]
INFO    [<name>] Spawned PID <stub>
INFO    [<name>] Gateway alive (PID <child>) after 11s
```

Killing a *profile* gateway leaves the default gateway untouched — but confirm you are killing the
child PID of the intended profile before pulling the trigger.

## Rule 6 — Stub→child pairs are not duplicates

The venv `Scripts\pythonw.exe` is a launcher stub that re-execs the embedded runtime
`python\pythonw.exe`. Every Hermes process therefore appears as **two** rows with the same command
line and different PIDs — parent = stub, child = the real process. Compare `ParentProcessId` before
concluding you have duplicate gateways or two supervisor loops running.

Consequences: the supervisor's `Spawned PID` line and its `did not write PID file within 20s`
warning both name the **stub**; the real PID is the child. Re-read `gateway.pid` after startup rather
than trusting the spawn line, and treat that 20s warning as benign when the log shows the child
coming up.

## One-bot-silent triage

1. PID from `gateway.pid` → `tasklist /FI "PID eq <pid>"`. Dead? Note it and continue.
2. `logs/gateway.log` tail → died how, and when (Rule 2).
3. `logs/watchdog.log` tail → was anything supervising at that moment (Rule 3).
4. Check whether the user's message ever *arrived*: `grep -a "inbound message" logs/gateway.log`.
   Absent = the bot was down. Arrived with a response line = the command worked and the problem is
   elsewhere. Do this before theorising about the command.
5. Restart detached (Rule 4), prove it (Rule 5), then report the **root cause** — not just "it's up
   again".
