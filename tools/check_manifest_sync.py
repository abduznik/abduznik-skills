#!/usr/bin/env python3
"""
Validates that pack_manifest.json agrees with what's actually on disk under
skills/: every manifest entry has a matching skills/<name>/SKILL.md, every
skills/<name>/ directory has a matching manifest entry, and each SKILL.md's
frontmatter `name` matches its folder name.

Catches the drift case where a skill folder was added/removed/renamed by
hand without regenerating pack_manifest.json via tools/publish.py.

Exit 0 = in sync. Exit 1 = mismatch found.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish import extract_frontmatter, parse_fm_lines  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    manifest_path = REPO_ROOT / "pack_manifest.json"
    skills_dir = REPO_ROOT / "skills"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_names = {s["name"] for s in manifest["skills"]}

    disk_names = {p.name for p in skills_dir.iterdir() if p.is_dir()}

    errors = []

    missing_on_disk = manifest_names - disk_names
    for name in sorted(missing_on_disk):
        errors.append(f"manifest lists {name!r} but skills/{name}/ does not exist")

    missing_in_manifest = disk_names - manifest_names
    for name in sorted(missing_in_manifest):
        errors.append(f"skills/{name}/ exists but is not listed in pack_manifest.json")

    for name in sorted(manifest_names & disk_names):
        skill_md = skills_dir / name / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"skills/{name}/ has no SKILL.md")
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        fm = extract_frontmatter(text)
        if fm is None:
            errors.append(f"skills/{name}/SKILL.md has invalid/missing frontmatter")
            continue
        fm_block, _, _ = fm
        entries = parse_fm_lines(fm_block)
        fm_name = next((e["clean_val"] for e in entries if e["key"] == "name"), None)
        if fm_name != name:
            errors.append(f"skills/{name}/SKILL.md frontmatter name is {fm_name!r}, expected {name!r}")

    if errors:
        print("MANIFEST SYNC FAILURE:")
        print("\n".join(f"  - {e}" for e in errors))
        return 1

    print(f"OK — {len(manifest_names)} skills in sync between pack_manifest.json and skills/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
