# Changelog

All notable changes to Mission Control are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/) — one version number for both
platforms.

## [Unreleased]

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

[Unreleased]: https://github.com/jokeane9/mission-control-desktop/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/jokeane9/mission-control-desktop/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/jokeane9/mission-control-desktop/releases/tag/v1.0.0
