# Changelog

All notable changes to Mission Control are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/) — one version number for both
platforms.

## [Unreleased]

## [1.5.0] — 2026-07-14
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
