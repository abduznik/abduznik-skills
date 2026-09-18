---
name: psp-development
title: Playstation Portable Homebrew Development
category: software-development
description: >
  Cross-compile, debug, and test PSP homebrew using the pspdev toolchain
  and PPSSPP emulator. Covers CMake scaffold, debug channels, runtime
  analysis, and common render-pipeline pitfalls unique to PSP hardware.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [psp, homebrew, pspdev, ppsspp, cross-compile]
    category: software-development
triggers:
  - psp homebrew
  - pspdev
  - PPSSPP
  - psp-gcc
  - EBOOT.PBP
  - fallou1-ce-port
---


# PSP Homebrew Development

## Session Start-up Procedure

Before doing any work on a PSP port project:

1. **Check for process docs in the repo root.** Look for `WORKING_NOTES.md`, `AGENTS.md`, `README.md`, or any file that records how work is done on this project. Read it before touching code, theorising about bugs, or making claims about what's working.

2. **Check for a project state document** (`STATUS.md` or similar). This tells you what's verified working, what's not yet verified, and what the current gate/blocker is. Update your understanding of HEAD commit before relying on it if the doc is stale.

3. **Identify the gate condition.** Many PSP port projects have a visual gate — the agent is vision-blind and cannot confirm screenshots, emulator output, or colours from logs alone. Find what specifically the user needs to confirm before you can proceed to the next step.

4. **Ask the user before proceeding past the gate.** Report what you found — the state, the gate, what's blocking — and explicitly wait for a verdict. Do not keep working past a visual gate on the assumption it's fine.

5. **Never narrate visual success** ("it renders in colour now", "the background looks correct") from log data, return codes, or hope. That claim requires user confirmation.

6. **Update WORKING_NOTES.md** when you discover new process discipline during a session — keep it short and durable, not a per-task log.

## Environment

- **Toolchain**: pspdev (pre-built, installed at `/usr/local/pspdev/` on Ubuntu homelab)
- **Cross-compiler**: `psp-gcc` / `psp-g++` (GCC 15.2.0, MIPS R3000 / Allegrex target)
- **CMake**: uses `$PSPDEV/psp/share/pspdev.cmake` toolchain file + `-DPSP=ON`
- **SDK**: PSPSDK headers + stub libraries under `/usr/local/pspdev/psp/sdk/`
- **Build host**: Linux (Ubuntu 24.04) — pspdev Windows build is not available
- **Test host**: Windows 10/11 via PPSSPP emulator (`PPSSPPWindows64.exe`)

## Build Scaffold

### CMakeLists.txt PSP Block
Add an `if(PSP)` block that:
1. Sets Allegrex/MIPS compiler flags (`-O2 -G0 -DNDEBUG`)
2. Links platform libraries:
   ```cmake
   target_link_libraries(${EXECUTABLE_NAME}
       SDL2::SDL2
       SDL2::SDL2main
       pspctrl       # controller input
       pspdebug      # debug screen functions (optional, see Pitfalls)
       pspgu         # graphics engine
       pspgum        # matrix math
       pspvfpu       # vector FPU
   )
   ```
3. Includes an `os/psp/psp.cmake` for EBOOT packaging (`create_pbp_file()`)
4. Routes SDL2 lookup through `find_package(SDL2)` (PSP ships SDL2 as part of pspdev)

### Startup Entry
PSP programs start in `main(int argc, char* argv[])`. On pspdev, the entry sequence:
1. `chdir("ms0:/PSP/GAME/<GAME_ID>/")` — set working dir to where game data lives
2. `sceCtrlSetSamplingCycle(0); sceCtrlSetSamplingMode(PSP_CTRL_MODE_ANALOG)` — init input
3. SDL2 init (`SDL_InitSubSystem(SDL_INIT_VIDEO)`, then create window + renderer)
4. Game loop

### Code Segregation
Use `#ifdef __PSP__` in shared files, and dedicated files under `os/psp/`. The `__PSP__` define is injected automatically by the pspdev CMake toolchain — **do not** define it manually in CMakeLists or source.

## Testing on PPSSPP

### Running an EBOOT
```bash
PPSSPPWindows64.exe <path-to-EBOOT.PBP> --log=<logfile.txt>
```
### System Dialog Blocking

**Critical**: PSP homebrew often shows a system dialog on first boot (save data check, or **"Error initializing video mode 640x480"** when SDL2 video init fails). This dialog blocks the game's main loop — `SDL_UpdateTexture` / `SDL_RenderPresent` **never get called** until the dialog is dismissed.

**⚠️ Windows UIPI blocks SendKeys/SendInput from terminal sessions.** The `SendKeys` approach only works when PowerShell runs interactively on the Windows desktop with direct user focus. From a background/terminal process, both `SendKeys` and compiled C# `SendInput` return 0 (blocked by User Interface Privilege Isolation). Do NOT rely on SendKeys for automated headless testing.

#### ✅ Reliable Fix: Auto-Dismiss Thread

Spawn a low-priority PSP thread that waits 3 seconds then calls `sceUtilityMsgDialogAbort()`. This works entirely within the emulated PSP and needs no host-side input injection.

**Required includes:**
```c
#include <pspthreadman.h>           // sceKernelCreateThread, etc.
#include <psputility.h>             // base utility types
#include <psputility_msgdialog.h>   // sceUtilityMsgDialogAbort
```

**Required library linkage:**
```cmake
target_link_libraries(${EXECUTABLE_NAME}
    ...
    psputility
)
```

