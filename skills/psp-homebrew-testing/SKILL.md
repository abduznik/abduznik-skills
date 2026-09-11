---
name: psp-homebrew-testing
description: Test and debug PSP homebrew on PPSSPP emulator for Windows — deploy EBOOT, capture screenshots, read debug logs, manage emulator config and processes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [psp, testing, ppsspp, emulator]
    category: software-development
---



# PSP Homebrew Testing (PPSSPP on Windows)

Test workflow for PSP homebrew builds using PPSSPP on Windows. Covers deploying EBOOTs, capturing visual output, reading debug logs, and managing PPSSPP process lifecycle.

## Prerequisites

- PPSSPP installed on Windows (`/path/to/emulators\ppsspp\PPSSPPWindows64.exe`)
- PSP homebrew EBOOT.PBP built with pspdev toolchain
- Game data files (CRITTER.DAT, MASTER.DAT, DATA/ etc.) alongside EBOOT

## PPSSPP Config Management

Config lives at: `<memstick>/PSP/SYSTEM/ppsspp.ini`

Key settings to toggle:

| Setting | Section | Effect |
|---------|---------|--------|
| `iShowFPSCounter = 1` | `[Graphics]` | Show FPS overlay (0=off, 1=FPS, 2=FPS+speed, 3=detailed) |
| `FileLogging = True` | `[General]` | Enable PPSSPP logging to file |
| `AutoRun = True` | `[General]` | Auto-run last booted game on launch |

**NOTE:** Changes to `ppsspp.ini` only take effect on PPSSPP restart. Running PPSSPP processes cache the config at startup.

## Deploying to PPSSPP

1. Place EBOOT.PBP + assets in `<memstick>/PSP/GAME/<SOMEID>/`
   - Folder name (e.g. `FOUT00002`) becomes the game's entry name in PPSSPP browser
   - Folder ID (6 chars from PARAM.SFO) used for playtime tracking in `[PlayTime]` section
2. Launch PPSSPP with game path as argument:
   ```
   /f/emulators/ppsspp/PPSSPPWindows64.exe "/f/emulators/ppsspp/memstick/PSP/GAME/FOUT00002/EBOOT.PBP"
   ```
3. Alternative: launch PPSSPP normally, navigate game browser to the entry, press Enter/X

## Capturing Screenshots

The FPS counter and other PPSSPP overlays are NOT captured by PSP internal framebuffer dumps (sceIoWrite, etc.). They render in PPSSPP's Vulkan/D3D presentation layer.

Use Windows screen capture (PowerShell) to capture the full PPSSPP window including overlays:

```powershell
Add-Type -AssemblyName System.Drawing,System.Windows.Forms
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bounds.Size)
$bmp.Save("/tmp/screenshot.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
```

Run from git-bash via:
```
powershell.exe -ExecutionPolicy Bypass -File C:/path/to/script.ps1
```

**IMPORTANT:** The PPSSPP window must be visible and not minimized. Use `ShowWindow` + `SetForegroundWindow` Win32 APIs to activate it before capture if needed.

## Reading PSP Debug Logs

PSP homebrew can write debug output via `sceIoWrite` to the memstick. Common paths:
- `<memstick>/psp_debug.txt`
- `<memstick>/palette_log.txt`
- `<memstick>/showrect_log.txt`
- `<memstick>/ppsspp.log` (PPSSPP emulator log)

To check if the game is actually running (vs PPSSPP sitting on game browser):
- Check PSP debug logs for `svga_init` success, `createRenderer OK`, frame loop timestamps
- Check PPSSPP log for game load traces
- Compare log file modification timestamps

## Process Management

**Kill all zombie PPSSPP processes:**
```
cmd.exe //c "taskkill /F /IM PPSSPPWindows64.exe"
```

**Launch game directly (background):**
```
/f/emulators/ppsspp/PPSSPPWindows64.exe "/f/emulators/ppsspp/memstick/PSP/GAME/FOUT00002/EBOOT.PBP"
```

**Send keystrokes to activate and control PPSSPP:**
```powershell
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class WinAPI {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$hwnd = (Get-Process PPSSPPWindows64)[0].MainWindowHandle
[WinAPI]::ShowWindow($hwnd, 1); [WinAPI]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("~")  # Enter
```

## Pitfalls

- **Zombie processes:** PPSSPP processes accumulate if not cleanly exited. Always `taskkill /F` before restarting.
- **Config changes ignored:** PPSSPP reads `ppsspp.ini` at startup. Changes to a running instance's config file have no effect.
- **Vulkan overlay not in framebuffer dumps:** The FPS counter and emulator overlays are rendered by PPSSPP's GPU presentation layer. Internal PSP framebuffer dumps (via sceIoWrite) will NOT show them. Always use Windows `CopyFromScreen` for overlay-inclusive screenshots.
- **AutoRun ambiguity:** `AutoRun=True` runs the LAST booted game. A fresh PPSSPP install with no boot history goes to game browser regardless.
- **SendKeys unreliability:** `SendKeys` only works if the target window is in the foreground. `SetForegroundWindow` may fail if another app (like a UAC prompt or terminal) has focus.

## See Also

- `windows-environment` skill — general Windows/git-bash usage
- `references/ppsspp-settings.md` — PPSSPP config details
