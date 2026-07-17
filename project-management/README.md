# project-management/

The PM system for Orrery. If a decision isn't written here (or in
`CLAUDE.md` / `DISTRIBUTION.md`), it's lost. Don't read every file at session
start — open the one relevant to what you're doing.

Adapted from the killdate-kit convention, trimmed for a **shipped desktop app**
(no live prod to blue/green — the "deploy" is a GitHub Release + Homebrew bump).

---

## Read every session

| File | What it is |
|---|---|
| `_log.md` | One entry per session — what changed, decisions, RESUME HERE for mid-flight work. Read the last ~80 lines. |
| `ROADMAP.md` | What's next, ordered, with blockers. Full read. |
| `KNOWN-ISSUES.md` | Open issues only. Quick scan. |

## Read on trigger

| File | Read when… |
|---|---|
| `SHIP-RULES.md` | Before cutting a release or making a versioning call. Covers semver axes, the one-surgical-change invariant, and the release checklist. |
| `ARCHITECTURE.md` | Before touching how the layers connect (generate ↔ app ↔ packaging). |
| `STACK.md` | Before any permanent tooling/dependency decision, or to see why an alternative was ruled out. |
| `UX-FLOWS.md` | Before changing any user-facing interaction (navigation, groups/folders, drag, keyboard, editor). The canonical interaction model. |
| `UX-AUDIT.md` | The 2026-07-14 full-app UX review — findings, what shipped in v1.6.0, and the prioritized backlog. Read before picking up a UX task. |

## Also

- `CLAUDE.md` (repo root) — orientation, build/run/release commands. Read first.
- `DISTRIBUTION.md` (repo root) — signing, notarization, stores, $0 launch.
