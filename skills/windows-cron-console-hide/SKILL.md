---
name: windows-cron-console-hide
description: Suppress console window flashes on Windows — covers both Python subprocess creationflags AND VBS wrappers for launching .cmd/.bat files invisibly from Startup folder or scheduled tasks.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [windows, cron, vbs, console, scheduled-tasks]
    category: devops
---



# Windows Cron Console Flash Fix

## Problem

On Windows, every `subprocess.run(["hermes", ...])` or `subprocess.run(["gh", ...])` inside cron no_agent scripts causes `hermes.exe` (or `gh.exe`) to briefly flash a console window. The cron scheduler's `_run_job_script` already uses `CREATE_NO_WINDOW` for the **top-level** script process, but scripts that internally call `hermes`/`gh` as subprocesses don't pass hide flags — so child processes create visible windows.

This is most noticeable with high-frequency cron jobs (kanban-monitor every 1m, kanban-watchdog every 2m).

## Diagnosis

When the user reports window flashes from background cron jobs, find the offenders in two steps:

```bash
# 1. Search all cron scripts for subprocess calls to the offending CLI
grep -rn "subprocess.run.*gh[^a-z]" /path/to/hermes/data/scripts/

# 2. Cross-reference with cron list to see which are actively running
cronjob action=list
```

Scripts found in step 1 that are **not paused** in step 2 are the active flashers. Fix each one by adding `creationflags=_WIN_HIDE` — see the Fix Pattern below.

## Fix Pattern

Every cron script that calls `hermes` or `gh` as a subprocess needs:

```python
import subprocess
import sys

# Windows: suppress console window when spawning subprocesses
_WIN_HIDE = 0x08000000 if sys.platform == "win32" else 0
```

Then pass `creationflags=_WIN_HIDE` to every `subprocess.run()` / `subprocess.Popen()` call:

```python
result = subprocess.run(
    ["hermes", "kanban", "ls", "--json"],
    capture_output=True, text=True, timeout=30,
    creationflags=_WIN_HIDE,  # ← prevents console window flash
)
```

## Also Fix the Scheduler

In `cron/scheduler.py`, `_run_job_script()` should use `windows_detach_flags()` (which includes `DETACHED_PROCESS | CREATE_NO_WINDOW`) instead of `windows_hide_flags()` (just `CREATE_NO_WINDOW`). The detach flag is stronger at suppressing console windows and still works with `capture_output=True` (pipes are independent of console handles).

## Launching .cmd/.bat Files Invisibly (VBS Wrapper)

The Python `creationflags` pattern above works for `subprocess.run()`/`Popen()` calls. But when you need to launch a `.cmd` or `.bat` file invisibly from the Windows Startup folder or by double-click, there's no Python in the chain — you need a different approach.

**Problem:** `start "" /min cmd.exe /c script.cmd` creates a briefly-visible minimized console window. Also, `cmd /c start /B /WAIT` from git-bash/MSYS2 gives "Access is denied" — do NOT use this approach from git-bash.

**Solution (fire-and-forget):** Use a `.vbs` (VBScript) wrapper with `WScript.Shell.Run` and `nCmdShow=0` (SW_HIDE):

```vbs
' script_launcher.vbs — launches a .cmd file with zero visible window
Dim objShell
Set objShell = CreateObject("WScript.Shell")
objShell.Run "cmd.exe /c /path/to/path\to\script.cmd", 0, False
Set objShell = Nothing
```

- `0` = SW_HIDE (window is never created, not even minimized)
- `False` = non-blocking (fire-and-forget, VBS exits immediately)

**Solution (capture output, hidden):** When you need to run a Windows CLI executable (like `gh.exe`) completely hidden but still capture stdout/stderr and exit code, use `WScript.Shell.Exec` instead of `.Run`:

```vbs
' gh-hidden.vbs — runs gh.exe with zero window visibility, captures stdout/stderr
Dim WshShell, proc, cmd, allOutput
Set WshShell = CreateObject("WScript.Shell")

' Build command: executable + space-separated quoted arguments
cmd = "gh.exe"
If WScript.Arguments.Count > 0 Then
  For i = 0 To WScript.Arguments.Count - 1
    cmd = cmd & " " & Chr(34) & WScript.Arguments(i) & Chr(34)
  Next
End If

' Exec runs hidden by default (no window style flags needed)
Set proc = WshShell.Exec(cmd)

' Capture stdout (blocks until process finishes)
allOutput = ""
Do While Not proc.StdOut.AtEndOfStream
  allOutput = allOutput & proc.StdOut.ReadLine() & vbCrLf
Loop
WScript.Echo allOutput

' Capture stderr
Dim errOutput
errOutput = ""
Do While Not proc.StdErr.AtEndOfStream
  errOutput = errOutput & proc.StdErr.ReadLine() & vbCrLf
Loop
If errOutput <> "" Then WScript.StdErr.Write errOutput

' Pass through exit code
WScript.Quit(proc.ExitCode)
```

Call from bash via `cscript //Nologo` (suppresses the Microsoft logo banner):
```bash
cscript //Nologo "/path/to/path\to\gh-hidden.vbs" status
```

**Known pitfalls:**
- `WshShell.Exec` only works for standalone EXEs, not cmd.exe builtins
- If the executable is not in PATH, provide the full absolute path inside the VBS
- Always use the full path to the VBS from the caller; relative paths fail when called from a different working directory
- `proc.ExitCode` is only valid after the stdout/stderr streams have reached end-of-stream (the read loops block until the process finishes, so by the time you read ExitCode the process is done)
- **Bash shebang wrappers are invisible to Python's `subprocess.run` on Windows.** `CreateProcess` does not understand shebangs. A bash wrapper script (no extension, shebang) at `<user-path>\bin\gh` is completely invisible to `subprocess.run(["gh", ...])`. You MUST also have a `.bat`/`.cmd` file in the same intercept directory for Python subprocess interception to work — Windows finds it via PATHEXT resolution before reaching the real `.exe` in a later PATH directory.

**Python subprocess PATH interception requires .bat, not just a bash script:**

When a cron no_agent script (Python) calls `subprocess.run(["gh", ...])` or `subprocess.run(["hermes", ...])`, Windows `CreateProcess` resolves executables via PATH + PATHEXT — it checks each directory in PATH with every extension in PATHEXT (`.COM, .EXE, .BAT, .CMD, .VBS, ...`) before moving to the next directory.

If PATH order is:
1. `<user-path>\bin` (has `gh.bat`)
2. `C:\Program Files\GitHub CLI` (has `gh.exe`)

The `.bat` is found at step 1 (via `.BAT` in PATHEXT) before `.exe` at step 2. So a `.bat` file catches `CreateProcess` calls that a shebang script would miss.

**Pattern for silent CLI wrappers that work from ALL contexts on Windows:**

```bash
# File 1 — Bash wrapper (<PATH_DIR>/exename, no extension, shebang)
#!/usr/bin/env bash
VBS_SCRIPT="/path/to/hidden.vbs"
exec cscript //Nologo "$VBS_SCRIPT" "$@"
```

```bat
REM File 2 — Batch wrapper (<PATH_DIR>/exename.bat)
@echo off
cscript //Nologo "/path/to/path\to\hidden.vbs" %*
exit /b %ERRORLEVEL%
```

The bash wrapper handles `terminal()` and interactive bash sessions. The `.bat` handles `subprocess.run(...)` from Python cron scripts. Both call the same VBScript helper.

**From a Startup folder .cmd entry:**
```cmd
@echo off
wscript.exe "/path/to/path\to\script_launcher.vbs"
exit /b 0
```

**When to use this vs `creationflags`:**
| Scenario | Solution |
|----------|----------|
| Python script spawning subprocess | `creationflags=0x08000000` (CREATE_NO_WINDOW) |
| Startup folder / scheduled task launching .cmd | VBS wrapper with `WScript.Shell.Run ... , 0` |
| Manual double-click of a launcher | VBS wrapper (or .cmd that calls wscript) |
| CLI tool where output must be captured, invisibly | VBS wrapper with `WScript.Shell.Exec` + `cscript //Nologo` |

