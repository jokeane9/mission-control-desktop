# Auto-populate: P3 build plan — GitHub sync

Plan for [#15](https://github.com/jokeane9/mission-control-desktop/issues/15)
phase 3. Adds GitHub as a **discovery + facts source**: list the repos you own
(including ones not cloned on this machine), pull their metadata, and fetch each
one's `CLAUDE.md`/`AGENTS.md`/`.mission-control.json`. This is the first phase
that touches the network, so the privacy design is load-bearing, not an
afterthought.

Builds on the P1 [resolver](autopopulate-resolver.md) — GitHub is the
lowest-priority source and its repos join discovery by identity (git remote).

---

## The one architectural decision: the sync/cache boundary

**`generate.py` and `resolve.py` never touch the network or the token.** All
authenticated GitHub work lives in a new `github_sync.py`, invoked by `app.py`'s
bridge on an explicit **Sync** action. It writes a local cache file; the
resolver reads that cache like any other offline source.

```
app.py  ──Sync──▶  github_sync.py  ──(token, network)──▶  GitHub API
                          │
                          ▼
                 github_cache.json  (data dir, gitignored)
                          │
      generate.py / resolve.py  ──(stdlib read)──▶  github() source
```

Why this matters:
- **The dashboard stays offline-first.** Every 15-min regen reads the cache;
  it never blocks on the network or a rate limit. Sync is deliberate and manual.
- **`generate.py` stays stdlib-only.** Token handling, keychain, and any HTTP
  dependency live only in `github_sync.py` (the app side, which already has deps).
- **The token never enters config or the render path.** It goes keychain →
  `github_sync.py` → discarded. The cache holds data, never the token.

This mirrors the existing viz model: a tool runs out-of-band and writes an
artifact; the renderer just reads it.

---

## Auth

**Ship PAT-first; add device flow as a follow-up.**

- **P3.1a — fine-grained PAT** (no external setup, fully buildable now): user
  pastes a token scoped to **Metadata: read** + **Contents: read**. Stored in
  the **OS keychain** (macOS Keychain / Windows Credential Manager via the
  `keyring` dep — app-side only), never in `baseline.json`.
- **P3.1b — device flow** (nicer UX, later): needs a registered "Mission
  Control" GitHub OAuth App and its (public, non-secret) client id. Standard
  desktop flow: request device code → show the user a code + open the verify
  URL → poll for the token. Classic `repo`/`read:org` scope is broader than a
  fine-grained PAT — note the trade-off.

Recommend starting with PAT: zero external registration, minimal scope, works
today. Device flow is a UX upgrade, not a prerequisite.

---

## What syncs, and the cache

On Sync, `github_sync.py` (authenticated, ~5000 req/hr):
1. **List repos** — paginated `/user/repos` (respecting `github` config filters:
   owners, include-private, topic match, exclude patterns).
2. **Per repo, metadata** — name, description, homepage, topics, language,
   default branch, `private`, `clone_url`, `pushed_at`.
3. **Per repo, the block** — fetch `.mission-control.json` → `CLAUDE.md` /
   `AGENTS.md` via the Contents API (so an uncloned repo can still describe its
   own card). One conditional request per repo; skip on 404.

Written to `github_cache.json` (data dir, gitignored): `{ synced_at, repos: [
{identity, remote, name, description, homepage, topics, language, default_branch,
private, pushed_at, block: {…}} ] }`. Bounded + cached; a stale-but-present cache
still renders. Handle pagination, partial failures (one repo's fetch failing
doesn't sink the sync), and rate-limit headers.

---

## Wiring into discovery + the resolver

- **`github(repo, cache)` source** (in `resolve.py`, stdlib): looks the repo up
  in the cache by identity and returns `{thesis: description, prod: homepage,
  tags: topics, …}` plus the fetched block's fields. Lowest priority — every
  local source still wins.
- **Discovery** gains the cache's repos (per the resolver doc's union):
  deduped by identity = normalized git remote URL. A cached repo that matches a
  locally-scanned repo (same remote) **merges** — local git chips + GitHub-filled
  gaps, one card. A cached repo with no local clone becomes an **uncloned card**.
- **Uncloned repos** (`path=None`): the render path must tolerate no local git.
  `collect()` is skipped for a `GIT_UNAVAILABLE` sentinel; the card shows GitHub
  metadata, a "not cloned locally" note, and (later) a clone affordance. This is
  the one real render change — `rows_html`/cards already use `.get`, but
  `collect()` and the git-chip path assume a local dir.

---

## Config

Token lives in the keychain; `baseline.json` only carries non-secret prefs:

```jsonc
{ "github": { "enabled": true, "include_private": true,
              "owners": ["jokeane9"], "match_topics": [], "exclude": [] } }
```

`github_cache.json` is gitignored (it holds repo descriptions + fetched docs —
treat it as sensitive, same as `baseline.json`).

---

## Privacy (non-negotiable — this is where the local-first promise is tested)

- **Local scan stays the default and stays 100% offline.** GitHub is strictly
  additive and off unless connected.
- **Explicit connect with disclosure** at the moment of connect: "This sends
  authenticated requests to GitHub and downloads repo metadata + your agent docs
  to a local cache." No silent network.
- **Token in the OS keychain only.** Never in `baseline.json`, never in the
  cache, never logged.
- **Disconnect** clears the keychain entry *and* deletes `github_cache.json` —
  the GitHub cards vanish, back to local-only.

---

## UI / bridge (pywebview only, like the editor)

New `Api` methods, gated on the bridge: `github_status()`, `github_connect(token)`
(PAT) / `github_begin_device()` + `github_poll_device()` (later), `github_sync()`,
`github_disconnect()`. A "Connect GitHub" affordance + a Sync button with
last-synced status; uncloned cards get the "not cloned" treatment. All new UI is
`editonly` (hidden without the bridge).

---

## Phasing

- **P3.1 — auth**: PAT connect/disconnect + keychain + `github_status()`. No data
  yet. (P3.1b device flow later.)
- **P3.2 — sync + source**: `github_sync.py` (list + metadata + blocks → cache),
  the `github()` source, discovery union + dedup, uncloned-repo rendering.
- **P3.3 — UI polish**: connect/sync/disconnect controls, uncloned card
  treatment + clone affordance, sync status.

---

## Open questions

- **Auth first cut**: PAT (recommended) vs registering the OAuth App for device
  flow up front.
- **`keyring` dependency** on the app side — acceptable (app.py already has
  deps), but confirm it packages cleanly under PyInstaller on both platforms.
- **Sync trigger**: manual-only (recommended for v1) vs an optional periodic
  background sync.
- **Scale**: users with hundreds of repos — filters + pagination caps; do we
  fetch the block for every repo or only ones without a local clone?
- **Uncloned "clone" action**: shell out to `git clone`? Out of scope for P3.2;
  the card can just link to the repo initially.

## Non-goals

- Writing to GitHub (issues, commits) — read-only, always.
- Making GitHub mandatory — local scan is always a complete path on its own.
- Putting the token anywhere but the keychain.

## Verify criterion (the demo that means "done")

1. Connect with a fine-grained PAT → **Sync** → repos you own appear as cards,
   uncloned ones marked "not cloned" and populated from GitHub metadata + their
   fetched `CLAUDE.md`.
2. A repo cloned locally *and* on GitHub shows git chips **and** GitHub-filled
   gaps — one card, not two (deduped by remote).
3. **Disconnect** → token gone from keychain, cache deleted, GitHub cards vanish,
   dashboard back to local-only and fully offline.
