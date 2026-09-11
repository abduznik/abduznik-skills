---
name: psp-prx-plugin-maintenance
description: Use when building/debugging PSP prx kernel plugins.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [psp, prx, plugin, release]
    category: software-development
---




# PSP PRX Plugin Maintenance

Building and debugging PSP **kernel plugins (.prx)** — cheat devices, VSH tools, sysmon overlays — especially when rebuilding legacy codebases with modern toolchains. Homebrew EBOOT ports are `psp-development`'s territory; this skill covers prx plugins and real-hardware validation.

## Trigger

- User reports a PSP plugin fork/rebuild crashes on real hardware ("CI passed but my PSP crashes")
- Working on TempAR / CWCheat-style prx plugins or any `seplugins/`-deployed kernel plugin
- Toolchain upgrade of a legacy PSP plugin (moving pspdev to GCC 14/15)

## Core rules

1. **CI green ≠ hardware-valid.** Rebuilding 2010s-era PSP plugin C with modern pspdev (GCC 14/15) can pass CI yet crash on a real PSP: the old code relies on UB (stack layout, OOB reads like `for(i=0;i<3;i++)` over a 2-element array) that newer compilers compile differently. The game may even boot and play intros, then crash at asset-load. Field-test the actual prx before claiming success, and tell the user explicitly that CI is not proof.
2. **Find the original working release binary FIRST.** Upstream repos often still host original release assets (e.g. `raing3/tempar` v1.6.4 tar.gz = the old-toolchain TempAR binary, 122,450 B). Download and diff: size, md5, `psp-readelf -S` section sizes (.text/.data/.bss). Near-identical sections → the regression is **codegen behavior, not footprint** — stop chasing memory-size theories.
3. **Keep the ELF for disassembly.** `make release` runs `clean` and deletes `src/*.elf`. Use `make prep <tgt>` so the ELF survives, then `psp-objdump -d src/<tgt>.elf | awk '/<fn>:/,/\$/'`. On Windows, objdump/readelf must run via the toolchain on the build host (homelab), not local.
4. **Sysmem partitions matter at game RAM peaks.** `sceKernelAllocPartitionMemory` from the game's own partitions (1/6) steals RAM the game needs at its asset-load peak → hard crash (GTA LCS pattern: boots, title cards, crash when 3D assets start). The original TempAR alloc list was `{9,1,6}` (still visible commented out in kmalloc.c). A "correct" loop-count fix that truncates the fallback partitions removes the safety net that made older builds survive. Fix: restore the author's original partition list AND **fail closed** — if all named partitions are exhausted, `return NULL` instead of calling `sceKernelAllocPartitionMemory(0, ...)` (partition 0 may silently draw from the game's pool).
5. **CFLAGS overrides drop include paths.** A command-line `CFLAGS=...` makes build.mak's `CFLAGS += -I...` inert (command-line vars ignore `+=`). Re-add explicitly: `-I$PSPDEV/psp/include -I$PSPSDK/include -Iinclude -Isrc`.
6. **Old toolchain images are gone from Docker Hub** (oldest `pspdev/pspdev` tag ≈ v20240701, GCC 14-era; `pspdev/pspsdk` no longer exists). Original codegen cannot be reproduced via Docker — diff against the original release binary instead.
7. **Multiple kernel plugins contaminate field tests.** If the stick carries other plugins (AutoCat, PSPSysMon, etc.), disable them for a clean control run before blaming the binary under test.

## Release workflow (GitHub Actions)

- Repos of this class often auto-release on `v*` tags via a build workflow (`docker run pspdev/pspdev make prep psp lite` + `make pack` + `softprops/action-gh-release`).
- Version bump: `RELVER` is hardcoded in the makefile — bump it or the packaged zip keeps the old name despite the new tag.
- Beware cp1252/MSYS mangling of non-ASCII commit messages on Windows git-bash — the pushed subject garbles (cosmetic; do not force-push history to fix it).
- Watch CI with `gh run watch <id> --repo <owner>/<repo> --exit-status`; verify release assets (prx sizes) after.

## Pitfalls

- Patch-tool edits on CRLF C sources mangled indentation this session — use a Python normalize-replace-save (match on `\n`, write back `\r\n`) for block edits in this codebase (same lesson as the homelab `repair_*.py` pattern).
- Windows Defender/vendors may delete freshly downloaded .prx binaries from temp dirs (curl reports success, file vanishes) — download on the Linux build host instead.
- Shell `$(cmd)` interpolation inside ssh one-liners can trip the terminal hardline parser — use `awk` two-pass instead of mid-command variable capture.

See `references/psp-plugin-toolchain-triage.md` for the full TempAR case study (evidence, fixes, tags).