## Files Typically Needing Fix

- `data/scripts/kanban-monitor.py` — runs every 1m
- `data/scripts/kanban-watchdog.py` — runs every 2m
- `data/scripts/kanban-status.py` — runs every 15m
- `data/scripts/pr-check.py` — uses `gh` CLI
- `data/scripts/pr-review-discover.py` — uses `gh` CLI
- `data/scripts/repo-monitor.py` — uses `gh` CLI (every 30m)
- `data/scripts/gfi-scout.py` — uses `gh` CLI (every 12h)
- `data/scripts/send-kanban.py` — uses `subprocess.Popen` for servers
- `src/hermes-agent/cron/scheduler.py` — `_run_job_script()` function
- Any new cron script that calls external CLIs

## Gateway Launcher (Zero-Window Startup)

The gateway itself (not just cron subprocesses) can flash a console window when started. The inner wrapper `Hermes_Gateway.cmd` uses `pythonw.exe` (invisible), but the Startup folder entry or manual double-click can flash a minimized `cmd.exe` window.

### PowerShell One-Liner (Simplest for .bat Files)

When you need to start a CLI like `hermes gateway` or `hermes dashboard` from inside a `.bat` file without any visible window, use `Start-Process -WindowStyle Hidden`:

```batch
powershell -NoProfile -Command "Start-Process hermes -ArgumentList 'gateway' -WindowStyle Hidden"
```

This is simpler than a VBS wrapper — no separate file needed, just one inline command. The spawned process inherits the batch file's environment (PATH, env vars, etc.) so it finds `hermes` correctly.

Use this to replace `start "" hermes gateway` (which creates a visible new console window) in any batch launcher.

### VBS Silent Launcher

Create `data/gateway-service/Hermes_Gateway_Silent.vbs`:
```vbs
Dim objShell
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "/path/to/\your-hermes-path\\src\\hermes-agent"
objShell.Run "cmd.exe /c /path/to/\your-hermes-path\\data\\gateway-service\\Hermes_Gateway.cmd", 0, False
Set objShell = Nothing
```

The `0` window style = completely hidden. `False` = don't wait for it to finish.

### Startup Folder Entry

Point the Startup `.cmd` at the VBS launcher:
```cmd
@echo off
wscript.exe "/path/to/\your-hermes-path\\data\\gateway-service\\Hermes_Gateway_Silent.vbs"
exit /b 0
```

### Manual Launcher Shortcut

Create a `.lnk` shortcut at the portable root pointing to a `Start_Gateway.cmd` that also calls the VBS. Use PowerShell to create the shortcut:
```powershell
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut('/path/to/\your-hermes-path\\Start Gateway.lnk')
$shortcut.TargetPath = '/path/to/\your-hermes-path\\data\\gateway-service\\Start_Gateway.cmd'
$shortcut.WorkingDirectory = '/path/to/\your-hermes-path\\data\\gateway-service'
$shortcut.Description = 'Start Hermes Gateway silently (no window flash)'
$shortcut.Save()
```

### Which Approach to Use

| Scenario | Solution |
|----------|----------|
| Inline fix in an existing `.bat` file | `Start-Process -WindowStyle Hidden` (no extra file) |
| Startup folder / scheduled task | VBS wrapper with `WScript.Shell.Run ... , 0` |
| Double-click launcher that needs working directory | VBS (sets `CurrentDirectory`) |
| CLI tool where output must be captured, invisibly | VBS wrapper with `WScript.Shell.Exec` + `cscript //Nologo` |

## Verification

After fixing, run a cron job with `cronjob action=run job_id=<id>` and watch Task Manager on Windows — no `hermes.exe` or `gh.exe` process should appear briefly.

For the gateway launcher, double-click `Start Gateway.lnk` and verify no window flashes at all (not even minimized).