**Thread entry function (in winmain.cc PSP block):**
```c
int dialogDismissThread(SceSize args, void* argp)
{
    sceKernelDelayThread(3000000);          // Wait 3s for dialog to appear
    sceUtilityMsgDialogAbort();             // Dismiss it
    sceKernelExitDeleteThread(0);
    return 0;
}
```

**Spawn during PSP platform init:**
```c
SceUID dismissThread = sceKernelCreateThread("dialog_dismiss",
    (SceKernelThreadEntry)dialogDismissThread,
    0x11, 0x1000, PSP_THREAD_ATTR_USER, NULL);
if (dismissThread >= 0) {
    sceKernelStartThread(dismissThread, 0, NULL);
}
```

PPSSPP log confirmation:
```
0=sceUtilityMsgDialogAbort()        → STATUS_NONE → game init continues
```

**⚠️ Caveat**: `sceUtilityMsgDialogAbort()` sets `buttonPressed=UNKNOWN1` (0), not `YES` (1). Some game code checks this field and exits on abort but continues on YES. If the game exits after dismiss, the dialog may have been a FATAL ERROR (e.g., "Error initializing video mode") — see "Diagnosing svga_init/createRenderer failures" below.

#### Fallback: PowerShell SendKeys (interactive only)
```powershell
Start-Process -FilePath "PPSSPPWindows64.exe" -ArgumentList "EBOOT.PBP"
Start-Sleep -Seconds 8
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
```

### Screenshot Capture (for headless/remote testing)

The agent **cannot see rendered output** directly. All visual checks must go to the human via Telegram. Use PowerShell to capture screenshots:

**Window capture (Alt+PrintScreen to clipboard):**
```powershell
$wshell = New-Object -ComObject wscript.shell
$wshell.AppActivate("PPSSPP")
Start-Sleep 1
[System.Windows.Forms.SendKeys]::SendWait("%{PRTSC}")
Start-Sleep 1
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$bmp = [System.Windows.Forms.Clipboard]::GetImage()
$bmp.Save("/tmp/screenshot.png", [System.Drawing.Imaging.ImageFormat]::Png)
```

**Full desktop capture (larger files, more context):**
```powershell
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$bmp.Save("/tmp/screenshot.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
```

**Important:** 
- Set `FullScreen = False` in `ppsspp.ini` before capture sessions (otherwise PPSSPP takes over the display and screenshots show black)
- Revert `FullScreen = True` after testing
- Send to Telegram via `MEDIA:/f/screenshot.png` in the response
- Do NOT interpret visual content yourself — ask the user specific questions

### EBOOT.PBP Locked by Anti-Virus Workaround

Windows Defender sometimes holds an exclusive lock on `EBOOT.PBP` after PPSSPP accesses it, preventing overwrite/deletion even after PPSSPP exits. Symptoms: `rm: cannot remove 'EBOOT.PBP': Device or resource busy`, all copy/rename operations fail.

**Cause:** Orphan PPSSPP processes accumulate across testing sessions — each `start` or `Start-Process` call launches a new instance, and previous instances often remain running. Over many test cycles, 6+ zombie PPSSPP processes have been observed simultaneously, all holding file handles on `EBOOT.PBP`. Check with `tasklist /FI "IMAGENAME eq PPSSPPWindows64.exe"` (or `ps aux | grep -i ppsspp` in git-bash). Kill all:  
```bash
taskkill /F /IM PPSSPPWindows64.exe
```

If it's still locked after killing PPSSPP (e.g., Windows Defender real-time scanning), use the workaround directory:

**Fix:** Create an alternate game directory (e.g., `FOUT00002`) with a copy of the new EBOOT and game data. Update the game's `chdir()` call to point to the new directory, rebuild, and deploy there:

```bash
mkdir -p "/f/emulators/ppsspp/memstick/PSP/GAME/FOUT00002"
cp CRITTER.DAT MASTER.DAT    "/f/emulators/ppsspp/memstick/PSP/GAME/FOUT00002/"
cp -r DATA                   "/f/emulators/ppsspp/memstick/PSP/GAME/FOUT00002/"
cp new_eboot.pbp             "/f/emulators/ppsspp/memstick/PSP/GAME/FOUT00002/EBOOT.PBP"
# Patch winmain.cc to chdir to FOUT00002, rebuild
PPSSPPWindows64.exe ".../FOUT00002/EBOOT.PBP"
```

The game's startup code calls `chdir("ms0:/PSP/GAME/FOUT0000X/")` to find data files. The EBOOT is loaded into RAM at boot, so its on-disk location doesn't matter for code execution.

### FullScreen Toggle for Screenshot Capture

PPSSPP's `FullScreen = True` setting prevents desktop screenshot capture (PPSSPP takes over the display, producing black images). Before any screenshot session, set to False in `memstick/PSP/SYSTEM/ppsspp.ini`, then revert after:

```bash
# Before capture:
sed -i 's/FullScreen = True/FullScreen = False/' "$PPSSPP_CONFIG"
# After capture:
sed -i 's/FullScreen = False/FullScreen = True/' "$PPSSPP_CONFIG"
```

### FPS Counter (Overlay, Not Framebuffer)

PPSSPP's built-in FPS counter is an **emulator overlay** rendered by PPSSPP's own UI layer — it is NOT part of the PSP framebuffer. This distinction matters for testing:

- **Framebuffer dumps** (e.g. `sceIoWrite` to a debug file, or any capture of the game's output buffer) will NEVER show the FPS counter — they only contain game pixels
- To see the FPS counter, you must capture the **full PPSSPP window** (desktop screenshot via PowerShell's `CopyFromScreen`)

**Enabling the FPS counter:**

Add this setting under `[Graphics]` in `/path/to/ppsspp.ini`:
```ini
iShowFPSCounter = 1
```

Values:
- `0` = Off (default)
- `1` = FPS counter only
- `2` = FPS + speed percentage
- `3` = Detailed stats

**Capturing for visual testing:**

Use a full desktop screenshot via PowerShell (see "Screenshot Capture" above). The `CopyFromScreen` method captures the PPSSPP overlay along with the game image. Do NOT use framebuffer dumps for performance assessment — they only contain game pixels, not the overlay.

**Troubleshooting:** If the FPS counter doesn't appear after setting the ini:
1. Verify the setting was added under the `[Graphics]` section, not accidentally placed under `[General]` or another section
2. Kill all PPSSPP processes first (`taskkill /F /IM PPSSPPWindows64.exe`) — settings are read at startup and cached until the process exits; stale processes won't pick up changes
3. Check that the ini file was saved with correct line endings (the entry should be on its own line in the `[Graphics]` section)

### Log Analysis
Use `--log` to capture PPSSPP's console. Key log markers:
- `sceUtilityMsgDialogUpdate` — system dialog is active (main loop blocked)
- `sceGeListEnQueue` — display list submitted (game is rendering)
- `sceDisplaySetFrameBuf` — framebuffer swapped
- `PRINTFEnabled` does NOT capture C `printf()` — it captures `sceKernelPrintf`

## Diagnosing svga_init / createRenderer Failures

When a PSP build boots but shows an error dialog (often "Error initializing video mode 640x480") followed by `exit(1)`, the root cause is usually **SDL2 video init failure inside `createRenderer()`**.

This presents as: game starts → system dialog appears → `sceUtilityMsgDialogAbort()` → `exit(1)` immediately after. The game NEVER enters its render loop.

### The Five-Call Chain in createRenderer

```cpp
static bool createRenderer(int width, int height) {
    gSdlRenderer = SDL_CreateRenderer(gSdlWindow, -1, 0);     // 1
    SDL_RenderSetLogicalSize(gSdlRenderer, width, height);     // 2
    gSdlTexture = SDL_CreateTexture(gSdlRenderer,
        SDL_PIXELFORMAT_RGB888, SDL_TEXTUREACCESS_STREAMING, width, height); // 3
    SDL_QueryTexture(gSdlTexture, &format, NULL, NULL, NULL);  // 4
    gSdlTextureSurface = SDL_CreateRGBSurfaceWithFormat(        // 5
        0, width, height, SDL_BITSPERPIXEL(format), format);
}
```

Known PSP SDL2 backend failure modes:
- **SDL_CreateRenderer** with `SDL_HINT_RENDER_DRIVER="opengl"` — harmless on PSP, but if no driver computes, returns NULL
- **SDL_CreateTexture** with `SDL_PIXELFORMAT_RGB888` — PSP GPU only does 16-bit textures (RGB565). Requesting RGB888 may fail or degrade silently
- **SDL_RenderSetLogicalSize(640, 480)** — PSP native display is 480×272; a larger logical size may be rejected

### Step-by-Step File Logging (the reliable diagnostic)

Since on-screen debug conflicts with SDL2 and printf doesn't reach PPSSPP's log, use per-step file writes:

```cpp
static void psp_debug_log(const char* msg) {
#ifdef __PSP__
    SceUID fd = sceIoOpen("ms0:/psp_debug.txt",
        PSP_O_WRONLY | PSP_O_CREAT | PSP_O_APPEND, 0777);
    if (fd >= 0) { sceIoWrite(fd, msg, strlen(msg)); sceIoClose(fd); }
#endif
}
```

Add a marker before each call in `svga_init()` / `createRenderer()`. After running on PPSSPP, check `/path/to/psp_debug.txt`. The FAILED marker tells you the exact failing call.

**Known result from Fallout 1 CE PSP port:** Calls 1-2 (SDL_InitSubSystem, SDL_CreateWindow) succeed. The failure is at **Call 3 — `SDL_CreateTexture`** with `SDL_PIXELFORMAT_RGB888` at 640×480. The PSP SDL2 renderer has a hard **512×512 texture dimension limit** (Media Engine GPU constraint). Error: `"Texture dimensions are limited to 512x512"`.

**Fix:** Use surface-based rendering — see "Surface-Based Rendering Workaround" below.

### In-Memory Buffer Logging (when sceIoWrite fails after SDL calls)

On PSP, some SDL calls (`SDL_CreateRenderer`, `SDL_CreateTexture`) can corrupt or exhaust the PSP's file I/O subsystem, causing subsequent `sceIoOpen`/`sceIoWrite` calls to fail silently. When `psp_debug_log` output stops mid-function after an SDL call, use an in-memory buffer instead:

```cpp
static char crBuf[2048];
int crPos = 0;
#define CRLOG(fmt, ...) do { \
    int n = snprintf(crBuf + crPos, sizeof(crBuf) - crPos - 1, fmt, ##__VA_ARGS__); \
    if (n > 0) crPos += n < (int)(sizeof(crBuf) - crPos) ? n : (int)(sizeof(crBuf) - crPos - 1); \
} while(0)
```

Accumulate all log lines into `crBuf` via `CRLOG(...)` during the function, then write the entire buffer in one shot at the end:

```cpp
// At end of function (both success and failure paths):
{ SceUID fd = sceIoOpen("ms0:/debug.txt",
    PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777);
  if (fd >= 0) { sceIoWrite(fd, crBuf, strlen(crBuf)); sceIoClose(fd); } }
```

This was essential for diagnosing the `SDL_CreateTexture` failure — the per-line file writes inside `createRenderer()` produced no output because SDL had broken the PSP file system state, but the in-memory buffer captured the full sequence.

### ⚠️ PSP SDL2 Silent Blit Failure: INDEX8→RGB565 Bug

**Critical finding:** PSP SDL2's `SDL_BlitSurface` has a silent failure mode when blitting from an INDEX8 (paletted) surface to an RGB565 surface that was created via `SDL_CreateRGBSurfaceWithFormat` (a "separately-allocated" surface). The function:

- Returns `0` (success)
- Sets `SDL_GetError()` to empty string
- **But writes NO pixels** to the destination surface — all destination pixels remain 0x0000 (black)

This differs from blitting to the **window surface** returned by `SDL_GetWindowSurface()`, which DOES work. The bug only manifests on surfaces you allocate yourself.

**Why it matters:** If your rendering pipeline creates an intermediate surface for palette conversion (as the two-step approach does), `SDL_BlitSurface(gSdlSurface, NULL, gSdlTextureSurface, NULL)` silently produces a black intermediate. `SDL_BlitScaled` then scales black to the window — you get grayscale/blocky output because the intermediate has no pixel data.

**Diagnostic technique:** After `SDL_BlitSurface(INDEX8→RGB565)`, check actual pixel values:

```cpp
Uint16* px = (Uint16*)gSdlTextureSurface->pixels;
// If px[0] == 0x0000 after blit, surface was NOT populated despite ret=0
```

**Fix — manual pixel conversion:** Replace `SDL_BlitSurface` with pixel-by-pixel conversion that reads the palette directly:

```cpp
static void psp_convert_index8_to_rgb565(SDL_Surface* src, const SDL_Rect* srcRect,
                                          SDL_Surface* dst, int dstX, int dstY) {
    if (!src || !dst || !src->format->palette) return;
    SDL_Color* colors = src->format->palette->colors;
    int srcPitch = src->pitch;
    int dstPitch = dst->pitch;
    int dstBpp = dst->format->BytesPerPixel;  // = 2 for RGB565

    int sx = srcRect ? srcRect->x : 0;
    int sy = srcRect ? srcRect->y : 0;
    int sw = srcRect ? srcRect->w : src->w;
    int sh = srcRect ? srcRect->h : src->h;
    if (sx + sw > src->w) sw = src->w - sx;
    if (sy + sh > src->h) sh = src->h - sy;
    if (sw <= 0 || sh <= 0) return;

    Uint8* srcBase = (Uint8*)src->pixels + sy * srcPitch + sx;
    Uint8* dstBase = (Uint8*)dst->pixels + dstY * dstPitch + dstX * dstBpp;

    for (int y = 0; y < sh; y++) {
        for (int x = 0; x < sw; x++) {
            Uint8 index = srcBase[x];
            Uint16 pixel = ((colors[index].r >> 3) << 11) |
                           ((colors[index].g >> 2) << 5) |
                           (colors[index].b >> 3);
            ((Uint16*)dstBase)[x] = pixel;
        }
        srcBase += srcPitch;
        dstBase += dstPitch;
    }
}
```

**Integration at all three call sites:**

The manual conversion must replace `SDL_BlitSurface` in THREE places, not one:

**Call site 1 — `GNW95_SetPaletteEntries` (partial palette update + full re-blit):**
```cpp
void GNW95_SetPaletteEntries(unsigned char* palette, int start, int count) {
    // ... set SDL_SetPaletteColors(...) ...
#ifdef __PSP__
    psp_convert_index8_to_rgb565(gSdlSurface, NULL, gSdlTextureSurface, 0, 0);
#else
    SDL_BlitSurface(gSdlSurface, NULL, gSdlTextureSurface, NULL);
#endif
}
```

**Call site 2 — `GNW95_SetPalette` (full palette set + full re-blit):**
```cpp
void GNW95_SetPalette(unsigned char* palette) {
    // ... set SDL_SetPaletteColors(...) ...
#ifdef __PSP__
    psp_convert_index8_to_rgb565(gSdlSurface, NULL, gSdlTextureSurface, 0, 0);
#else
    SDL_BlitSurface(gSdlSurface, NULL, gSdlTextureSurface, NULL);
#endif
}
```

**Call site 3 — `GNW95_ShowRect` (per-rect dirty-region blit):**
```cpp
void GNW95_ShowRect(unsigned char* src, unsigned int srcPitch, ...,
                    unsigned int destX, unsigned int destY) {
    buf_to_buf(..., gSdlSurface->pixels + ...);  // copy pixels to INDEX8

    SDL_Rect srcRect = { destX, destY, srcWidth, srcHeight };
    SDL_Rect destRect = { destX, destY, 0, 0 };
#ifdef __PSP__
    psp_convert_index8_to_rgb565(gSdlSurface, &srcRect, gSdlTextureSurface, destX, destY);
#else
    SDL_BlitSurface(gSdlSurface, &srcRect, gSdlTextureSurface, &destRect);
#endif
}
```

Note: the `srcRect` uses `destX, destY` because `buf_to_buf` already placed
the incoming pixel data at that offset within `gSdlSurface` — the rect origin
is where the NEW pixels live in `gSdlSurface`, not a crop into the source buffer.

**Why text overlays worked while full-frame blits didn't (diagnostic insight):**

PSP SDL2's `SDL_BlitSurface` from INDEX8→RGB565 has TWO code paths internally:
- **NULL rect (= full surface):** Returns 0, writes NOTHING (silent no-op)
- **Non-NULL rect (= specific region):** Works correctly, writes pixel data

The game's palette-update functions use `SDL_BlitSurface(gSdlSurface, NULL, ...)`
(NULL rect) which hits the broken path. `ShowRect` uses
`SDL_BlitSurface(gSdlSurface, &srcRect, ...)` (non-NULL rect) which hits the
working path.

**Result:** Text overlay (many ShowRect calls) renders correctly, but the
full-frame background never appears because the palette-change full blit
silently produces black. `SDL_BlitScaled` then scales black → grayscale output.

**Diagnostic rule for future debugging:** If text renders correctly but
backgrounds/FMV are grayscale/null, the bug is SPECIFICALLY in the
full-surface (NULL-rect) blit path, not the rect-blit path. Check destination
pixel data after `SDL_BlitSurface(..., NULL, ...)` even when it returns 0.

### ⚠️ 13. MVE Movie Frames Can Be Sub-Fullscreen, Creating Stale-Data Margins

**Critical finding for the Fallout 1 CE PSP port:** During MVE movie playback,
the decoded movie frame is NOT necessarily 640×480 (full screen). The MVE
decoder in `movie_lib.cc` produces frames at the MOVIE'S native resolution.
For the Vault-13 logo intro, the movie frame is **432×320 pixels** — only
45% of the full 640×480 framebuffer.

The movie frame is placed at **(movieX, movieY)** on the 640×480 INDEX8
surface (`gSdlSurface`). For the Vault-13 logo, movieX=104 and movieY=80
(from `MOVIEFRAME` diagnostic log). This leaves **four margin areas** that
are NOT covered by the movie blit:

| Margin | Columns | Rows | Size |
|--------|---------|------|------|
| Top | 0-639 | 0-79 | 640×80 |
| Left | 0-103 | 80-399 | 104×320 |
| Right | 536-639 | 80-399 | 104×320 |
| Bottom | 0-639 | 400-479 | 640×80 |

After the manual blit (or `SDL_BlitSurface`) copies the 432×320 movie frame
to gSdlSurface at (104,80), `psp_convert_index8_to_rgb565(gSdlSurface, NULL,
gSdlTextureSurface, 0, 0)` converts the **ENTIRE** 640×480 surface —
including all four margins with their **stale, unmodified data** from before
the movie started.

**Why this matters for debugging:**
- Stale data in the margins persists through the full-surface conversion AND
  through the `psp_manual_scale` downscale to 480×272
- Any text or UI elements that were on screen BEFORE the movie started will
  appear to "bleed through" the movie in the margin areas after scaling
- This is the most likely cause of the "duplicated mirrored text" artifact
  seen during the Vault-13 logo intro (text from the initial screen survives
  in the bottom/left margins)

**Diagnostic test:** Clear the margin areas to black before the movie blit
each frame. If the duplicated/mirrored artifacts disappear, the source is
confirmed as stale margin data:

```cpp
#ifdef __PSP__
// In movie_MVE_ShowFrame, before the blit:
int clearColor = 0;
Uint8* base = (Uint8*)gSdlSurface->pixels;
int p = gSdlSurface->pitch;
int fbW = gSdlSurface->w;  // 640
int fbH = gSdlSurface->h;  // 480
// Top margin
for (int y = 0; y < destRect.y; y++) memset(base + y * p, clearColor, fbW);
// Bottom margin
for (int y = destRect.y + srcRect.h; y < fbH; y++) memset(base + y * p, clearColor, fbW);
// Left/right margins within movie row range
for (int y = destRect.y; y < destRect.y + srcRect.h; y++) {
    Uint8* rowBase = base + y * p;
    memset(rowBase, clearColor, destRect.x);
    memset(rowBase + destRect.x + srcRect.w, clearColor, fbW - destRect.x - srcRect.w);
}
#endif
```

**Implication for the 30+ writes/present mystery:** The FRAME_PROFILE log
shows `writesSinceLast=32` at 15 FPS during movie playback. Since the
palette-change skip is active (confirmed by PALETTE_SKIP log), and
GNW95_ShowRect is NOT called during movie playback (confirmed by SHOWRECT
log showing 0 entries during movie), the only conversion happening is the
single `psp_convert_index8_to_rgb565` in `movie_MVE_ShowFrame`. One
conversion = 2 `gSdlTextureVersion` increments. At 15 FPS, that's 30
increments/sec. Over ~1.068s between FRAME_PROFILE entries: 30 × 1.068 =
32.04 ≈ 32. **The writes count is exactly and solely the movie frame
conversion. No mystery thrash.**

This means:
- GNW95_ShowRect does NOT fire during movie playback at all
- No UI overlay rendering happens during MVE playback
- The only work is: decode frame → blit → convert → scale → present

**Test result:** The margin-clearing test was deployed and tested against
the Vault-13 logo intro. The corruption was **IDENTICAL** — no improvement,
no change. This rules out stale margin data as the source of FMV corruption.

**Raw decode frame dump technique:** When per-surface hypotheses are
exhausted, compare the raw decoder output against the converted texture:

1. In `movie_MVE_ShowFrame`, write `gMovieSdlSurface1` raw INDEX8 pixels
   and palette to files on `ms0:/` using `sceIoOpen`/`sceIoWrite`
2. Write `gSdlTextureSurface` after conversion to a separate file
3. On the host, convert to viewable PNGs using Pillow:
   - INDEX8: read raw bytes → look up palette → RGB tuple → Image.putpixel
   - RGB565: unpack each 16-bit pixel as (r<<11)|(g<<5)|b, expand to 8-bit
4. Pixel-compare raw decode vs texture cropped to movie area

This isolates the corruption to either the decoder output (clean → bug in
convert/scale) or the decoder itself (corrupted → bug in movie_lib.cc).

See `references/psp-movie-corruption-debugging.md` "Hypothesis 4" for
detailed findings including the 12.5% pixel diff and cluster analysis.

## Surface-Based Rendering Workaround

When `SDL_CreateTexture` fails due to the 512×512 limit, **do not use the SDL renderer/texture pipeline at all**. Use two-step surface-based rendering:

**Step 1 — Create two surfaces in `createRenderer()`:**
```cpp
static bool createRenderer(int width, int height)
{
#ifdef __PSP__
    gSdlRenderer = NULL;
    gSdlTexture = NULL;
    // Window surface (PSP native 480x272 RGB565) — owned by SDL_DestroyWindow
    gSdlWindowSurface = SDL_GetWindowSurface(gSdlWindow);
    if (gSdlWindowSurface == NULL) return false;
    // Intermediate 640x480 surface (same pixel format as window) for palette conversion
    gSdlTextureSurface = SDL_CreateRGBSurfaceWithFormat(0, width, height,
        gSdlWindowSurface->format->BytesPerPixel * 8,
        gSdlWindowSurface->format->format);
    if (gSdlTextureSurface == NULL) return false;
    return true;
#else
    // ... normal renderer path ...
#endif
}
```

**Declare the window surface variable:**
```cpp
SDL_Surface* gSdlWindowSurface = NULL;  // PSP only, inside #ifdef __PSP__
```

### Step 2 — Per-frame presentation in `renderPresent()`:
```cpp
void renderPresent()
{
#ifdef __PSP__
    // Step A: GNW95_ShowRect already converted INDEX8→RGB565 via manual
    //         palette conversion to the 640x480 intermediate surface.
    // Step B: Scale the 640x480 RGB565 intermediate surface down to the
    //         480x272 window surface.
    SDL_BlitScaled(gSdlTextureSurface, NULL, gSdlWindowSurface, NULL);
    // Step C: Push the window surface to the display.
    SDL_UpdateWindowSurface(gSdlWindow);
#else
    // ... normal renderer path ...
#endif
}
```

**Update `destroyRenderer()` for PSP:**
```cpp
static void destroyRenderer()
{
#ifdef __PSP__
    if (gSdlTextureSurface != NULL) {
        SDL_FreeSurface(gSdlTextureSurface);  // our intermediate
        gSdlTextureSurface = NULL;
    }
    gSdlWindowSurface = NULL;  // owned by window, don't free
    gSdlTexture = NULL;
    gSdlRenderer = NULL;
}
```

**⚠️ CRITICAL: Why three issues, not one?** Getting PSP rendering working requires surmounting THREE separate bugs, not one:

1. **512×512 texture limit** — `SDL_CreateTexture` with 640×480 fails. Fix: surface-based rendering (skip renderer entirely).
2. **INDEX8+scaling in one call fails** — `SDL_BlitScaled(gSdlSurface, NULL, gSdlWindowSurface, NULL)` fails with `"Blit combination not supported"`. INDEX8→RGB565 conversion + downscale MUST be separate steps.
3. **SDL_BlitSurface silently fails INDEX8→RGB565 to separate surfaces** — `SDL_BlitSurface(gSdlSurface, NULL, gSdlTextureSurface, NULL)` returns 0 but writes nothing when `gSdlTextureSurface` was created via `SDL_CreateRGBSurfaceWithFormat`. Fix: manual palette→RGB565 conversion (`psp_convert_index8_to_rgb565`).

The working approach splits the work:
1. `GNW95_ShowRect` → `psp_convert_index8_to_rgb565(gSdlSurface, &rect, gSdlTextureSurface, ...)` — manual palette→RGB565 conversion, NO scaling, using pitch-corrected memory writes.
2. `renderPresent` → `SDL_BlitScaled(gSdlTextureSurface, NULL, gSdlWindowSurface, NULL)` — RGB565→RGB565 with 640→480 downscale. Same-format scaling IS supported.

**⚠️ Window flags must not include OpenGL on PSP:** `SDL_GetWindowSurface` requires a non-OpenGL window. Remove the OpenGL hint and flag:
```cpp
#ifndef __PSP__
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "opengl");
#endif
    Uint32 windowFlags = SDL_WINDOW_ALLOW_HIGHDPI;
#ifdef __PSP__
    windowFlags = 0;  // No OpenGL, no high-DPI
#else
    windowFlags |= SDL_WINDOW_OPENGL;
#endif
```

The window surface from `SDL_GetWindowSurface` returns the PSP-native 480×272 RGB565 surface (`fmt=0x15551002`, `bpp=2`). The intermediate surface is 640×480 in the same format.

**Performance note:** Both the palette conversion (GNW95_ShowRect) and scaling (renderPresent) run on the 333MHz MIPS CPU. Expect usable frame rates for turn-based games. Real-time action games may need VFPU-accelerated conversion or reduced internal resolution.

## PSP Debug Channels

### ✅ Works on PPSSPP
| Method | Code | Notes |
|--------|------|-------|
| Native PSP file I/O | `sceIoOpen("ms0:/debug.txt", PSP_O_WRONLY\|PSP_O_CREAT, 0777)` then `sceIoWrite()` | Write to memory stick. Requires `#include <pspiofilemgr.h>`. **Must use `ms0:/` device prefix.** |
| On-screen debug screen | `pspDebugScreenInit()` + `pspDebugScreenPrintf()` | BUT: **conflicts with SDL2** — see Pitfalls below. |

### ❌ Does NOT work on PPSSPP
| Method | Why |
|--------|-----|
| `fopen("ms0:/debug.txt", "w")` | Wrong path format or device not mounted — `fopen` returns NULL |
| `printf()` / `fprintf(stderr,...)` | Goes through `sceIoWrite(1)`, **NOT** the `sceKernelPrintf` channel that PPSSPP's `PRINTFEnabled` captures |
| `puts()` | Same as `printf` — goes through `sceIoWrite(1)` |

## Pitfalls

### 1. pspDebugScreenInit conflicts with SDL2
`pspDebugScreenInit()` calls `sceDisplaySetFrameBuf()` which reconfigures the PSP's display controller. If SDL2 has already set up the display (via `sceGu`), the debug screen init will either:
- Overwrite SDL2's framebuffer configuration (causing rendering glitches)
- Trigger a system "message dialog" that blocks the game's main loop indefinitely

**Fix**: Do NOT call `pspDebugScreenInit()` in code that also uses SDL2. Use `sceIoOpen`/`sceIoWrite` for file-based debug output instead.

### 2. PSP file paths need `ms0:/` prefix
On PSP, all file paths must start with the device prefix:
- `ms0:/` — Memory Stick (writable, use for debug output)
- `flash0:/` — Flash ROM (read-only system area)
- `umd:/` — UMD disc

Without the prefix, `fopen`/`sceIoOpen` returns an error.

### 3. PPSSPP system dialogs block render loop
On first boot, PSP homebrew often triggers a system dialog (save data management, language selection). This dialog:
- Uses PPSSPP's built-in PPGe rendering, NOT the game's SDL2 path
- Blocks the game thread at `sceUtilityMsgDialogUpdate()` — `renderPresent()` is never called
- Must be dismissed with a button press (ENTER/Cross button)

### 4. PSP SDL2 has a 512×512 texture dimension limit (hardware constraint)

The PSP's Media Engine GPU cannot handle textures larger than 512×512 in either dimension. `SDL_CreateTexture` with dimensions exceeding this (e.g., 640×480) fails with: `"Texture dimensions are limited to 512x512"`.

**Fix:** Use surface-based rendering instead of the renderer/texture pipeline. See "Surface-Based Rendering Workaround" above.

This is NOT a pixel format issue — the RGB888/RGB565 question is irrelevant when the texture itself won't fit. Even RGB565 textures at 640×480 would fail. The only paths forward are:
- Surface-based rendering (SDL_GetWindowSurface + SDL_BlitScaled)
- Reducing game resolution to ≤512 in both dimensions
- Tiling the output across multiple 512×512 textures

### 5. OpenGL hint and window flag must be removed on PSP

Two OpenGL-related settings in `svga_init()` prevent surface-based rendering on PSP:

```cpp
// WRONG on PSP — must be skipped:
SDL_SetHint(SDL_HINT_RENDER_DRIVER, "opengl");   // ← Remove via #ifndef __PSP__

// WRONG on PSP — SDL_GetWindowSurface needs a non-OpenGL window:
Uint32 windowFlags = SDL_WINDOW_OPENGL;           // ← Use windowFlags = 0 on PSP
```

If these are not removed:
- `SDL_GetWindowSurface` returns NULL or produces incorrect results
- The window is created in OpenGL mode, but PSP has no OpenGL driver
- Result: `createRenderer` fails or the display is corrupt

Fix:
```cpp
#ifndef __PSP__
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "opengl");
#endif

    Uint32 windowFlags = SDL_WINDOW_ALLOW_HIGHDPI;
#ifdef __PSP__
    windowFlags = 0;
#else
    windowFlags |= SDL_WINDOW_OPENGL;
#endif
```

### 7. Windows UIPI blocks host-side input injection

When running PPSSPP from a terminal/background process (`Start-Process`, cron job, CI), `SendKeys` and even compiled `SendInput` API calls return 0 and are silently blocked by Windows User Interface Privilege Isolation (UIPI). The only reliable way to dismiss PSP system dialogs in headless/automated sessions is the **Auto-Dismiss Thread** technique (see above).

### 8. psputility library needed for dialog functions

Functions like `sceUtilityMsgDialogAbort()` exist in `libpsputility.a`. You must:
1. Add `psputility` to `target_link_libraries()` in CMakeLists.txt
2. Include headers in the CORRECT ORDER:
   ```c
   #include <psputility.h>           // first — defines SceUtilityMsgDialogParams
   #include <psputility_msgdialog.h> // second — defines sceUtilityMsgDialogAbort
   ```
   Swapping the include order produces `'pspUtilityDialogCommon' does not name a type`.

### 9. Thread functions require `<pspthreadman.h>`

`sceKernelCreateThread`, `sceKernelStartThread`, `sceKernelExitDeleteThread`, and `sceKernelDelayThread` are declared in `<pspthreadman.h>`. The stubs are in the default kernel library set — no extra `target_link_libraries()` needed.

### 10. Palette-change callbacks trigger redundant full-surface conversions during FMV playback

During MVE movie playback, `GNW95_SetPaletteEntries` is called 2-3× per frame
(pre-frame and post-frame in `movie_lib.cc`'s MVE decoder). On PSP, this
function calls `psp_convert_index8_to_rgb565(gSdlSurface, NULL,
gSdlTextureSurface, 0, 0)` — a FULL 640×480 INDEX8→RGB565 conversion —
EVERY time, even though the frame data hasn't changed yet.

This creates a triple-conversion cascade per movie frame:
1. Pre-frame palette change → converts stale pixel data with new palette
   (temporarily corrupts `gSdlTextureSurface`)
2. `movie_MVE_ShowFrame` → blit new frame + correct conversion
3. Post-frame palette change → redundant re-conversion

Vita avoids this because `updateVita2dPalette()` writes palette to GPU
hardware registers without touching pixel data.

**Partial fix (insufficient):** Guard the conversion in
`GNW95_SetPaletteEntries`/`GNW95_SetPalette` with a `gIsMoviePlaying` flag
so the palette-change path skips the full-surface conversion when the movie
callback owns that responsibility.

**IMPORTANT — This fix was deployed and VERIFIED at runtime** (see
`references/psp-movie-corruption-debugging.md` for the full diagnostic
session). The `PALETTE_SKIP` diagnostic fires repeatedly during FMV
playback, confirming the fix is active, but it had **NO VISIBLE EFFECT**
on the corruption. The sectioned/blocky tearing persisted unchanged.

**What this means:** The palette-cascade theory, while plausible, is NOT
the root cause of FMV rendering corruption on PSP. The real source is
elsewhere — most likely the closed-source PSP SDL2 `SDL_BlitSurface` call
in `movie_MVE_ShowFrame` that blits decoded MVE frame data from
`gMovieSdlSurface1` to `gSdlSurface` (INDEX8→INDEX8). The PSP SDL2 binary
is pre-built and cannot be inspected; standard SDL2's INDEX8→INDEX8 blit
is well-tested, but the PSP fork may have bugs with specific src/dst rect
parameters or pitch calculation.

**Debugging protocol when a plausible fix has no visible effect:**
1. Add diagnostic logging INSIDE the guarded branch to confirm it fires
2. Add lifecycle logging at entry/exit (movieStart, cleanupMovie) to
   confirm the flag lifecycle
3. Add path-selection logging (Direct vs Buffered) to confirm which
   rendering path the specific screen uses
4. If the fix fires but corruption persists, the theory is WRONG —
   report this clearly and do NOT layer more fixes
### 11. sceIoWrite requires `<pspiofilemgr.h>` in EVERY file that uses it

The `sceIoOpen`, `sceIoWrite`, and `sceIoClose` functions are declared in
`<pspiofilemgr.h>`. If you add sceIo debug logging to a file that didn't
previously use it (e.g. `movie.cc`), you MUST add:

```cpp
#ifdef __PSP__
#include <pspiofilemgr.h>
#endif
```

The LSP (`clangd`) will report `'pspiofilemgr.h' file not found` on the
Windows host — this is expected since the PSP toolchain headers aren't on
the Windows include path. Ignore it; the `psp-gcc` cross-compiler on the
build server will find it.

Also remember to include `<stdio.h>` for `snprintf` if using formatted output.

### 12. PSP SDL2's SDL_BlitSurface is closed-source and suspected corrupt for INDEX8→INDEX8 blits

**Finding:** During MVE movie playback, the `SDL_BlitSurface(surface,
&srcRect, gSdlSurface, &destRect)` call in `movie_MVE_ShowFrame` copies
decoded INDEX8 frame data from the movie surface to the main framebuffer.
The PSP SDL2 binary is pre-built and cannot be inspected. Standard SDL2's
INDEX8→INDEX8 blitter is well-tested, but the PSP fork may have bugs with:

- Non-zero src/dest rect coordinates combined with specific pitch values
- Different pitch values between source and destination surfaces
- Palette pointer sharing after `SDL_SetSurfacePalette`

**Diagnostic technique:** Replace `SDL_BlitSurface` with a manual per-row
`memcpy` that bypasses the closed-source SDL2 blitter entirely. Both
surfaces are INDEX8 (1 byte/pixel), so the copy is straightforward:

```cpp
#ifdef __PSP__
{
    int copyW = srcRect.w;
    int copyH = srcRect.h;
    Uint8* srcRow = (Uint8*)surface->pixels + srcRect.y * surface->pitch + srcRect.x;
    Uint8* dstRow = (Uint8*)gSdlSurface->pixels + destRect.y * gSdlSurface->pitch + destRect.x;
    for (int y = 0; y < copyH; y++) {
        memcpy(dstRow, srcRow, copyW);
        srcRow += surface->pitch;
        dstRow += gSdlSurface->pitch;
    }
}
#else
    SDL_BlitSurface(surface, &srcRect, gSdlSurface, &destRect);
#endif
```

Keep `SDL_SetSurfacePalette` before the copy — it ensures the INDEX8 index
values map to the correct palette entries during subsequent conversion to
RGB565. The palette only needs to match; the raw byte copy doesn't use it.

**When to use:** Use THIS technique as a FIRST diagnostic step when rendering
corruption appears ONLY in animated content that goes through the MVE movie
decoder (`movie_MVE_ShowFrame`). If the corruption disappears with the
manual copy, you've confirmed the PSP SDL2 blitter is the cause. If it
persists, the corruption source is elsewhere.

**Actual test result (Fallout 1 CE PSP port):** The manual per-row `memcpy`
replacement was deployed (commit `5c9e975`) and tested against the Vault-13
logo intro which uses the Direct MVE path (`movie_MVE_ShowFrame`). The
corruption was **IDENTICAL** — no improvement, no change. This rules out
the closed-source SDL_BlitSurface as the root cause of FMV corruption.

**See also:** Pitfall 13 (MVE Movie Frames Can Be Sub-Fullscreen) for the
current working hypothesis about the actual source.

**Session reference:** See `references/psp-movie-corruption-debugging.md`
"Hypothesis 2" for the full test results including MOVIEFRAME coordinate
logs and the margin-stale-data diagnostic.

- CPU: MIPS R3000 (Allegrex, 333 MHz)
- FPU: VFPU (vector FPU, separate from main CPU)
- GPU: `sceGu` (renders via display lists, not OpenGL)
- RAM: 64MB (8MB reserved for kernel)
- VRAM: 2MB (within the 64MB)
- Screen: 480×272, RGB565 native
