# Roadmap

Ordered by priority. Updated at the end of every session — check off completed
items, reorder if priorities shifted, add anything new. Now / Next / Later.

---

## Now

- [ ] Nothing in flight. `main` clean, 0 open PRs. Auto-populate P1→P3.2 all
      merged but **not yet released** (main is ahead of the v1.1.0 tag).

## Next

- [ ] **Verify GitHub sync with a real token** — the one deferred P3.2 check:
      connect a fine-grained PAT (Metadata + Contents: read), hit "sync repos",
      confirm owned repos populate and uncloned ones show "not cloned". (tonight)
- [ ] **Cut v1.2.0** — release the auto-populate + config-editor + GitHub work
      (`git tag v1.2.0 && git push --tags`). ⚠ First release exercising the
      Dependabot `release.yml` action bumps (upload/download-artifact, gh-release,
      setup-python, checkout) — watch that run; one-line reverts if any break.
- [ ] **P3.3 — GitHub sync UI polish** ([#15](https://github.com/jokeane9/mission-control-desktop/issues/15)) —
      last-synced timestamp, a "clone" affordance on uncloned cards, sync progress.
- [ ] **Windows code signing** ([#7](https://github.com/jokeane9/mission-control-desktop/issues/7)) —
      SignPath enrollment → activates the already-wired step. (`platform:windows`, `signing`)
- [ ] **winget listing** ([#8](https://github.com/jokeane9/mission-control-desktop/issues/8)) —
      after signing. (`platform:windows`, `packaging`)

## Later

- [ ] **P4 — LLM extraction** ([#15](https://github.com/jokeane9/mission-control-desktop/issues/15)) —
      feed a repo's CLAUDE.md to Claude to distill card fields for repos without a
      structured block. Opt-in, needs an API key + disclosure. **Deferred by decision.**
- [ ] **macOS notarization** — Apple Developer Program ($99/yr) + 6 secrets.
      CI ready. (`platform:mac`, `signing`)
- [ ] **Tahoe icon polish** — `.icon` (Icon Composer) + `Assets.car` for macOS 26. Cosmetic. (`platform:mac`)
- [ ] **Blog launch post** — the open-source / donation announcement.
- [ ] **Name decision** — "Mission Control" collides with Apple's window manager.

---

## Completed

- [x] 2026-07-14 — **Top-level views epic** (v1.3.0): Skills catalog (#24),
      Work Log — commits chart + list + standup copy + overview Today line
      (#25), Roadmap aggregator (#26), per-day Claude token chart with a
      transcript cache (#27). All render-path only; `views.py` new stdlib
      sibling module.

- [x] 2026-07-12 — Auto-populate epic (#15), P1→P3.2 merged: local discovery +
      resolver (#16), provenance badge (#17), P2 auto-maps (#18), P3.1 GitHub
      auth — keychain token (#19), P3.2 GitHub sync — repos→cache→cards incl.
      uncloned (#20). Local scan offline; GitHub opt-in; token/network stay out
      of the render path. (P4 LLM extraction deferred.)
- [x] 2026-07-12 — Merge sweep: cleared 5 stale Dependabot PRs (#2–#6) +
      P3.2 (#20); main clean, 0 open PRs
- [x] 2026-07-12 — In-app config editor (#13), shipped in v1.1.0 — add/edit/
      delete projects from a form; verified end-to-end in the real app
- [x] 2026-07-12 — PM + CI/CD scaffolding: CLAUDE.md, project-management/ docs,
      guardrail `ci.yml` (lint + render smoke + both-platform build on PRs),
      branch protection on `main` (requires CI), CHANGELOG, Dependabot,
      issue/PR templates, labels + v1.1 milestone, roadmap seeded to issues #7–#13
- [x] 2026-07-12 — Cross-platform refactor (per-user data dir when frozen,
      first-run sample seeding, Ctrl labels on Windows, configurable viz tools)
- [x] 2026-07-12 — Packaging: PyInstaller spec, mac sign/notarize/staple script,
      Windows Inno Setup installer w/ WebView2 bootstrap, icon.ico generator
- [x] 2026-07-12 — CI release workflow: v* tag → build both → publish → bump tap
- [x] 2026-07-12 — Public repo + Homebrew tap set up; v1.0.0–v1.0.2 released;
      auto-bump proven end-to-end
- [x] 2026-07-12 — Docs: CLAUDE.md, DISTRIBUTION.md, project-management/, README
