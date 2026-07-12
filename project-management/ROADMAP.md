# Roadmap

Ordered by priority. Updated at the end of every session — check off completed
items, reorder if priorities shifted, add anything new. Now / Next / Later.

---

## Now

- [ ] Nothing in flight. Baseline shipped: v1.0.2 live on Mac + Windows, Homebrew
      tap auto-bumping.

## Next

- [ ] **Windows code signing** — enroll in SignPath Foundation (free OSS), add the
      signing step to `release.yml` before the release upload. Kills SmartScreen.
      (`platform:windows`, `signing`)
- [ ] **winget listing** — PR a manifest to microsoft/winget-pkgs pointing at the
      GitHub release. Do *after* signing (winget rejects low-reputation unsigned
      installers). (`platform:windows`, `packaging`)
- [ ] **CI on PRs** — a `ci.yml` that builds both platforms + lints on every PR,
      so a broken change can't reach a tag. Add branch protection once it's green.

## Later

- [ ] **macOS notarization** — join Apple Developer Program ($99/yr), add the 6
      signing secrets. CI already supports it. (`platform:mac`, `signing`)
- [ ] **Tahoe icon polish** — author a `.icon` (Icon Composer) + ship `Assets.car`
      so the icon isn't shrunk inside the generic glass tile on macOS 26. Cosmetic.
      (`platform:mac`)
- [ ] **Blog launch post** — the open-source / donation announcement.
- [ ] **Name decision** — "Mission Control" collides with Apple's window manager;
      consider a distinct launch name before wide promotion.
- [ ] **Config UX** — in-app editing of `baseline.json` instead of hand-editing.

---

## Completed

- [x] 2026-07-12 — Cross-platform refactor (per-user data dir when frozen,
      first-run sample seeding, Ctrl labels on Windows, configurable viz tools)
- [x] 2026-07-12 — Packaging: PyInstaller spec, mac sign/notarize/staple script,
      Windows Inno Setup installer w/ WebView2 bootstrap, icon.ico generator
- [x] 2026-07-12 — CI release workflow: v* tag → build both → publish → bump tap
- [x] 2026-07-12 — Public repo + Homebrew tap set up; v1.0.0–v1.0.2 released;
      auto-bump proven end-to-end
- [x] 2026-07-12 — Docs: CLAUDE.md, DISTRIBUTION.md, project-management/, README
