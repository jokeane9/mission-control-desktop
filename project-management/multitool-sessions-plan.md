# Multi-tool Sessions — reading Cursor next to Claude Code

Design + build plan. Verified against live Claude and Cursor data on 2026-07-17.
Scope: **Sessions only** (see "Deliberately not building").

---

## The finding that reshapes the ask

The request was to split three views by tool — Sessions, Worktrees, Work Log.
But **tool identity only exists in one of them.** Git records who you are, never
which agent typed the commit; a worktree is a plain git object. Only each tool's
own session log knows it was Claude or Cursor.

| View | Verdict | Why |
|---|---|---|
| **Sessions** | ✅ **build it** | Tool-native. Cursor's live in a local SQLite DB and read cleanly — repo, branches, files, timing all recover. This is the whole build. |
| **Worktrees** | ❌ can't, honestly | Git has no tool field, and Cursor makes **no local worktrees** (verified: every worktree flag is off; it's a cloud-agent feature). Nothing to put in a Cursor tab. |
| **Work Log** | ❌ can't, honestly | Commits carry zero tool attribution, and Work Log feeds **Copy as standup** — a guessed label would be a lie on the one surface you hand to other people. |

The two attempted escapes both fail on data: you *could* try to guess a commit's
tool from branch/time correlation (fuzzy, and it feeds standup), and you *could*
stack the Work Log **tokens** chart by tool (tokens are tool-native) — except
Cursor exposes **no token counts at all**. So the honest conclusion: the only
view that can carry tool identity is Sessions.

---

## Does it need an integration, or run on git?

**Neither an integration nor git — it reads each tool's local files, read-only.**

- Claude Code writes JSONL under `~/.claude/projects/**`.
- Cursor writes a SQLite DB at
  `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`.

No API, no network, no extension, no account. Worktrees and Work Log run on git.
The local-first promise is untouched — same read-what's-on-disk model, one new
file format.

---

## What Cursor's data actually gives us

Pulled from the live 97 MB DB. **6 real sessions** (62 other `composerData` rows
are empty drafts and `task-tool` subagents — filtered on "non-empty headers AND
a resolvable repo"). Honest empties beat faked values.

| Session field | Status | Source in Cursor |
|---|---|---|
| repo · branch · branches | ✓ recovers | `trackedGitRepos[].repoPath` + branches; file-path fallback for orphans |
| files · dirs · tools | ✓ recovers | per-message `toolFormerData` (edit/read/run), **path string only** |
| started · ended · active | ✓ recovers | `createdAt` / `lastUpdatedAt` / branch `lastInteractionAt` |
| messages | ✓ recovers | `len(fullConversationHeadersOnly)` |
| lines added / removed | ✓ bonus | `totalLinesAdded/Removed` — richer than Claude's record |
| **tokens** | ✗ empty | `usageData` is blank on every session → leave 0 |
| **pull requests** | ✗ empty | `pullRequests` array never populated locally → leave [] |
| **worktree** | ✗ none | no local worktrees (cloud-agent feature) → leave "" / False |

### Repo attribution (the one hard part), first hit wins
1. `composerData.trackedGitRepos[0].repoPath` — absolute (`/Users/keane/projects/shelf`).
2. `composerData.workspaceIdentifier.uri.path`, cross-checked against
   `workspaceStorage/<id>/workspace.json`.
3. **Bubble fallback** for older sessions: scan `bubbleId:<composerId>%` rows,
   pull absolute paths from `toolFormerData.rawArgs`, longest-prefix match with
   Orrery's existing `_match_repo`. (This resolved 100% of real sessions.)

---

## How the view reads — unified, not tabbed

Hard tabs would *un-stack* the very thing worth stacking. One view, a lightweight
source filter, and a per-row tag.

- **`All · Claude · Cursor` filter** — reuse the Work Log range-pill component
  (`.fbtn`). Default All. A 3rd tool later is one more pill, not a rebuild.
- **Per-row source tag** — reuse the `.prov` pill, placed first on the row.
  Claude → `--blue` (already owns it); Cursor → a new `--cursor:#bc8cff` purple,
  in-family and deliberately **not** green/amber/red (those mean state/safety).
  The live/idle **dot stays state**; the tag is tool. Two orthogonal channels.
- **Stacking** — repo-grouped, then time-desc, tools interleaved. Repo is the
  mental unit; the tag carries the tool.
- **Three honest empty states** — Cursor *not detected* → ghosted pill (proof we
  looked); *detected but quiet* → active pill, empty result; *has sessions* →
  normal. A missing tool never just vanishes.
- **Bonus the data unlocks** — a per-repo, cross-tool timeline: everything that
  touched one repo, every agent, in one frame. The literal tagline, made plural
  about the agents. (Follow-up, not this build.)

---

## Build phases

1. **Adapter refactor — no behaviour change.** Lift the Claude reader behind a
   `SessionSource` interface; `collect_sessions` becomes source-agnostic and
   gains a `source` field. Default stays Claude-only, so every existing test
   passes untouched. Shippable alone.
2. **CursorSource.** Read `composerData` rows (0.5 MB, cheap), attribute repo,
   scan bubbles for the footprint. Open the DB `mode=ro&immutable=1` so it never
   locks a running Cursor. Cache per session on `(lastUpdatedAt, msg-count)` — the
   97 MB DB is never fully scanned. Match edit tools by **prefix** (`edit_file`,
   `write`, `apply`, `search_replace`) since Cursor versions the `_v2` suffix.
3. **Render.** Source filter + per-row tag in `sessions_html` and
   `orrery sessions`. Rows already guard every chip on truthiness, so Cursor's
   empty tokens/PRs render as clean absence, not zeroes.
4. **Tests.** Extend the content-leak guard to the Cursor path (the DB is full of
   prompt text — reader touches only paths, names, timestamps). Add a Cursor-DB
   fixture; skip cleanly when no DB is present.

Roughly a Phase-1 PR, then a Phase-2/3/4 PR — two coherent releases.

---

## Risks (from the reverse-engineering)

- **No schema contract.** Cursor internals, undocumented. Field renames silently
  break extraction → every access defensive; a source that raises is swallowed so
  Cursor breakage never blanks the Claude view.
- **Tool-name drift** — match edit-tool prefixes, not exact `edit_file_v2`.
- **97 MB read cost** — only `composerData` (0.5 MB) on the hot path; bubble scans
  are per-session, prefix-indexed, cached. Never a full-table scan. Always
  `mode=ro&immutable=1`.
- **Privacy** — the DB holds prompt/response text. Read **only** ids, timestamps,
  `repoPath`, branch names, `toolFormerData.name`, and the single path string.
  **Never** `text`/`richText`/`context`/`conversationMap`/`result`/`contents`/
  `aiService.*`. Extend `test_footprint_never_leaks_*` to the Cursor path.

---

## Deliberately not building

**The Worktrees and Work Log tool-splits** — not a compromise, but because they'd
force Orrery to print a tool attribution that git and Cursor can't support, and
the whole worth of this app is that it doesn't lie about state. The real need —
*see per-tool activity* — lives entirely in Sessions, where the data is true.
