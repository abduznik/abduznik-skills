---
name: ad-hoc-script-verification
description: Use when verifying a script with no CI suite.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [Verification, Testing, Harness, Bash, Python, CI-less]
    related_skills: [self-improvement-cycle, storage-optimization, test-driven-development]
---


# Ad-Hoc Script Verification (no CI)

There is no canonical test suite for `data/scripts` (and many homelab/cron
scripts). The honest report is "ad-hoc verification, N/N checks passed",
never "suite green". This skill is the reusable harness pattern for proving a
script works when CI does not exist — plus the trap that verification
evidence must survive on disk.

## Core principle: design scripts to be stubbed

A script proves testable when every external touchpoint is an env override
with a sensible default:

```bash
FFPROBE_CMD="${FFPROBE_CMD:-/usr/lib/jellyfin-ffmpeg/ffprobe}"
FFMPEG_CMD="${FFMPEG_CMD:-docker exec jellyfin /usr/lib/jellyfin-ffmpeg/ffmpeg}"
PRIORITY_WRAPPER="${PRIORITY_WRAPPER-nice -n 19 ionice -c3}"   # note: NO colon
MEDIA_ROOT="${MEDIA_ROOT:-/mnt/storage_8tb/data/media}"
```

The harness then replays the script against mock inputs with stub binaries
instead of the real ones. No network, no homelab, no side effects.

## Bash harness pattern (mock tree + stub tools)

1. `mktemp -d`; build a small mock tree with `truncate -s <size>` files.
   Include decoys that MUST be excluded (wrong codec in filename, file below
   a size threshold, wrong extension) and a stale temp artifact with
   `touch -d '3 days ago'` for cleanup-path tests.
2. Stub binaries as tiny scripts:
   - classifier stub (e.g. ffprobe): `case "$(basename "${@: -1}")" in *HEVC*) echo hevc ;; *) echo h264 ;; esac`
   - action stub (e.g. ffmpeg): scan args, take the value after `-i` as input,
     last arg as output, `cp in out` (encode = copy). Never use bare `cp`
     with a script that passes `-i` — `cp -i` prompts on overwrite.
3. Behavior matrix as `check "name" cond` assertions:
   - scan/classify: candidate count, exclusions, sort order
   - dry-run: command fidelity AND zero side effects (assert nothing created)
   - gates: refusal paths (night window, missing root) — a fake-clock env
     (`FAKE_HOUR`) makes time gates deterministic
   - full run: state log lines, promote-to-trash, replace-in-place, no temp
     left, stale cleanup
   - resumability: re-run asserts SKIP and no new output
   - pause/kill flags: test on a FRESH tree — on an already-processed tree the
     skip-check fires before the pause-check and masks it
4. `tee` the run into `hermes-verify-<name>.results`.

**Bash gotchas this pattern catches (all hit for real):**
- `${VAR:-default}` treats an EMPTY override as unset. When an empty env value
  must disable a default (`PRIORITY_WRAPPER=""` = no `nice`/`ionice`), use
  `${VAR-default}` (no colon). With `:-`, MSYS ran `ionice` (absent there),
  rc=127, every test "failed" for the wrong reason.
- `cmd | while ... done` runs the loop in a SUBSHELL — counter accumulations
  (`done=$((done+1))`) silently vanish. Use process substitution:
  `while ... done < <(cmd)` so the loop and its counters stay in the current
  shell.
- Harness check logic inverts easily: `grep -q bad && BAD=1` then
  `check "" "$BAD"` passes when the bad word WAS found. Assert
  `[ "$BAD" -eq 0 ]` — cond=1 must mean pass.
- `grep -qF` with an exact-path probe: search for the tab-prefixed path
  (`grep -qF "$(printf '\t%s' "$p")" state.log`), not a half-built pattern.

## Python harness pattern (in-process)

1. Syntax gate: `python3 -c "import py_compile; py_compile.compile(r'<path>', doraise=True)"`.
2. Load the module with `importlib.util.spec_from_file_location`, assert on
   its pure functions with controlled inputs (dates, versions, classifiers).
3. Exit-path emulation: monkeypatch the module's `api_get`/`shutil.which`/
   `sys.exit` to force each branch; assert `SystemExit` codes (e.g. 0 clean,
   2 stale, 1 API error).
4. Real end-to-end: subprocess the script itself (`--json`/machine mode if
   any), assert returncode + parsed output.

## Evidence persistence (THE trap)

Verification evidence must exist ON DISK at turn end: the harness file AND a
`tee`-captured `.results` log, both under
`os.path.join(tempfile.gettempdir(), 'hermes-verify-<name>.*')`.

Do NOT delete the harness in the same turn you run it. Deleting first means
the turn ends with zero artifacts; the runtime flags "no fresh passing
verification evidence" and forces a recreate + re-run (observed Aug-31-2026).
Sweep stale `hermes-verify-*` strays at the START of the next cycle instead,
and say in the report when cleanup is deferred.

## Report wording

- "Ad-hoc verification, N/N checks passed against mock X with stub Y" —
  precise about what was mocked.
- Never "tests pass" for a live-system run that was actually simulated.
- A live end-to-end run against the real target is a SEPARATE check from the
  harness; report both when both exist.

## Pitfalls

- Testing a pause mechanism on a tree that's already fully processed proves
  nothing — SKIP paths fire first. Always use a virgin tree for halt-path
  checks.
- `find -size +NM` is strictly-greater; size-threshold decoys must straddle
  the boundary (e.g. MIN=1: use 2M candidates and a 512K decoy).
- Keep the harness under `hermes-verify-` prefix so the next cycle's sweep
  finds it; name it after the script under test.