---
name: embedded-porting-patterns
description: Porting C/C++ CMake+SDL2 applications to new embedded/handheld platforms (PSP, Vita, 3DS, etc.) by following existing fork patterns without touching core game logic.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [embedded, porting, cmake, sdl2]
    category: software-development
---




# Embedded / Game-Engine Platform Porting Patterns

Class of work: taking an existing C/C++ application (CMake + SDL2) that ships for desktop/mobile and adding support for a new embedded/handheld platform. The canonical example is porting `fallout1-ce` (or similar) to PSP/Vita/3DS by adding a platform branch — never modifying core game logic.

## Guiding Principles

1. **Platform branch, not fork of logic.** The upstream repo's game engine, render path, and asset pipeline are untouched. New files go under `os/<platform>/`. Conditionals go in shared files under `#ifdef __<PLATFORM>__`.
2. **Copy the pattern of an existing platform fork.** For PSP, use the Vita fork (`Northfear/fallout1-ce-vita`) as the structural reference. Diff it against upstream to see what a complete platform block looks like in CMakeLists.txt.
3. **One platform branch per commit series** — never mix unrelated port work.

## Workflow

### 1. Setup
- Fork the upstream repo with a `-psp` / `-vita` etc. suffix in the clone name
- Clone the reference fork (e.g. `Northfear/fallout1-ce-vita`) alongside for quick `diff` access
- Initialize a build directory on the cross-compilation host

### 2. Toolchain
- Install or locate the platform toolchain (e.g. `pspdev` for PSP)
- Verify with a stand-alone "hello world" SDL2 CMake project BEFORE touching the game repo
- Key verification: `find_package(SDL2)` resolves against the toolchain's packaged SDL2 (not building from source)

### 3. CMake Integration
Add an `if(<PLATFORM>)` block in `CMakeLists.txt` that:
- Sets platform compiler flags (architecture-specific, not copied verbatim from other platforms)
- Routes SDL2 lookup through `find_package(SDL2)` (skip `third_party/sdl2` source build)
- Links platform-native libraries (e.g. `pspctrl`, `pspgu`, `pspdebug` for PSP)
- Includes `os/<platform>/<platform>.cmake` for packaging (EBOOT/PBP, icon, metadata)

### 4. Platform Scaffold (files to create)
- `os/<platform>/<platform>.cmake` — packaging rules (EBOOT, icon, PARAM.SFO, title)
- `os/<platform>/icon.png` — placeholder icon (replaceable later)
- Modify `src/plib/gnw/winmain.cc` — platform init block (chdir, controller init, debug screen)
- Modify `src/plib/gnw/dxinput.cc` — input source (game controller, analog sticks)
- Modify `src/plib/gnw/input.cc` — cursor mapping (stick → mouse)
- Include `<pspkernel.h>` / `<pspdebug.h>` etc. in the PSP init in the file, not in headers

### 5. Debug Output (critical — C printf doesn't work on many embedded systems)
On PSP specifically:
- **C `printf()`** goes through newlib → `write(1,...)` → `sceIoWrite(1,...)`. This is NOT captured by PPSSPP's log (which captures `sceKernelPrintf` syscalls).
- **C `fopen()`** needs the full `ms0:/` device prefix — bare `/` paths may point to unwritable flash.
- **Working channels (PSP):**
  - Native file API: `sceIoOpen("ms0:/debug.txt", PSP_O_WRONLY|PSP_O_CREAT, 0777)` + `sceIoWrite()` + `sceIoClose()` — requires `<pspiofilemgr.h>`
  - On-screen: `pspDebugScreenInit()` + `pspDebugScreenPrintf()` — writes to VRAM. Must be called BEFORE SDL2 takes over the display; the text may be overwritten by GPU rendering.
  - Kernel printf: `sceKernelPrintf()` captured by PPSSPP, but NOT directly callable from user-space. Install via `pspDebugInstallKprintfHandler()`.
- **Verify the debug channel works** with a known marker string before trusting it for diagnostic data.
- For other platforms (Vita, 3DS), check the reference fork for their equivalent debug channel.

### 6. Build & Deploy Loop
1. Commit, push to GitHub
2. SSH to cross-compilation host, pull, build
3. Deploy EBOOT.PBP to emulator memstick
4. Run emulator, capture screenshots or log output
5. Iterate

Use `ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null` if host key caching causes connection hangs (common with Tailscale/residential proxies).

### 7. Rendering Pitfalls (PSP-specific)
- The PSP SDL2 backend uses a **16-bit RGB565** framebuffer via `sceGu`. The game engine creates an **8-bit paletted surface** (`SDL_CreateRGBSurface(depth=8, ...)`) and calls `SDL_SetPaletteColors()`. The INDEX8 → RGB565 conversion during `SDL_BlitSurface` may silently fail or produce wrong colors.
- Direct pixel writes to `gSdlTextureSurface->pixels` may NOT reach the screen — the PSP SDL2 backend uses GPU-managed texture memory.
- Do NOT modify `SDL_HINT_RENDER_DRIVER="opengl"` or `SDL_WINDOW_OPENGL` — the PSP SDL2 backend ignores these gracefully. Removing them causes regressions.
- Do NOT change the internal resolution from 640×480 to 480×272 — the engine coordinates depend on 640×480.
- **To diagnose palette issues, use `sceIoWrite` to dump palette entries to a file** — on-screen debug may be overwritten by GPU.

## Platform-Specific Libraries to Link

### PSP (pspdev toolchain)
```
pspctrl    — controller input
pspdebug   — pspDebugScreenInit/Printf (link explicitly)
pspgu      — graphics engine
pspgum     — matrix utilities
pspvfpu    — vector FPU
pspiofilemgr — file I/O (header only for sceIoOpen/Write/Close)
```

## Reference Files
- `references/psp-debug-output.md` — full transcript of which debug channels work on PSP and PPSSPP

## Pitfalls
- **PSPDEV env var must be set** before running cmake: `export PSPDEV=/usr/local/pspdev && export PATH=$PSPDEV/bin:$PATH`
- **pspdebug library is NOT auto-linked by pspdev.cmake** — must be added to `target_link_libraries()` explicitly (unlike pspctrl/pspgu which come through the toolchain default libs)
- **fopen("ms0:/...") may still work**, but sceIoOpen is more reliable. If fopen returns NULL, try sceIoOpen — don't assume the path is wrong.
- **SSH connectivity** to the cross-compilation host may appear intermittent because of host key verification mismatches. Use the flags above to avoid false "host unreachable" conclusions.
- **Force-push never** — always `git push origin main` without `--force`. The user has explicitly rejected force-push.
