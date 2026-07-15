# UX Audit — 2026-07-14

A full-app UX review run after the project-groups feature landed (v1.5.0),
because groups sit "at the seams" of the app and exposed how muddled some of
the interaction model had become. Five design/UX passes, each grounding in the
actual source before recommending:

1. **Grouping interaction spec** — resolve collapse-vs-filter-vs-drag on the
   group elements.
2. **Home / information architecture** — the overview grid, cards, "Today"
   line, status bar, empty states.
3. **The four workspace views** — Skills, Work Log, Roadmap, PM.
4. **Project detail + config editor + GitHub flows.**
5. **Global visual system + interaction consistency + keyboard + a11y.**

---

## Cross-cutting themes (all reviewers converged)

1. **The home screen was an activity log, not a triage queue.** Cards rendered
   in discovery order; "needs attention" was marked only by a ~3px near-invisible
   border and encoded three times (card border, sidebar dot, stats bar) but
   never *ranked* or stated in plain language. The hero line counted commits
   ("what did I do") instead of surfacing what needs you ("what should I do").
2. **The app was keyboard-dead.** Every navigational element was a
   `<div onclick>` — not focusable, no Enter/Space, no visible focus ring — so
   the core loop was mouse-only. `--faint` (`#6e7681`), the most-used small-text
   color, failed WCAG AA (~4:1).
3. **The group model needed the folder / collapse / drag split.** The whole
   header was bound to collapse, leaving no gesture for "open this folder."
4. **Two features quietly did the wrong thing** (worse than looking wrong):
   PM autosave can lose edits to the periodic full-page refresh; "Copy as
   standup" ignores the active filter and only ever copies *yesterday* (empty on
   Mondays).

---

## Findings by surface (ranked; anchors are file:concept)

### Home / IA
- **F1 (critical) — grid not sorted by attention.** Discovery order; accent is a
  hairline. → sort needs-attention → tier → recency. `generate.py` card loop.
- **F2 (high) — "Today · N commits" is a vanity hero.** → attention-first rollup
  ("⚠ 3 need you · 12 uncommitted, 5 unpushed" / "✓ all clear · 6 commits").
  `views.py:today_line` + `totals`.
- **F3 (high) — stats bar is redundant + inert.** → promote attention to the
  hero, keep the bar for machine-state (freshness/refresh) only; make the count
  a clickable grid filter.
- **F4 (high) — `.card.accent` too weak, card never says *why*.** → full left
  border + tint + a plain-language state ("needs commit", "push 5").
- **F5 (high) — `tier` collected but never prioritizes / shows.** → secondary
  sort key + de-emphasize minor.
- **F6 (med) — grid order ≠ sidebar order** (partly resolved by folder filter).
- **F7 (med) — first-run is three separate zero-states.** → one real empty state.
- **F8 (med) — blank thesis = dead card.** → fall back to last commit message.
- **F9 (low-med) — `focus` ("the one thing") buried in detail.** → surface on card.

### Workspace views
- **F1 (high) — PM autosave races the meta-refresh → data loss.** → guard the
  reload while the pad is dirty/focused.
- **F2 (high) — "Copy as standup" ignores the filter, only copies yesterday**
  (breaks Mondays). → respect the active range and/or relabel; skip weekends.
- **F3 (med-high) — Skills search: no "no matches" state, no result count.**
- **F4 (med-high) — Roadmap `file://` links hijack the pywebview window.** →
  bridge "open in editor" with browser fallback.
- **F5 (med) — "Today" filter draws one degenerate bar.** → list, not a 1-bar chart.
- **F6 (med) — token chart: jargon caption, no range total, heterogeneous sum.**
- **F7 (med) — jumpy midpoint gridline; x-axis drawn twice** across the stacked charts.
- **F8 (med) — the four views are orphaned** (grey dots, no "Workspace" label, no
  shortcuts).
