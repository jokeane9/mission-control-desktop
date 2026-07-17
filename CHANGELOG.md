# Changelog

All notable changes to Orrery are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/) — one version number for both
platforms.

## [Unreleased]

## [2.3.0] — 2026-07-17
### Added
- **Session footprints.** Each session row now shows *what it did*, not just a
  hex id: the files it edited, the dirs it worked in, the branches it touched,
  and the PRs it opened (clickable). `04dc2441` becomes "edited views.py,
  cli.py, generate.py · mission-control-desktop/ tests/ · PR #36 #37 #43" — so
  eight sessions under one repo stop being eight blanks.
  - All of it is action-metadata (file paths, branch names, PR URLs, tool
    names). **Still never prompt or response content** — the privacy test now
    also plants a secret in a Bash command and asserts it can't leak.
  - Free: it comes out of the transcript pass the Work Log already does. Cache
    v3 → v4; a read-only session (no edits) falls back to showing where it ran.
  - `orrery sessions` shows the footprint too, and `--json` carries the fields.


## [2.2.1] — 2026-07-17
### Fixed
- **"Needs attention" no longer cries wolf** ([#44](https://github.com/jokeane9/orrery/issues/44)).
  The unmerged-branch count included every *remote* branch, so a repo you cloned
  to read was flagged for hundreds of open upstream PRs you'll never merge
  (langflow: 1884, dspy: 366). On a real 29-project workspace that lit up 19
  projects and reported 2374 "unmerged branches". It now counts only **local**
  branches — your own work in progress — which drops the same workspace to 14
  genuinely-need-you projects and 12 unmerged. The other signals (uncommitted,
  unpushed, stashes) are unchanged; `collect()` now has tests.


## [2.2.0] — 2026-07-16

Two features, one release: they landed in a single commit, so they ship as one
version rather than pretending to be two. Both are the same bet — Orrery's
differentiator isn't the git dashboard, it's the state your agents leave behind.

### Added
- **Sessions view** — what your agents are doing, and what they left behind.
  Every Claude Code session in your repos: live or idle, which branch, how long,
  how many messages and tokens. Newest first.
  - **It joins Worktrees.** A session that ended without cleaning up its
    worktree is flagged *left a worktree* — the folder is still on disk. An
    abandoned worktree and the interrupted session that stranded it are one
    story; this is the other end of it.
  - **Metadata only — never prompts, never responses, never titles.** The
    transcripts are the most sensitive thing on the machine. Timings, counts,
    paths and token totals reach the page; content never does. There's a test
    that fails if it ever leaks.
  - Costs ~nothing: the Work Log already parses `~/.claude` transcripts, so
    session metadata now comes out of the *same* pass and the same per-file
    cache. Warm render is unchanged.
  - Note the horizon: Claude Code prunes transcripts at ~29 days, so the join
    only explains *fresh* ghosts. Worktrees persist; sessions expire. For
    anything older, the Worktrees verdict stands alone — which is why it's
    pessimistic by default.

- **A CLI.** The dashboard as a command — because a window you have to *open*
  loses to a command you can pipe, and a CLI needs no bundle, no Gatekeeper and
  no notarization to run.
  ```sh
  orrery status [--all] [--strict]     orrery worktrees
  orrery sessions [--days N]           orrery standup [--since today|week|month|3months]
  orrery skills [search]               <cmd> --json
  ```
  - `--json` on every command, so it composes with what you already use:
    `orrery status --json | jq '.projects[] | select(.attention) | .name'`
  - `orrery status --strict` exits non-zero when something needs you, so
    `orrery status --strict && ./deploy.sh` won't deploy over unsaved work.
  - It reads the **installed app's config**, so the CLI and the window always
    describe the same workspace (`--data` / `$ORRERY_DATA` to override).
  - Colour only when attached to a terminal, and `NO_COLOR` is honoured — piped
    output is clean text.

### Changed
- `generate.workspace()` is now the single source of truth for "what needs you".
  The attention rollup used to live inline in the HTML render; the GUI and CLI
  now both call it, so the two surfaces cannot disagree about which repos need
  you or what the totals are.

### Known issue
- **"Needs attention" over-reports** ([#44](https://github.com/jokeane9/orrery/issues/44)).
  `collect()` counts every unmerged *remote* branch, so a repo you cloned to read
  gets flagged for upstream branches you'll never merge (langflow: 1884). Both
  the window and `orrery status` inherit it. Fix queued.

## [2.0.0] — 2026-07-16
### Changed
- **Mission Control is now Orrery.** The old name collided with Apple's own
  Mission Control, and the collision wasn't cosmetic: `open -a "Mission Control"`
  resolved to Apple's window manager, so the most common scripted launch path
  silently did nothing. An orrery is a desk instrument that shows every planet's
  position at once — the product in one word. The app, the Homebrew cask
  (`mission-control-desktop` → `orrery`), the bundle id, the winget package, and
  the download filenames all move together.
- **Major, not minor.** Nothing about `baseline.json`'s schema changed, but the
  cask token and bundle id did, and that's the most install-breaking thing a
  release can do short of a schema change. You deserve the signal.

### Migrations (automatic — you shouldn't have to do anything)
- **Your config moves with you.** The data dir is keyed off the app name, so
  first launch copies `Mission Control/` → `Orrery/` (baseline, PM notes, caches)
  rather than opening empty. It copies rather than moves — the old folder stays
  put as a fallback, and is only cleaned up by `brew uninstall --zap`.
- **Your GitHub token still works.** The keychain service was renamed too; a
  pre-2.0 token is read from the old entry once and re-saved under the new one,
  so the rename doesn't look like a surprise logout.
- **`.mission-control.json` still works.** The per-repo block file is now
  `.orrery.json` / `.orrery.yml` (and the `orrery:` frontmatter key), but the old
  spellings are still read — they live in *your* repos, so this release can't
  retire them. New name wins where both exist.

### Upgrading
- **Homebrew:** `brew upgrade` follows the rename automatically (the tap carries
  a `cask_renames.json`). On macOS the first launch of any new unsigned version
  needs one "Open Anyway" in System Settings → Privacy & Security (see the
  README) — that's notarization, not this rename.
- **If you set `HOMEBREW_REQUIRE_TAP_TRUST`,** Homebrew trusts casks by *token*,
  so the rename invalidates your existing entry and the cask is refused until you
  re-trust it once:
  ```sh
  brew trust --cask jokeane9/tap/orrery
  ```
  Most people don't set that variable and won't see this.
- **Windows:** the installer upgrades in place; the Start-menu entry is renamed.
- **winget:** the package identifier changed, so `winget upgrade` won't cross the
  rename — install `JohnOKeane.Orrery` once.

## [1.7.0] — 2026-07-16
### Added
- **Worktrees view** — every extra checkout across your repos in one place, with
  a safe-to-remove verdict on each. A worktree is a second folder checked out
  from the same repo; Claude Code creates them under `.claude/worktrees/` and
  only auto-removes them on a clean session exit, so interrupted sessions leave
  ghost folders that no `git status` will ever mention. Each row shows the
  parent repo, path, branch (or detached), age, uncommitted count and unmerged
  commits; oldest first, so the ones you've forgotten surface at the top.
  A worktree is only called safe when it has **zero uncommitted files** *and* a
  HEAD reachable from some branch — anything else says NO and why.

## [1.6.1] — 2026-07-14
### Fixed
- **The PM scratchpad can no longer lose edits to the background refresh.** The
  periodic reload now waits while the pad has unsaved changes or focus.
- **"Copy as standup" now copies the most recent day you actually committed**
  (so Monday grabs Friday), instead of always copying "yesterday" and coming up
  empty after a weekend.
### Changed
- The overview's top line leads with **attention** — "⚠ N projects need
  attention · X uncommitted, Y unpushed" (or "✓ All clear") — instead of just a
  commit count, so the first thing you read is what needs you.

## [1.6.0] — 2026-07-14
### Added
- **Groups are folders now.** Click a group in the sidebar to filter the main
  view to just that group's projects, with a breadcrumb back to all. The
  chevron still collapses the group in place — click targets are split so the
  two never collide.
- **Drag-and-drop** the sidebar: drag a group header to reorder groups, or drag
  a project into another group to regroup it. Your arrangement is remembered
  per machine.
- **Attention rollup dots** on group headers — a collapsed group still shows an
  amber dot when a project inside it needs you.
### Changed
- The overview grid and each sidebar group are now ordered **needs-attention
  first, then by tier**, so the loudest thing on screen is the thing that needs
  you — not whatever was discovered first.
- Cards with no thesis fall back to the last commit message instead of blank space.
- "Ungrouped" is now **Other**.
### Fixed
- **Keyboard accessibility:** every sidebar item, tab, card, and group is now
  focusable and activatable with Enter/Space, with a visible focus ring.
- Muted/secondary text now meets WCAG AA contrast on the dark theme; added a
  reduced-motion preference.
### Added
- **Project groups in the sidebar.** The flat project list is now organized into
  named, collapsible sections (collapse state remembered per machine).
- **Auto-organize.** Groups are inferred for you from general repo signals —
  shared name prefixes (shelf / shelf-site / shelf-workbench → *shelf*), shared
  GitHub owner, or a common sub-folder — so you don't hand-sort. Nothing is
  hardcoded; it works for any set of repos.
- A **Group** field in the project editor to override the auto grouping; manual
  groups always win, and unassigned repos fall under *Ungrouped*.

## [1.4.1] — 2026-07-14
### Fixed
- The app no longer swallows dashboard-regeneration errors silently. If a
  refresh fails, the traceback is written to `error.log` in the data dir (and
  stderr) instead of leaving a stale page with no signal. No behavior change in
  the normal case — purely diagnosability.

## [1.4.0] — 2026-07-14
### Added
- **PM tab** — a local admin scratchpad as a top-level view. One free-text
  notes area that autosaves to a local file as you type (and when you switch
  views), so you always have a place to jot priorities, follow-ups, and
  decisions. Local-only, never synced.
- `PRODUCT.md` — the canonical product doc (what it is, who it's for, the
  non-goals, and the open product questions incl. the deliberate no-sync /
  no-accounts stance).

## [1.3.0] — 2026-07-14
### Added
- Three new top-level sidebar views alongside the overview:
  - **Skills** — a searchable catalog of your Claude Code skills (installed
    plugins, each project's `.claude/skills/`, and `~/.claude/skills/`),
    grouped by source with count badges and invoke hints.
  - **Work Log** — your own commits across every dashboard repo: a
    commits-per-day chart plus a day-grouped commit list (repo · message ·
    time), filtered by Today / Week / Month / 3 months, with a
    **Copy as standup** button (yesterday's commits → clipboard).
  - **Roadmap** — every project's `ROADMAP.md` Now/Next sections in one
    place, each linked to the full file.
- Work Log also charts your per-day Claude Code token usage (parsed from
  `~/.claude` session transcripts with a per-file cache) as a second small
  chart sharing the time axis.
- The overview gains a "Today · N commits across M repos" line.

## [1.2.2] — 2026-07-13
### Fixed
- Scrollbars now match the dark theme instead of rendering as bright white/grey
  WebKit defaults.

## [1.2.1] — 2026-07-13
### Added
- GitHub sync status in the sidebar — repo count + relative last-synced time.
- Uncloned GitHub repos get a **Clone** button that clones into your first
  `roots` folder and turns them into a normal local card.
### Changed
- Connecting GitHub now **auto-syncs**, so your repos appear immediately instead
  of a confusing "not synced yet" state.

## [1.2.0] — 2026-07-13
### Added
- **Auto-populate** — point `"roots"` at a folder and Mission Control discovers
  your git repos and fills each card from the repo itself: `.mission-control.json`
  / `CLAUDE.md` / `AGENTS.md` blocks, `package.json`/git metadata, and README
  prose. Your `baseline.json` values always win; auto-fill only fills gaps (#16).
- **Provenance badges** — auto-derived fields show `auto` / `guess`; manual
  overrides stay plain, so you can see what you set vs what was inferred (#17).
- **Auto-maps** — architecture/pipeline map tabs are detected per repo instead of
  needing per-project config (#18).
- **GitHub sync** (opt-in) — connect a fine-grained token (stored in the OS
  keychain) and sync your repos into cards, including ones not cloned locally,
  shown as "not cloned" (#19, #20). Token and network stay out of the render path.
- **Native menu bar** — File / GitHub / Help menus surfacing existing actions.
### Changed
- CI action versions bumped (Dependabot): checkout, setup-python,
  upload/download-artifact, action-gh-release.

## [1.1.0] — 2026-07-12
### Added
- In-app config editor — add, edit, and delete projects from a form in the
  dashboard instead of hand-editing `baseline.json` (#13). Available in the
  desktop app; a plain browser stays read-only.

## [1.0.2] — 2026-07-12
### Fixed
- Homebrew tap auto-bump now updates the cask through the GitHub Contents REST
  API (fine-grained PATs are rejected over git-HTTPS basic auth).

## [1.0.1] — 2026-07-12
### Fixed
- Release artifact version no longer keeps the tag's leading `v`, so the
  Homebrew cask download URL resolves.

## [1.0.0] — 2026-07-12
### Added
- First public release. macOS `.dmg` and Windows installer + portable zip built
  from one codebase.
- Live per-project git dashboard (branch, uncommitted, unmerged, unpushed) plus
  editable per-project facts in `baseline.json`.
- Per-user config seeded from a sample on first launch; background refresh.
- CI release pipeline: `v*` tag → build both platforms → publish GitHub Release
  → auto-bump the Homebrew cask.

[Unreleased]: https://github.com/jokeane9/orrery/compare/v1.2.2...HEAD
[1.2.2]: https://github.com/jokeane9/orrery/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/jokeane9/orrery/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/jokeane9/orrery/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jokeane9/orrery/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/jokeane9/orrery/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/jokeane9/orrery/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/jokeane9/mission-control-desktop/releases/tag/v1.0.0
