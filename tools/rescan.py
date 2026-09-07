#!/usr/bin/env python3
"""
Re-runs the fail-closed scrub gate (the same DENYLIST_RES used by publish.py)
against everything currently shipped in this repo: skills/, docs/, README.md,
pack_manifest.json.

This exists because the repo IS the generated pack — there's no private
source tree to re-publish from in CI. If a skill is hand-edited after
publish.py generated it (a typo fix, a manual doc tweak), this catches any
denylisted term that slipped in without a full republish.

Exit 0 = clean. Exit 1 = at least one hit; CI should fail the build.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish import run_scrub  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# The repo legitimately carries the owner's GitHub handle in the sponsor
# link, repo README, and manifest — same exemption publish.py applies at
# its own final rescan step.
OWNER_HANDLE_EXEMPT = ("abduznik",)


def main() -> int:
    hits = []

    for p in sorted((REPO_ROOT / "skills").rglob("*")):
        if p.is_file():
            hits += run_scrub(p.read_text(encoding="utf-8", errors="replace"), str(p.relative_to(REPO_ROOT)))

    docs_dir = REPO_ROOT / "docs"
    if docs_dir.is_dir():
        for p in sorted(docs_dir.rglob("*.html")):
            hits += run_scrub(
                p.read_text(encoding="utf-8", errors="replace"),
                str(p.relative_to(REPO_ROOT)),
                exclusions=OWNER_HANDLE_EXEMPT,
            )

    for name in ("README.md", "pack_manifest.json"):
        p = REPO_ROOT / name
        if p.is_file():
            hits += run_scrub(p.read_text(encoding="utf-8", errors="replace"), name, exclusions=OWNER_HANDLE_EXEMPT)

    if hits:
        print("SCRUB FAILURE — denylisted terms found in shipped content:")
        print("\n".join(hits))
        return 1

    print("OK — rescanned skills/, docs/, README.md, pack_manifest.json, no hits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
