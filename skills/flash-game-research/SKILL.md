---
name: flash-game-research
description: Run, analyze, or automate Flash SWF games via Ruffle.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [flash, swf, ruffle]
    category: software-development
tags: flash, swf, ruffle, emulation, automation
---


Use when running, analyzing, or automating Flash (.swf) games via Ruffle.

## Procedure

### 1. Get the SWF
- Archive.org: `https://archive.org/metadata/<slug>` lists files. Find the `.swf` filename from the metadata JSON, then download via `https://archive.org/download/<slug>/<filename>`.
- Verify with `file <swf>` — expect `Macromedia Flash data (compressed), version N`.
- CWS = zlib-compressed. The first byte after the 8-byte header is the start of zlib data.

### 2. Ruffle Setup
- Download: GitHub releases API `https://api.github.com/repos/ruffle-rs/ruffle/releases?per_page=3`, look for `windows-x86_64` zip.
- **Graphics backend**: Intel HD Graphics (e.g. HD 520) segfaults on Vulkan. Force `--graphics gl`. DX12 also works on some Intel iGPUs.
- Launch: `./ruffle/ruffle.exe --graphics gl --width 800 --height 600 game.swf`
- SWF v9 games (AS2) load fine. AVM1 stack underflow warnings are cosmetic. Ad URL errors (InvalidDomain) are harmless.

### 3. SWF Introspection (finding interactables)

**Quick method — string extraction:** Decompress the SWF and scan for readable ASCII strings. Finds button names, instance names, screen labels, ActionScript constants without a full parser.

```python
import zlib
with open('game.swf', 'rb') as f:
    f.read(8)  # skip CWS header
    compressed = f.read()
decompressed = zlib.decompress(compressed, 15)  # wbits=15 for CWS
```

Scan for runs of printable ASCII >4 chars. Filter for game-relevant keywords: `btn`, `button`, `click`, `order`, `cook`, `cut`, `serve`, `station`, `screen`, `menu`, `play`, `start`, `score`, `drag`, `drop`.

**Tag-level parsing:** SWF tags include:
- DoAction (12): ActionScript 2 bytecode — extract string constants
- FrameLabel (43): named frames = game states
- PlaceObject2 (22): placed MovieClips with instance names
- SymbolClass (76): maps character IDs to class names (AS3 games)
- DefineSprite (39): animated sequences, frame count reveals screen complexity

**Full decompilation:** JPEXS Free Flash Decompiler (requires Java) gives complete ActionScript source.

### 4. Game Control
- Flash games use `onPress`/`onRelease` handlers on named MovieClips.
- No programmatic API from Ruffle desktop — control via mouse/keyboard simulation (pyautogui, mss).
- Station detection: frame labels or screen region fingerprinting (color histograms per station area).
- Coordinate mapping: Ruffle window position from pyautogui, game coordinates relative to window.

## Pitfalls

- **Ruffle Vulkan segfault on Intel iGPUs**: always pass `--graphics gl` on machines without dedicated GPU.
- **SWF decompression wbits**: `zlib.decompress(data)` fails on CWS SWFs. Use `zlib.decompress(data, 15)` — 15 = max window bits + enable zlib header detection.
- **python3 vs python**: On this Windows machine, `python3` resolves to a broken Windows Store alias. Use `python` (3.11.10 in the venv) and `python -m pip` for installs.
- **AS2 vs AS3**: SWF version ≤8 is AS2 (DoAction tags, no SymbolClass). Version ≥9 can be either. AS3 games use class-based structure via SymbolClass tag 76. AS2 games use `_root.onPress` style with all logic in DoAction bytecode.
- **Frame label extraction**: FrameLabel tags contain null-terminated strings. Parse with `tag_data.split(b'\x00')[0].decode('latin-1')`.
- **PlaceObject2 instance names**: variable-length matrix encoding makes naive offset parsing unreliable. Use string extraction method instead for finding instance names.