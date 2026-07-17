# Changelog

All notable changes to Mission Control are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/) — one version number for both
platforms.

## [Unreleased]

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

[Unreleased]: https://github.com/jokeane9/mission-control-desktop/compare/v1.2.2...HEAD
[1.2.2]: https://github.com/jokeane9/mission-control-desktop/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/jokeane9/mission-control-desktop/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/jokeane9/mission-control-desktop/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/jokeane9/mission-control-desktop/releases/tag/v1.0.0
