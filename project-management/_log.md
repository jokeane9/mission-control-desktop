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

---

## 2026-07-14 — Top-level views epic → v1.3.0

**What happened:** Added three new top-level sidebar views (peers of the
overview) in four branch→PR→green-CI→merge cycles, then released v1.3.0.

- **Skills** (#24) — searchable catalog of Claude Code skills. New stdlib
  sibling `views.py` (collect_* pure-data + *_html renderers); generate.py
  gained `%%TOPSIDE%%`/`%%TOPVIEWS%%` template slots for top-level views.
- **Work Log** (#25) — own-commits-only across all dashboard repos
  (per-repo + global user.email, `--fixed-strings`), commits/day SVG chart +
  day-grouped list, Today/Week/Month/3-months filter, Copy-as-standup,
  overview "Today · N commits across M repos" line.
- **Roadmap** (#26) — Now/Next of every project's ROADMAP.md (3 conventional
  locations, top-items fallback), linked to the file.
- **Token chart** (#27) — tokens/day from ~/.claude session transcripts as a
  second chart sharing the time axis (never dual-axis); per-file (size,mtime)
  cache in DATA/token_cache.json; series excludes cache reads (~50× larger).

**Gotchas worth remembering:**
- `git log --author` is POSIX basic regex: `re.escape` turns the `+` in GitHub
  noreply emails into a repetition operator that silently matches nothing —
  use `--fixed-strings`.
- `git log --since` prunes traversal at the first too-old commit, so tests
  must create commits in chronological order.
- The autopopulate tests were leaking the dev github_cache.json into their
  sandboxed renders (green in CI, red locally) — they now override
  `generate.DATA` too.

**Released:** v1.3.0 (tag → CI builds both platforms → Release → tap bump).

---

## 2026-07-14 (session 2) — PM scratchpad tab + PRODUCT.md → v1.4.0

**What happened:** Added a fifth top-level view and the first product doc, on
branch `pm-admin-and-docs` → PR #28 → v1.4.0.

- **PM tab** — a local admin scratchpad (view id `pm`). One free-text file
  (`pm_notes.md` in the data dir, gitignored) rendered into a textarea and
  autosaved via a new `save_notes` bridge method (debounced on input; flushed
  on visibilitychange/beforeunload so the 15-min meta-refresh can't drop
  unsaved text). Bridge-gated like the config editor: read-only in a plain
  browser, editable in the packaged app. `views.load_notes`/`save_notes` pure +
  tested.
- **PRODUCT.md** — first canonical *product* doc (distinct from the
  project-management/ process docs): one-liner, who it's for, principles,
  non-goals, success north star, and open product questions written Q&A-style —
  incl. the deliberate "no sync / no login, it's a different product" stance
  that came out of this session's questions.

**Decision captured (not built):** cross-device sync / accounts collide with
the local-first, no-server, no-accounts principle. Parked as a conscious pivot
question in PRODUCT.md, not a feature.

---

## 2026-07-14 (session 3) — Views epic → v1.3.0–v1.6.0, QA, cask, full UX pass

**Big day. Six releases (v1.3.0 → v1.6.0) plus a Gatekeeper cask fix and a
5-agent UX audit.**

**What shipped**
- **v1.3.0** — three top-level views: Skills (searchable skill catalog),
  Work Log (commits/day + Claude-tokens/day charts + day-grouped list +
  "Copy as standup" + overview Today line), Roadmap (each repo's Now/Next).
  New stdlib sibling `views.py`. (#24 #25 #26 #27)
- **v1.4.0** — PM scratchpad tab (autosaves via the bridge) + `PRODUCT.md`
  (first canonical product doc). (#28)
- **v1.4.1** — `app.py` logs regeneration errors instead of swallowing them
  (`_log_exc` → DATA/error.log). Motivated by the QA scare below. (#30)
- **v1.5.0** — auto-organized, collapsible **project groups** in the sidebar;
  `resolve.auto_groups()` (name-prefix → owner → non-dominant parent-dir);
  manual `Group` editor field overrides; provenance-marked. (#32)
- **v1.6.0** — groups become **folders** (click = filter the grid, chevron =
  collapse, breadcrumb back); **drag-and-drop** reorder groups + move projects
  (localStorage); attention **rollup dots**; attention-first + tier **triage
  sort**; blank thesis → last commit; "Ungrouped" → "Other"; **keyboard a11y**
  (focus ring, Enter/Space on div-nav, `--faint` → WCAG-AA `#868f9c`,
  reduced-motion). Built from the UX audit. (#33)
- **Cask caveats** — the Homebrew cask now prints the macOS "Open Anyway" steps
  at `brew install` (repo copy #31 + live in the tap). Real fix is still
  notarization (#9).

**The QA scare (important lesson).** A "critical bug — packaged app shows no
new views" turned out to be a **false alarm**: a stale v1.2.2 instance (process
named `org.python.python`) never got killed, the window was on a second
monitor, and a bundle-id mismatch (`com.keane.mission-control` vs `…app`) hid the
fresh instance from screenshots — compounded by a contaminated shared data dir.
The shipped app was fine all along (verified by running the real binary; then
re-verified v1.5.0/v1.6.0 in the packaged app). Takeaways: kill by
`org.python.python`, the window can be on `LG 32 FHD (1)`, grant
`com.keane.mission-control`, and the silent `except: pass` (now fixed in v1.4.1)
is what made a 5-second diagnosis take an hour. Also: unsigned app + macOS 26
quarantine caused "vanishing" during rapid `brew reinstall` — de-quarantine with
`xattr -cr`; the signature is valid ad-hoc (recoverable "Open Anyway", not
"damaged").

**UX audit** — see `UX-AUDIT.md` (findings + recommendations) and `UX-FLOWS.md`
(the interaction model). 5 design agents: grouping spec + home/IA + views +
detail/editor/GitHub + global/a11y. v1.6.0 shipped the seam fixes; the ranked
backlog (PM autosave race, standup-copies-wrong-day, attention hero line, editor
onboarding, provenance-made-usable, GitHub error consistency, design-system
tightening) is the v1.6.1+ queue.

**Also:** in `jokeane9/killdate.dev`, refreshed + relaunched the Mission Control
blog post and merged the duplicate-post-number renumber; both deployed.

**Owner-gated backlog unchanged:** SignPath enrollment (#7 → winget #8), Apple
notarization (#9), Tahoe icon (#10), posting the launch.
