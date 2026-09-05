# Hermes Skill Pack

A curated collection of reusable skills for [Hermes Agent](https://github.com/NousResearch/hermes-agent),
battle-tested in a production deployment and scrubbed clean of any private
infrastructure, personal data, or session traces.

Every skill in this pack passed a fail-closed privacy gate before publishing:
a single hit on hosts, paths, identities, or personal markers aborts the build.
`tools/publish.py` is the exact gate used — the pack is a generated artifact,
not a hand-maintained copy.

## Skills

| Category | Skill | Description |
|---|---|---|
| devops | `ad-hoc-script-verification` | Use when verifying a script with no CI suite. |
| devops | `docker-container-update-check` | Use when checking Docker containers for newer images. |
| devops | `ephemeral-file-sharing` | Expiring public web links for files, CLI-only (gofile.io). |
| devops | `google-oauth-file-poll` | Use when Google API OAuth needs a headless file-poll flow. |
| devops | `reverse-proxy-websocket-debugging` | Use when WebSockets die behind a reverse proxy (close 1006). |
| devops | `windows-crash-forensics` | PC crash/freeze forensics via event logs, blame attribution. |
| github | `github-code-review` | Review PRs: diffs, inline comments via gh or REST. |
| github | `maintained-fork-publishing` | Publish/maintain OSS forks; contribute upstream via PRs. |
| hardware | `usb-device-enumeration` | Use when a USB device is invisible on Windows. |
| hermes | `debugging-hermes-tui-commands` | Debug Hermes TUI slash commands: Python, gateway, Ink UI. |
| hermes | `hermes-agent-skill-authoring` | Author in-repo SKILL.md: frontmatter, validator, structure. |
| hermes | `hermes-gateway-slash-command` | Add a gateway-available slash command with message tracking and batch deletion capabilities. Covers  |
| media | `jellyseerr-watch-suggestions` | Use when suggesting watch picks filtered by your library. |
| media | `yt-dlp-anti-bot` | When yt-dlp hits 403s, harden with impersonation + backoff. |
| software-development | `circuit-design` | Design electrical circuits programmatically — SKiDL netlist generation, custom SVG schematic rendere |
| software-development | `embedded-porting-patterns` | Porting C/C++ CMake+SDL2 applications to new embedded/handheld platforms (PSP, Vita, 3DS, etc.) by f |
| software-development | `flutter-android-build` | Build Flutter APKs and modify Glance widgets. |
| software-development | `flutter-content-rendering` | Show HTML/links/PDFs in Flutter — viewers, clickable URLs. |
| software-development | `pdf-flatten` | Use when flattening PDFs to page images or raster PDFs. |
| software-development | `plan` | Write a markdown plan to .hermes/plans/; no execution. |
| software-development | `psp-prx-plugin-maintenance` | Use when building/debugging PSP prx kernel plugins. |
| software-development | `python-debugpy` | Debug Python: pdb REPL + debugpy remote (DAP). |
| software-development | `python-webapp-patterns` | Build Python web apps with FastAPI or Flask — static file serving, search-index frontends, PDF/binar |
| software-development | `simplify-code` | Parallel 4-agent cleanup of recent code changes. |
| software-development | `spike` | Throwaway experiments to validate an idea before build. |
| software-development | `subagent-driven-development` | Execute plans via delegate_task subagents (2-stage review). |
| software-development | `test-driven-development` | TDD: enforce RED-GREEN-REFACTOR, tests before code. |
| software-development | `writing-plans` | Write implementation plans: bite-sized tasks, paths, code. |

## Install

Hermes loads skills from its skills directory (typically `~/.hermes/skills/` on
Linux/macOS, or `<hermes-data>/skills/` in portable/profile setups). A skill is
just a folder containing `SKILL.md`.

1. Clone this repo — or fork it and clone your own copy:
   `git clone <this-repo-url> hermes-skill-pack`
2. Copy the skills you want:
   `cp -r skills/* ~/.hermes/skills/`
3. Restart your Hermes session — the skills appear in the toolbox.

You can also grab a single folder straight from the GitHub UI ("Download folder").

## Adding or updating a skill

1. Edit the source skill locally, then run:
   `python3 tools/publish.py --source <your-skills-dir> --dest . --manifest pack_manifest.json --force`
2. The gate re-scans everything; the table below updates itself.
3. (Optional) add support files per skill in a later revision — v1 ships
   SKILL.md only, by design, to keep the privacy surface minimal.

## License

MIT — see [LICENSE](LICENSE).

## Attributions

Several skills are adaptations of existing open work and keep their attribution
in the `author` frontmatter field:

- `plan`, `spike`, `subagent-driven-development`, `systematic-debugging`,
  `test-driven-development`, `writing-plans` — adapted from
  [obra/superpowers](https://github.com/obra/superpowers) (MIT)
- `simplify-code` — inspired by Claude Code `/simplify`
- `spike` — adapted from gsd-build/get-shit-done
- `ephemeral-file-sharing` — CLI wrapper around gofile.io public API

All other skills were authored by Hermes Agent from operational experience.
