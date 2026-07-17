# Roadmap

Ordered by priority. Updated at the end of every session — check off completed
items, reorder if priorities shifted, add anything new. Now / Next / Later.

---

## The wedge (read before prioritising)

**Orrery's differentiator is not the git dashboard.** Every tool shows branch and
dirty count. Look instead at what actually got built: a Skills catalog, a Claude
token chart, and a Worktrees view that exists *specifically* because interrupted
Claude Code sessions strand checkouts under `.claude/worktrees/`. That's three
features about **the state your agents leave behind across many repos** — and
nobody else ships it.

The evidence it's real: on 2026-07-16 the Worktrees view was built because six
ghost worktrees, up to 68 days old, were sitting in two repos where no
`git status` would ever mention them.

So the strategy is: **be the dashboard for agent-assisted development**, and let
the git state be the table stakes underneath it. Sessions ([#39](https://github.com/jokeane9/orrery/issues/39))
is the deliberate version of what Worktrees stumbled into. Weigh new work against
that, not against "what would a git dashboard have?"

The second lesson from the same day: the maintainer, faced with a real problem,
wrote a **bash script** (`~/.local/bin/wt`), not a window. Devs live in the
terminal. The CLI ([#38](https://github.com/jokeane9/orrery/issues/38)) isn't a
side quest — it's the surface that matches the instinct, and it routes around the
distribution friction (Gatekeeper, notarization) entirely.

## Now

- [ ] Nothing in flight. `main` clean, released through **v2.2.1**. Next up is
      distribution: notarization (#9) so installs stop fighting Gatekeeper, then
      the launch post. See the full-app UX audit in [`UX-AUDIT.md`](UX-AUDIT.md).

## Next

- [ ] **Uncloned repos can't be grouped or annotated**
      ([#40](https://github.com/jokeane9/orrery/issues/40)) — `resolve.overrides()`
      matches by path, so an uncloned repo can never take a manual group. Found
      while organising 28 projects: the only workaround was to clone the repo.
      Fix by matching on identity, which `discover()` already does. **A real bug,
      not a preference.**
- [ ] **`roots` ignore list** ([#41](https://github.com/jokeane9/orrery/issues/41)) —
      `~/projects/_archive/` scans as live work. One repo today; archives only grow.
- [ ] **⌘K palette** ([#42](https://github.com/jokeane9/orrery/issues/42)) —
      shortcuts stop at ⌘9; a real workspace has 28 projects, so 19 have no
      keyboard path. `skills` already has the search pattern to generalise.
- [ ] **Editor onboarding** — thesis before tier/group; `tier` → `<select>`;
      path validation/`.git` check. (UX-AUDIT · detail F2–F4)
- [ ] **Provenance made usable** — a legend + clickable "guess" → jump to that
      field in the editor. (UX-AUDIT · detail F1/F9)
- [ ] **GitHub error consistency** — replace native `alert()` in sync/clone with
      inline/toast; name the real clone path. (UX-AUDIT · detail F6/F7)
- [ ] **Design-system tightening** — consolidate the badge vocabulary
      (`.eyebrow`/`.pill`), adopt a type-scale token set, shape-encode git state
      for colorblindness. (UX-AUDIT · global F4/F7/F8)
- [ ] **Windows code signing** ([#7](https://github.com/jokeane9/orrery/issues/7)) —
      SignPath enrollment → activates the already-wired step. Owner action.
- [ ] **winget listing** ([#8](https://github.com/jokeane9/orrery/issues/8)) —
      manifests verified/prepped; blocked on #7.
- [ ] **Post the launch** — Show HN / r/programming / X drafts ready
      ([#11](https://github.com/jokeane9/orrery/issues/11) is
      done — blog post live on killdate.dev).

## Later

- [ ] **P4 — LLM extraction** ([#15](https://github.com/jokeane9/orrery/issues/15)) —
      feed a repo's CLAUDE.md to Claude to distill card fields for repos without a
      structured block. Opt-in, needs an API key + disclosure. **Deferred by decision.**
- [ ] **macOS notarization** — Apple Developer Program ($99/yr) + 6 secrets.
      CI ready. (`platform:mac`, `signing`)
- [ ] **Tahoe icon polish** — `.icon` (Icon Composer) + `Assets.car` for macOS 26. Cosmetic. (`platform:mac`)
- [ ] **Blog launch post** — the open-source / donation announcement.

---

## Deliberate noes

Written down so they don't get relitigated every quarter.

- **"What changed since you last looked" / delta view.** Tempting — it sounds like
  the actual job. But a delta needs remembered state, which fights principle #3
  (live from disk, no database) and adds a sync layer that can drift. The
  attention rollup already answers "what needs you" with zero stored state.
- **CI / build status.** Users will ask. PRODUCT.md's non-goal stands: scraping CI
  means tokens, network, and polling in the render path — that's a different
  product, and it breaks the offline-engine principle (#4).

## Completed

- [x] 2026-07-17 — **"Needs attention" cries wolf fixed** (v2.2.1, #44):
      `collect()` counted every unmerged *remote* branch, so repos cloned to
      read flagged on hundreds of upstream PRs (langflow: 1884). Now counts
      local branches only — 19→14 projects flagged, 2374→12 unmerged, all real.
      `collect()` had no test; now it does.
- [x] 2026-07-16 — **CLI + Sessions** (v2.2.0, #45/#46): the wedge, made
      deliberate. **Sessions** — every Claude Code session per repo (live/idle,
      branch, span, msgs, tokens) and the join that matters: a session whose
      worktree is still on disk is flagged *left a worktree*. Metadata only,
      never content (pinned by a test that plants a secret). Falls out of the
      *same* transcript pass the Work Log already did, so warm render is
      unchanged. **CLI** — `orrery status/worktrees/sessions/standup/skills`,
      `--json`, `--strict` as a deploy gate; reads the installed app's config so
      both surfaces agree. Forced `generate.workspace()` out of the HTML render,
      so the GUI and CLI can't disagree about what needs you.
      Shipped as ONE release: #46 was stacked on #45 and squash-merged first, so
      both landed in one commit — merging #45 afterwards would have *deleted*
      Sessions (663 deletions). Lesson: merge the base of a stack first.
      Learned along the way: transcripts are pruned at ~29 days, so the
      Sessions↔Worktrees join has a horizon and could never explain the 68-day
      ghost that started all this. Worktrees persist; sessions expire.
- [x] 2026-07-16 — **v2.0.0 — renamed Mission Control → Orrery** (#37): the old
      name collided with Apple's window manager, and not cosmetically —
      `open -a "Mission Control"` silently launched Apple's app, so the most
      common scripted launch path did nothing. Carried three migrations, each of
      which fails silently if it regresses: data dir (config would be orphaned →
      app opens empty), keychain service (token orphaned → looks like a logout),
      and per-repo `.mission-control.*` block files (live in *users'* repos, so
      the fallback is permanent). Cask renamed with `cask_renames.json`; verified
      a real 1.7.0 → 2.0.0 upgrade preserving config byte-for-byte.
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
