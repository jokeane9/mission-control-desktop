# Roadmap

Ordered by priority. Updated at the end of every session — check off completed
items, reorder if priorities shifted, add anything new. Now / Next / Later.

---

## Now

- [ ] Nothing in flight. `main` clean, released through **v1.7.0**. A full-app
      UX audit is captured in [`UX-AUDIT.md`](UX-AUDIT.md); the interaction
      model in [`UX-FLOWS.md`](UX-FLOWS.md).

## Next

- [ ] **v1.6.1 — the two UX "wrong thing" bugs** (from UX-AUDIT): PM autosave
      races the 15-min page refresh → possible edit loss; **"Copy as standup"
      ignores the filter and only copies yesterday** (empty on Mondays). Fix
      first — they misbehave silently.
- [ ] **Attention-first hero line** — replace "Today · N commits" with a
      "what needs you" rollup on the overview. (UX-AUDIT · IA F2)
- [ ] **Editor onboarding** — thesis before tier/group; `tier` → `<select>`;
      path validation/`.git` check. (UX-AUDIT · detail F2–F4)
- [ ] **Provenance made usable** — a legend + clickable "guess" → jump to that
      field in the editor. (UX-AUDIT · detail F1/F9)
- [ ] **GitHub error consistency** — replace native `alert()` in sync/clone with
      inline/toast; name the real clone path. (UX-AUDIT · detail F6/F7)
- [ ] **Design-system tightening** — consolidate the badge vocabulary
      (`.eyebrow`/`.pill`), adopt a type-scale token set, shape-encode git state
      for colorblindness. (UX-AUDIT · global F4/F7/F8)
- [ ] **Windows code signing** ([#7](https://github.com/jokeane9/mission-control-desktop/issues/7)) —
      SignPath enrollment → activates the already-wired step. Owner action.
- [ ] **winget listing** ([#8](https://github.com/jokeane9/mission-control-desktop/issues/8)) —
      manifests verified/prepped; blocked on #7.
- [ ] **Post the launch** — Show HN / r/programming / X drafts ready
      ([#11](https://github.com/jokeane9/mission-control-desktop/issues/11) is
      done — blog post live on killdate.dev).

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

- [x] 2026-07-16 — **Worktrees view** (v1.7.0, #36): `views.collect_worktrees()`
      + a workspace tab listing every extra checkout — repo, path, branch/
      detached, age, uncommitted, unmerged — each with a safe-to-remove verdict
      (clean tree AND HEAD reachable from a branch; anything else says NO and
      why). Closes the invisible-state hole: ghost worktrees left under
      `.claude/worktrees/` by interrupted Claude Code sessions, which no
      `git status` reports. Ported from a local bash script, fixing its
      macOS-only `stat -f %m` (would have broken the Windows build) and its
      dead unmerged count.
- [x] 2026-07-14 — **Groups become folders + triage + keyboard a11y** (v1.6.0,
      #33): click-a-group folder filter + breadcrumb, drag-and-drop reorder/move
      (localStorage), attention rollup dots, attention→tier sort, WCAG-AA
      contrast + keyboard operability. Built from the 5-agent UX audit
      ([`UX-AUDIT.md`](UX-AUDIT.md), [`UX-FLOWS.md`](UX-FLOWS.md)).
- [x] 2026-07-14 — **Auto-organized project groups** (v1.5.0, #32):
      `resolve.auto_groups()` (name-prefix → owner → parent-dir) + collapsible
      sidebar groups + manual `Group` editor override.
- [x] 2026-07-14 — **macOS Open-Anyway cask caveats** (#31 + live tap): brew
      prints the first-launch Gatekeeper steps. Real fix is notarization (#9).
- [x] 2026-07-14 — **Regen errors are logged, not swallowed** (v1.4.1, #30):
      `app.py._log_exc` → DATA/error.log. (After a QA false-alarm where a stale
      instance masqueraded as a broken build — see `_log.md`.)
- [x] 2026-07-14 — **PM scratchpad tab + canonical `PRODUCT.md`** (v1.4.0,
      #28): a local autosaving admin notes view (bridge-gated like the config
      editor; `pm_notes.md` in the data dir, gitignored) and the first product
      doc. Sync/login captured as a deliberate no in PRODUCT.md's open
      questions, not built.
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
