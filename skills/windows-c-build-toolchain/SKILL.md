---
name: windows-c-build-toolchain
description: "Build C/C++ on Windows with MSYS2 MinGW GCC."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [windows, c-cpp, msys2, mingw]
    category: devops
tags: [windows, gcc, mingw, msys2, build, cmake]
---


# Windows C Build Toolchain (MSYS2 MinGW GCC)

## When to Use

Building C/C++ projects on Windows when Visual Studio Build Tools are not installed or unavailable.

## Setup

```bash
# Install MSYS2 via winget
winget install MSYS2.MSYS2

# Fix PGP keyring (run once from MSYS2 bash)
C:/msys64/usr/bin/bash.exe -lc "
rm -rf /etc/pacman.d/gnupg
pacman-key --init
pacman-key --populate msys2
"

# Install GCC
C:/msys64/usr/bin/bash.exe -lc "pacman -S --noconfirm mingw-w64-x86_64-gcc"
```

## Build

**Always invoke gcc through MSYS2 bash, not directly from Git Bash.** Windows Defender silently kills cc1.exe when invoked from Git Bash (the terminal tool). The MSYS2 shell does not have this issue.

```bash
# WRONG — fails silently (exit 1, no output):
C:/msys64/mingw64/bin/gcc.exe -c file.c

# CORRECT — works:
C:/msys64/usr/bin/bash.exe -lc "
export PATH=/mingw64/bin:\$PATH
cd /c/Users/admin/projects/myproject
gcc -shared -o library.dll source.c -lkernel32 -ladvapi32
"
```

## Common Fixes

### Implicit declaration of function

GCC requires forward declarations. If a function is used in one `.c` file but defined in another, add `extern` declaration in a shared header:

```c
// In shared_header.h
extern double my_function(HANDLE handle);
```

### Linking Windows APIs

```bash
gcc -shared -o library.dll source.c \
  -lkernel32 -ladvapi32 -lshell32 -lole32 -loleaut32 -lwbemuuid
```

## Pitfalls

- **Windows Defender kills cc1.exe from Git Bash**: The MSYS2 gcc toolchain works fine from MSYS2 bash but fails silently from Git Bash. Always wrap gcc calls in `C:/msys64/usr/bin/bash.exe -lc "..."`.
- **MSYS2 PGP keyring corruption**: Fresh MSYS2 install may have invalid package signatures. Fix by removing and reinitializing the keyring.
- **Exit code 1 with no output**: If gcc exits 1 with no error messages, it is likely being killed by antivirus. Check Windows Defender protection history.
- **Missing forward declarations**: GCC is stricter than MSVC about implicit function declarations. Every function used in a translation unit must be declared before use.

## Reference

See `references/w64devkit-lightweight-mingw.md` for the alternative lightweight MinGW distribution (~60MB, no installer).