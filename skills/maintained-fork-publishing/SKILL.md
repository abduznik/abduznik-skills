---
name: maintained-fork-publishing
description: Publish/maintain OSS forks; contribute upstream via PRs.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [fork, github, gitea, upstream-pr, license, attribution, git]
    related_skills: [github-pr-workflow, git-commit-identity, github-repo-management]
---




# Maintained Fork Publishing

Turn a private fork of an abandoned/slow upstream project into a public,
properly-attributed maintained fork, and chip improvements back upstream as
clean topical PRs. Use when the user asks "how should I publish my fork",
"is it ethical to put this fork on GitHub", or wants to contribute additions
upstream.

## 0. Fact-check BEFORE forking

The user's premise may be wrong — verify before advising:

- **Releases vs branch activity:** tagged releases can be dead for years while
  `main` gets commits weekly. Check all three:
  - `git log origin/main --format='%ci %s' -5` (in the clone)
  - `curl -s https://api.github.com/repos/<owner>/<repo> | jq '{pushed_at, archived}'`
  - `curl -s .../releases?per_page=5` — compare release dates vs pushed_at
- **Did someone already build this feature?** Scan forks before duplicating:
  `curl -s ".../forks?sort=newest&per_page=30"` → inspect `pushed_at`; active
  forks: list commits (`/commits?per_page=8`), scan the tree
  (`/git/trees/<branch>?recursive=1`) and deps (raw pubspec.yaml/package.json)
  for the feature. Pure-sync forks have `pushed_at == upstream pushed_at`.
  Also check open upstream PRs (`/pulls?state=open`).

## 1. The repo MUST be a true fork (gotcha #1)

`gh repo create <name> --public` + push creates a repo that is NOT in the
fork network — `gh pr create --repo <upstream>` then fails with
"Head sha can't be blank / No commits between <upstream>:main and <you>:<branch>".

Fix: recreate as a real fork (`gh repo fork <up>/<repo> --fork-name <name> --clone=false`)
— also shows the GitHub "forked from" badge. If a wrong-name repo already
exists and deletion is blocked (gh token lacks `delete_repo` scope), fork
under `<name>-fork` and have the user delete the old repo in the GitHub UI
(Settings → Danger Zone).

## 2. Push auth: `gh auth setup-git`

`gh` auth does NOT make `git push https://...` work. Run `gh auth setup-git`
once — git's credential helper then feeds the gh token. Diagnostic: `gh api`
works while `git push` reports "access rights / repository exists".
Check the remote exists first too (`git remote add github <url>` may have been
skipped inside a blocked command — verify `git remote -v`).

## 3. Fork hygiene before going public

- **README fork banner** at top: fork-of + upstream link, upstream release
  status, "Changes vs upstream" list, keep upstream LICENSE intact (MIT etc.),
  drop upstream's release badges (they point at the official releases).
- **Identity rewrite before the first public push** (safe — no shared refs):
  ```bash
  export GIT_AUTHOR_NAME=<user> GIT_AUTHOR_EMAIL=<noreply> \
         GIT_COMMITTER_NAME=<user> GIT_COMMITTER_EMAIL=<noreply>
  git rebase origin/main --exec 'git commit --amend --reset-author --no-edit'
  ```
  Rewrites SHAs — any mirror with the old SHAs needs a force-push (see §5).
- Commit the README banner with the identity env vars set.

## 4. Topical PR branches (cherry-pick, don't dump your whole branch)

```bash
git checkout -b pr/widget-refresh origin/main     # UPSTREAM base, not your branch
git cherry-pick <sha1> <sha2>
```
- Skip version-bump-only commits; resolve version-line conflicts keeping the
  UPSTREAM version (splice conflict markers with Python, `git add`,
  `git cherry-pick --continue`).
- Commits from a long-lived branch often bundle sibling-feature hunks
  (context lines) → cherry-picks conflict; splice OUT the unrelated hunks.
- **Compile-check every PR branch locally** — partial feature sets can
  reference helpers that only existed in sibling commits (real case:
  `substringAfter` doesn't exist in Dart at all; fix = `.split("x").last`).
- `flutter analyze`/`pub get` rewrites `pubspec.lock`, the dirty file carries
  over on `git checkout -b` and aborts the next cherry-pick — fix:
  `git checkout -- pubspec.lock`.
- `grep -c` with 0 matches exits 1 and short-circuits `&&` chains.

## 5. Updating an internal mirror (Gitea) after a rewrite — snapshot first

```bash
git fetch gitea
git branch legacy-main gitea/main      # snapshot old SHAs
git branch legacy-feat gitea/feat/...  # snapshot old feature branch
git push gitea legacy-main:legacy-main && git push gitea legacy-feat:legacy-feat
git push gitea main --force            # confirm with user; tags untouched
```
`git reset --hard` and force-push trigger approval gates. If a prompt times
out the command is BLOCKED — report and wait, never rephrase/retry.

## Pitfalls

- Abandonware claims: distinguish "releases dead" from "code dead" — they
  differ and the fork README should state the truth.
- Licensing: MIT forks need the original notice retained; attribution in the
  README is the community norm; trademark-wise say "community fork, not
  affiliated with the official project".
- Keep upstream as a remote (`origin`) + your public fork (`github`) + your
  private mirror (`gitea`) with distinct names — never push to upstream directly.