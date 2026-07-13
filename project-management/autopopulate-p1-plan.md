# Auto-populate: P1 build plan

Build plan for [#15](https://github.com/jokeane9/mission-control-desktop/issues/15)
phase 1 — **local, offline auto-discovery**. Implements the
[schema](autopopulate-schema.md) and [resolver](autopopulate-resolver.md) with
no network. Follows the one-surgical-change-per-step discipline from
[SHIP-RULES](SHIP-RULES.md): each step below lands green on its own.

---

## Scope

**IN (P1)**
- Local repo discovery from configured `roots` (walk for `.git`).
- Four **offline** sources: `overrides` (baseline.json), `structured_block`,
  `repo_metadata`, `heuristics`.
- `resolve()` with per-field provenance + the auto/overridden badge.
- `baseline.json` demotes to `overrides` + a `roots` list. **Zero-break upgrade**:
  an existing baseline with no `roots` renders exactly as today.

**OUT (later phases)** — GitHub sync (P3), LLM extraction (P4), auto-maps (P2),
`tags` union-merge, conflict-drift UI, uncloned-repo cards.

---

## Decision to lock first: the YAML parser

`generate.py` is deliberately **stdlib-only**, and P1 must not break that.

- **`.mission-control.json`** → parsed with stdlib `json`. Fully supported, no dep.
- **`.mission-control.yml` + `CLAUDE.md`/`AGENTS.md` frontmatter** → a **~40-line
  vendored micro-parser** scoped to the schema's shapes only: top-level
  `key: value` scalars, an inline or block `tags:` list, and the one nested `viz:`
  map. Anything fancier (anchors, multi-doc, deep nesting) is ignored with a
  logged warning, and the repo can fall back to `.mission-control.json`.
- **Not** pulling in PyYAML — the schema is small and flat; a full YAML engine is
  overkill and would break the no-deps stance of the shared engine.

Document the supported subset in the schema doc when this lands.

---

## Ordered steps (each independently shippable)

1. **`roots` config.** Add an optional `roots: []` to `baseline.json` (dirs to
   scan). `load_config()` unchanged; sample config gains a commented example.
   *Test:* config with/without `roots` both load.

2. **Discovery.** `find_git_dirs(root)` (bounded walk — skip `node_modules`,
   `.git` internals, cap depth), `identity(path|remote|name)`, and
   `discover(cfg)` = union of local scan + baseline entries, deduped by identity.
   *Test:* same repo via root + baseline → one card.

3. **Source readers** (four isolated functions, each fail-soft → `{}` on error):
   - `overrides(repo, cfg)` — baseline project matched by identity.
   - `read_block(repo)` — `.mission-control.json` → `.yml` → frontmatter (uses the
     micro-parser).
   - `repo_metadata(repo)` — `package.json` (name/description), `pyproject.toml`,
     git remote → homepage guess.
   - `heuristics(repo)` — first paragraph of CLAUDE.md/README → `thesis`;
     `## Stack`/`## Tech` section → `stack`; first `http(s)` URL → `prod`.
   *Test:* each reader against a fixture repo carrying that one source.

4. **`resolve()`.** The precedence walk + provenance + computed fallbacks (`name`,
   `arch` chain), per the resolver doc.
   *Test:* precedence matrix — override > block > metadata > heuristic; empty
   value falls through.

5. **Wire into `main()`.** Replace the `for p in cfg["projects"]` loop with
   `for repo in discover(cfg): facts, prov = resolve(...)`. `collect()` and
   `rows_html()` keep their signatures — `facts` is the same dict shape.
   *Test:* render smoke; an old baseline renders identically (back-compat).

6. **Provenance badge.** A subtle "auto" marker on auto-derived fields (tooltip:
   which source); overridden/manual fields plain. Minimal CSS, no layout change.

7. **Docs + sample.** README note ("point it at a folder"), `baseline.sample.json`
   gains `roots`, schema doc gets the YAML-subset section.

---

## Testing (reuse the existing pattern)

Python unit tests + the render smoke + a fixtures dir of tiny repos:

- Discovery dedupe (root ∪ baseline → one).
- Each reader against its fixture (block / package.json / CLAUDE.md).
- `resolve()` precedence + empty-fallthrough.
- **Back-compat:** today's `baseline.json` (projects only, no `roots`) renders
  byte-identical to current output.
- **Fail-soft:** a repo with malformed `.mission-control.yml` still renders, warns.

All of this runs in the existing `ci.yml` `check` job (stdlib, offline).

---

## Verify criterion (the demo that means "done")

1. Point MC at a folder with 2–3 real repos and **no** baseline entries → cards
   come up **populated** (thesis/stack/prod from metadata + heuristics).
2. Drop a `.mission-control.json` into one repo → its fields win, provenance flips
   to `block`.
3. Add a `baseline.json` override for one field → the override wins, badge shows
   `overridden`.

If those three hold, P1 is done.

---

## Risks / things to watch

- **Perf.** Scanning a big root + reading files per repo on every 15-min regen.
  Mitigate: bounded walk (depth cap, ignore `node_modules`/build dirs), and cache
  each repo's block+metadata by file mtime so an unchanged repo isn't re-read.
- **Heuristic over-reach.** Keep it conservative — a wrong auto-guess is worse
  than an empty field. When unsure, leave it blank rather than fill it wrong.
- **Provenance plumbing.** `resolve()` returns `(facts, provenance)`; the renderer
  needs the second arg threaded through — the one signature change in the render
  path. Keep it a dict, optional, defaulting to "all manual" so nothing else moves.

---

## Files touched

`generate.py` (discovery + readers + resolver + micro-parser; likely a small new
module `resolve.py` imported by `generate.py`), `baseline.sample.json`, `README.md`,
`project-management/autopopulate-schema.md` (subset note), and `tests/` fixtures.