- **F9 (med) — Skills groups don't collapse; plugin labels noisy.**
- **F10 (low-med) — inconsistent empty-state voice.**

### Detail / editor / GitHub
- **F1 (high) — provenance is undiscoverable.** 8px badges, meaning only in
  tooltips + by *absence*; no legend. → legend + bump size.
- **F2 (high) — editor front-loads jargon** (name→path→**tier**→**group**→thesis).
  → move thesis to 3rd; tier/group near the end.
- **F3 — `tier` is undocumented free text.** → `<select>`.
- **F4 — path unvalidated; broken paths save silently.** → check `isdir`/`.git`,
  soft-warn; folder-picker via bridge.
- **F6 — Clone: unnamed "roots folder", no progress.**
- **F7 — inconsistent error surfaces** (inline vs native `alert()`).
- **F9 — "guess" badge is a dead-end.** → clickable → open editor at that field.
- **F10 — Delete looks identical to Edit until hover.** → persistent danger styling.
- **F12 — `delete_project` result ignored; always reports success.** (`app.py`)

### Global visual / a11y
- **F1 (critical) — all nav is `<div onclick>`** → keyboard-dead. → `tabindex`/
  `role` + global Enter/Space delegator (or real `<button>`s).
- **F2 (critical) — focus invisible everywhere.** → one `:focus-visible` rule.
- **F3 (high) — `--faint` fails WCAG AA.** → `#868f9c`.
- **F4 (high) — color-only git-state signal** (green/amber dot; chart blue/green)
  — the CVD confusion axis. → shape/count backing.
- **F5 (med) — modals lack dialog semantics + focus trap.**
- **F7 (med) — badge/label vocabulary sprawl** (~7 near-identical treatments).
- **F8 (low-med) — ad-hoc type scale** (11 sizes, 8px floor). → token scale.
- **F11 (low) — no `prefers-reduced-motion`.**

---

## Shipped in v1.6.0 (the seam release)

- **Groups → folders:** click a group filters the overview to its cards with a
  breadcrumb back to all; the chevron collapses in place (split hit-targets).
  *(grouping spec; addresses IA F6)*
- **Drag-and-drop:** reorder groups; move a project between groups; persisted
  per-machine in localStorage; restored on load with card `data-group` + counts
  in sync.
- **Attention rollup dot** on group headers (survives collapse).
- **Triage:** grid + each group sorted attention-first → tier. *(IA F1, F5)*
- **Blank thesis → last commit** *(IA F8)*; stronger `.card.accent` *(IA F4a)*;
  "Ungrouped" → "Other".
- **Accessibility:** keyboard operability + `:focus-visible` + `--faint`→`#868f9c`
  + reduced-motion. *(global F1, F2, F3, F11)*

## Recommended next (v1.6.1 and beyond, prioritized)

1. **The two "wrong thing" bugs first** — PM autosave-vs-refresh race; "Copy as
   standup" scope. *(views F1, F2)*
2. **Attention-first hero line.** *(IA F2)*
3. **Editor onboarding** — field reorder, tier→select, path validation.
   *(detail F2–F4)*
4. **Provenance made usable** — legend + clickable "guess" → jump-to-field.
   *(detail F1, F9)*
5. **GitHub error consistency** — replace `alert()` with inline/toast.
   *(detail F7)*
6. **Roadmap "open in editor" via bridge** *(views F4)*; Skills "no matches" +
   count *(views F3)*; token-chart caption + range total *(views F6)*.
7. **Design-system tightening** — consolidate the badge vocabulary into
   `.eyebrow`/`.pill`; adopt a type-scale token set; shape-encode git state for
   CVD. *(global F4, F7, F8)*
8. **Delete-button danger styling** *(detail F10)*; return the real
   `delete_project` result *(detail F12)*.

Dark-only is fine (a power-user instrument) — not worth a light theme. Reviewers
agreed the token foundation, the STALE freshness guard, the mono/sans split, and
the auto-organize heuristic are genuinely good; keep them.
