# Changelog

All notable changes to Mission Control are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/) — one version number for both
platforms.

## [Unreleased]

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

[Unreleased]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/jokeane9/mission-control-desktop/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/jokeane9/mission-control-desktop/releases/tag/v1.0.0
