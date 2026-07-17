# Orrery — Product

The canonical product doc. What this is, who it's for, what it deliberately is
*not*, and how we'll know it's working. Engineering/process lives in
[`project-management/`](project-management/); this file is the *product* north
star. If a product decision isn't captured here, it's not decided.

---

## One-liner

**One dark window that shows the live state of every git project you're working
on — and the human context no tool can derive.**

## What it is

A local, single-window desktop dashboard (macOS + Windows) that scans your git
repos and renders each one's live state — branch, uncommitted / unmerged /
unpushed counts — next to the facts a tool can't infer: what the project is,
where prod lives, what you're pushing on. On top of the project cards it carries
a few whole-workspace views: a **Skills** catalog, a **Work Log** (commits +
token usage over time), an aggregated **Roadmap**, a **Worktrees** cleanup view,
and a **PM** scratchpad.

Everything is read live from disk on each render; the human facts live in one
editable JSON file. Nothing leaves the machine.

## Who it's for

The developer running many repos at once — side projects, client work, a
monorepo split into pieces — who loses the thread on "what state is everything
in, and what was I doing here?" Built first for a solo multi-project developer;
useful to anyone whose work is spread across more repos than they can hold in
their head.

## The problem

Context is scattered. `git status` is per-repo and per-terminal. The "why" of a
project (prod URL, stack, the one thing you're mid-push on) lives in your head
or a stale README. Switching projects means rebuilding that context every time.
Orrery makes the whole workspace legible at a glance and keeps the
human context attached to each repo.

## Principles (the non-negotiables)

1. **Local-first, no accounts, no telemetry, no server.** Nothing leaves the
   machine. This is a product promise, not just an architecture note — features
   that require a backend or an account are out of scope by default.
2. **One app, two platforms, one version.** A single codebase builds the macOS
   and Windows apps from the same commit and the same version number. Never
   fork the platforms.
3. **Live from disk, not a database.** The git state is always the real current
   state, re-read on each render. No sync layer to drift.
4. **The engine stays stdlib-only and offline.** `generate.py` + `resolve.py`
   have no dependencies and never touch the network. Anything that needs the
   network (GitHub) is an opt-in, isolated module reading a cache file.
5. **Human facts are cheap to edit and they survive.** One JSON file, an in-app
   editor, provenance badges on auto-derived fields.
6. **It matches its own aesthetic.** GitHub-dark, SF Mono, thin muted marks.
   Calm, dense, not a toy.

## What it is NOT (non-goals)

- **Not a team/cloud product.** No shared state, no multi-user, no cross-device
  sync. (Sync would require the accounts + server we've ruled out. If that
  changes, it's a deliberate strategy pivot documented here first — not a
  feature that sneaks in.)
- **Not a git client.** It surfaces state and context; it doesn't stage,
  commit, rebase, or resolve conflicts. (Cloning an uncloned GitHub repo is the
  one write action, and it's explicit.)
- **Not a CI/observability dashboard.** No build logs, no uptime, no metrics
  scraping.
- **Not a full project-management tool.** The PM tab is a personal scratchpad
  and the Roadmap view aggregates your own `ROADMAP.md` files — it's not Jira.

## Success — how we'll know it's working

North star: **it's the first window you open and the one you keep open** — the
place you actually go to answer "what's the state of everything, and what was I
doing?"

Leading signals (a free, local, no-telemetry app, so these are observed, not
instrumented):

- **Install → keep.** People install it and it stays in the Dock / on launch,
  not a one-look-and-quit.
- **Cards stay populated.** Auto-populate + the editor mean projects carry real
  thesis / stack / focus, not empty shells.
- **Distribution is frictionless.** `brew install` / a signed installer that
  doesn't fight the user (see signing on the roadmap).
- **Organic pickup.** Stars / issues / the launch post landing with developers
  who run many repos.

## Open product questions

Written as the actual question with the current thinking — not decisions, just
the live tensions. Revisit these before any launch push.

### Does it sync across devices? Does it need a login?

**Short answer: no, and that's deliberate — for now.** Orrery is a
standalone local app. It runs as your OS user on one machine, keeps its config
in a local file (plus the optional GitHub token in the OS keychain), and has no
account system because there is no server to log into. Open it on a second
machine and it starts empty.

The question keeps coming up because "my projects, on all my devices" is a
reasonable want. But real sync means a backend + accounts + data leaving the
machine — a direct trade against principle #1 (local-first, no accounts, no
telemetry). So the honest framing is: **sync isn't a missing feature, it's a
different product.** If we ever do it, it's a deliberate strategy pivot
documented here first (e.g. optional end-to-end-encrypted sync, or a
bring-your-own-git-remote model that keeps the no-server promise) — never a
feature that quietly erodes the local-only guarantee. Until then: **standalone,
per-machine, no login.**

### What's the name?

**Decided: Orrery** (v2.0.0). An orrery is a desk instrument that shows every
planet's position at once, in one frame — which is the product in one word, and
matches the aesthetic: a calm, precise instrument rather than a toy.

It replaced "Mission Control", which collided with Apple's window manager. That
collision was never only cosmetic: `open -a "Mission Control"` resolved to
Apple's app, so the most common scripted launch path silently did nothing.
"Orrery" collides with nothing, so the bug goes away by construction.

### Who beyond the solo multi-repo developer?

Teams or a hosted variant are the obvious expansion, but both sit behind the
same local-first wall as sync. Explicitly deferred — revisit only as a
conscious pivot, not creep.

## Where the rest of the truth lives

- [`CLAUDE.md`](CLAUDE.md) — orientation, how it's built, build/run/release.
- [`project-management/`](project-management/) — roadmap, ship rules, known
  issues, architecture, stack decisions, session log.
- [`DISTRIBUTION.md`](DISTRIBUTION.md) — signing, notarization, the $0 launch
  path.
