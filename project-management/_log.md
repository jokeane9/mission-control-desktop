# Session log

One entry per session, most recent at the bottom. Read the last ~80 lines at
session start — this is the primary context transfer between sessions. If work
is mid-flight at session end, add a **RESUME HERE** block with numbered steps.

---

## 2026-07-12 — Ship as cross-platform apps + set up PM

**What happened:** Took Mission Control from a personal macOS-only script to a
public, open-source, donation-supported desktop app for **macOS and Windows**.

- Refactored `generate.py`/`app.py`/`menubar.py` to be cross-platform: per-user
  data dir when packaged, first-run seeding from `baseline.sample.json`, Ctrl
  labels on Windows, configurable viz tool paths, background regen thread.
- Added packaging: PyInstaller spec + hardened-runtime entitlements, mac
  build/sign/notarize/staple script, Windows Inno Setup installer (WebView2
  bootstrap) + zip, `icon.ico` generator.
- Set up CI (`release.yml`): `v*` tag → build both platforms → publish GitHub
  Release → auto-bump the Homebrew cask in `jokeane9/homebrew-tap`.
- Created the public repo `jokeane9/mission-control-desktop` and the tap. Cut
  v1.0.0 → v1.0.2 and proved the tap auto-bump end-to-end.
- Docs: `CLAUDE.md`, `DISTRIBUTION.md` (signing/notarization + the $0 launch
  path), and this `project-management/` system.

**Decisions** (see `STACK.md`): one codebase / two build targets (never split);
onedir + installer over onefile; GitHub-native PM; tap bump via Contents REST
API (not git push); launch unsigned, add signing later.

**Gotchas hit** (so future sessions skip the pain):
- The tap `bump-tap` job must use the **Contents REST API** with the fine-grained
  PAT as a bearer token. `git push` with the token in the URL → HTTP 401.
- `TAP_GITHUB_TOKEN` must be set via the **interactive** `gh secret set` prompt;
  a mis-pasted one-liner silently stored the placeholder text → 401.
- Artifact names strip the leading `v` from the tag; the cask URL relies on it.

**RESUME HERE (next session options):**
1. Windows signing via SignPath (free) — enroll, add the signing step to
   `release.yml`. First real "Next" roadmap item (issue #7).
2. Rotate `TAP_GITHUB_TOKEN` — it was pasted in chat during setup.

---

## 2026-07-12 (later) — CI/CD hardening + GitHub PM layer

**What happened:** Built out the rest of the PM/CI scaffolding.

- `ci.yml` guardrail: fast `check` (ruff real-errors + compile + render smoke) on
  push/PR, full both-platform packaging `build` on PRs.
- Branch protection on `main`: requires the `check` status check;
  `enforce_admins=false` so the owner still pushes directly, contributors' PRs
  must be green.
- `CHANGELOG.md` (seeded 1.0.0–1.0.2), `dependabot.yml` (actions + pip), issue
  forms (bug/feature) + PR template.
- Labels `platform:mac|windows`, `packaging`, `signing`, `ci`; milestone
  "v1.1 — signing & distribution"; roadmap seeded into issues #7–#13.

**Owner-only follow-ups (I can't do these):**
- GitHub **Project board** — CLI token lacks the `project` scope. Run
  `gh auth refresh -s project,read:project` then
  `gh project create --owner jokeane9 --title "Mission Control"` (or make it in
  the web UI). Add issues #7–#13 to it.
- Rotate `TAP_GITHUB_TOKEN` (exposed in chat during setup).
- SignPath enrollment (issue #7).

---

## 2026-07-12 (session 3) — Auto-populate epic + merge sweep

**What happened:** Built auto-populate P1→P3.2 (each its own branch/PR, verified,
merged) and cleared a backlog of stale Dependabot PRs.

- Config editor (#13→v1.1.0). Auto-populate: P1 discovery+resolver (#16),
  provenance badge (#17), P2 auto-maps (#18), P3.1 GitHub auth/keychain (#19),
  P3.2 GitHub sync (#20). Design docs: schema / resolver / P1 & P3 build plans.
- Architecture that held throughout: the **sync/cache boundary** — network + the
  GitHub token live only in github_sync.py / github_auth.py (app-side);
  generate.py + resolve.py stay stdlib + offline, reading a cache file.
- **Merge sweep:** 5 Dependabot PRs (#2–#6) had accumulated unnoticed +
  P3.2 (#20). All green → merged all 6. main clean, 0 open PRs, stale branches
  deleted.

**Deferred by decision:** P4 (LLM extraction). See ROADMAP Later.

**RESUME HERE (next session):**
1. **Real-token GitHub sync check** — connect a PAT in the app, "sync repos",
   confirm it populates (the one unverified P3.2 path).
2. **Cut v1.2.0** — main is well ahead of the v1.1.0 tag. First release to
   exercise the Dependabot release.yml action bumps — watch that run.
3. P3.3 (sync UI polish), then Windows signing (#7) / winget (#8) when enrolled.

**Still open owner-only:** Project board (needs `project` scope), rotate
`TAP_GITHUB_TOKEN`, SignPath enrollment.
