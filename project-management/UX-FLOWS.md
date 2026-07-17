# UX Flows — the interaction model

How Orrery is meant to be navigated and operated, as of v1.6.0. This is
the canonical description of the user-facing model; when you change an
interaction, update this file.

---

## Navigation altitude (three zooms)

```
ALL PROJECTS  ──open a group──▶  GROUP FOLDER  ──open a project──▶  PROJECT DETAIL
   (overview grid)                (filtered grid)                    (tabs + rows)
        ▲                              │                                  │
        └──────────── ‹ All projects / ⌘0 / click "overview" ────────────┘
```

- **All projects** — the `overview` view: a grid of every project's card, sorted
  **needs-attention-first, then by tier**. Reached by ⌘0, the sidebar
  `overview` item, or "‹ All projects" in a folder breadcrumb.
- **Group folder** — the same overview grid, filtered to one group's cards, with
  a `‹ All projects ▸ GROUP N` breadcrumb. Reached by clicking a group's header
  body in the sidebar (URL hash `#g/<gid>`).
- **Project detail** — one project's view: overview pane (labeled rows +
  provenance) + optional architecture/pipeline map tabs. Reached by clicking a
  card or a sidebar project item, or ⌘1–9 (URL hash `#p/<name>`).

---

## The sidebar

Top → bottom:

1. **overview** (⌘0).
2. **Workspace views:** skills · work log · roadmap · pm (top-level, always present).
3. **Projects (N)** — grouped into collapsible, reorderable **folders**.

### A group header — three gestures, three zones (no ambiguity)

| Gesture | Zone | Result |
|---|---|---|
| Click the **chevron** `▾` | the chevron only | Collapse/expand the group in place (sidebar). Persists per machine. |
| Click the **header body** (name / count) | rest of the header | **Open the folder** — filter the main grid to this group. Header goes active (blue bar). |
| **Drag** the header | anywhere on it | Reorder the group among the others. |

A group header also shows an **amber rollup dot** when any project inside needs
attention — visible even when the group is collapsed, so nothing urgent hides.

### A project item — two gestures

| Gesture | Result |
|---|---|
| **Click** | Open that project's detail view (clears any folder filter). |
| **Drag** | Move the project into another group. |

---

## Grouping & auto-organize

Groups form automatically; you only touch them to correct the guess.

- **Auto-organize** (`resolve.auto_groups`) infers a group per repo from general,
  offline signals, first match wins:
  1. **name-prefix family** — ≥2 repos share a first name token
     (`shelf` / `shelf-site` / `shelf-workbench` → *shelf*);
  2. **owner family** — ≥2 ungrouped repos share a GitHub owner;
  3. **parent-dir family** — ≥2 repos in a shared non-root sub-folder.
  Everything else → **Other** (rendered last).
- **Manual override wins.** A `Group` value set in the in-app editor (or
  `baseline.json`) is authoritative; auto never overwrites it. Auto-assigned
  groups are provenance-marked as a guess.
- Two override channels, kept distinct: the editor `Group` field writes
  `baseline.json` (durable, cross-device); **drag** writes `localStorage` (a
  per-machine view arrangement, re-applied after every regen). This matches the
  app's local-first model, same as collapse state.

---

## Drag-and-drop persistence

- **Reorder groups** → `localStorage.mcGroupOrder` (array of group ids).
- **Move a project** → `localStorage.mcGroupOverrides` / `mcItemGroup`
  (`{project: group-id}`); on drop the project's **card** `data-group` and the
  group **counts** update too, so the folder filter stays consistent.
- Both are restored on load and survive the 15-minute regen. To make a dragged
  grouping durable/cross-device, set it in the editor `Group` field instead.

---

## Keyboard

| Key | Action |
|---|---|
| ⌘0 | All projects (clears any folder filter) |
| ⌘1–9 | Jump to the 1st–9th project in flattened sidebar order |
| ⌘R | Refresh git (rescan all repos) |
| Enter / Space | Activate the focused element (item, tab, card, group, breadcrumb) |
| Esc | Close a modal |
| Tab | Move focus; every nav element is reachable with a visible focus ring |

Note: ⌘1–9 are positional in the flattened sidebar order and can shift after a
drag-reassign — expected.

---

## Editing a project (packaged app only)

The config editor and GitHub actions require the pywebview bridge; in a plain
browser they are read-only (the page falls back to `nobridge` styling).

- **Add / Edit** → modal form generated from `PROJECT_FIELDS`; saves to
  `baseline.json` and regenerates. Name + path are required.
- **Delete** → confirmation ("only edits baseline.json — does not touch the
  repo"); removes the override entry.
- **Provenance** — `auto` (derived from repo/GitHub) vs `guess` (inferred from
  prose) badges mark auto-filled fields; a field you typed carries no badge.
- **GitHub** — connect a fine-grained token (stored in the OS keychain, never in
  config) → sync repos → uncloned repos show a **Clone** action → become normal
  local cards.

---

## Freshness

Git data is a snapshot from generation time. The page meta-refreshes on a timer;
if regeneration stops (app quit / watcher died), a red **STALE** banner replaces
the "updated …" line rather than silently trusting an old snapshot.
