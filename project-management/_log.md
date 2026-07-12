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
   `release.yml`. First real "Next" roadmap item.
2. Stand up `ci.yml` (build both platforms + lint on PRs) + branch protection.
3. Seed GitHub Issues/Milestone from `ROADMAP.md` if we want the GitHub PM layer.
4. Rotate `TAP_GITHUB_TOKEN` — it was pasted in chat during setup.
