# Auto-populate: the resolver (P1)

Design draft for [#15](https://github.com/jokeane9/mission-control-desktop/issues/15),
phase 1. How the sources from [autopopulate-schema.md](autopopulate-schema.md)
combine into one card. The resolver is a new layer **in front of** today's
renderer — `collect()` (git) and `rows_html()` (facts) don't change; they just
receive a resolved dict.

---

## Shape

Every source is a pure function `repo → { field: value }` (partial — it only
returns what it knows). The resolver walks the sources in priority order, takes
the first non-empty value per field, and records where it came from.

## The sources (highest priority first)

```
overrides(repo)        # baseline.json entry matched to this repo — always wins
structured_block(repo) # .mission-control.yml | CLAUDE.md/AGENTS.md frontmatter
repo_metadata(repo)    # package.json, pyproject, git remote
heuristics(repo)       # first paragraph → thesis, "## Stack" → stack, first URL → prod
github(repo)           # description / homepage / topics / language  (opt-in)
```

The first four are **offline**. `github()` is the only networked source and is
skipped entirely unless GitHub is connected — the local-first default holds.

## Core resolve

```python
def resolve(repo, sources, keys):
    """sources are ordered high→low. First non-empty value per field wins."""
    facts, provenance = {}, {}
    for key in keys:
        for src in sources:
            val = src.values.get(key)
            if val not in (None, "", [], {}):      # empty == absent → fall through
                facts[key] = val
                provenance[key] = src.name          # 'overrides' | 'block' | 'metadata' | ...
                break
    # computed fallbacks for anything still missing
    facts.setdefault("name", repo.default_name)     # dir name, else remote name
    facts["arch"] = facts.get("arch") or first_existing(
        repo.path, ["ARCHITECTURE.md", "CLAUDE.md", "README.md"])
    provenance.setdefault("name", "computed")
    return facts, provenance
```

- The "empty == absent" test is what makes the schema's *"omitted → fall through"*
  rule work: a source carrying `""` for a field doesn't block a lower source.
- `provenance[key]` is what drives the **auto vs overridden** badge in the UI.

## Building the source list per repo

```python
def sources_for(repo, cfg, gh):
    srcs = [
        Source("overrides", overrides(repo, cfg)),
        Source("block",     structured_block(repo)),   # dedicated file, then frontmatter
        Source("metadata",  repo_metadata(repo)),
        Source("heuristic", heuristics(repo)),
    ]
    if gh and gh.connected:
        srcs.append(Source("github", github(repo, gh)))
    return srcs                                          # already high→low
```

Each source returns `{}` when it has nothing (missing file, no remote, not
connected) and **never raises** — a broken source just contributes nothing.

## Discovery: which repos exist

The card list is the **union** of three discovery sources, deduped by identity:

```python
def discover(cfg, gh):
    repos = {}
    # 1. local scan — walk configured roots for .git dirs (offline default)
    for root in cfg.get("roots", []):
        for path in find_git_dirs(expanduser(root)):
            repos[identity(path=path)] = Repo(path=path)
    # 2. explicit baseline.json entries — may point outside the roots
    for p in cfg.get("projects", []):
        repos.setdefault(identity(path=expanduser(p["path"])), Repo(path=...))
    # 3. GitHub repos — opt-in; may be uncloned (path=None)
    if gh and gh.connected:
        for r in gh.list_repos():
            repos.setdefault(identity(remote=r.clone_url), Repo(remote=r.clone_url, gh=r))
    # drop anything a resolved block marks hidden
    return [r for r in repos.values() if not is_hidden(r, cfg, gh)]
```

**Identity** = normalized local path if present, else normalized git remote URL,
else name. This is the key detail: it's what lets a `baseline.json` override
attach to a *scanned* repo (same path) or a *GitHub* repo (same remote) instead
of showing up as a duplicate.

## Plugging into `main()`

```
today:  for p in cfg["projects"]:
            g = collect(expanduser(p["path"]));  render(p, g)

P1:     for repo in discover(cfg, gh):
            facts, prov = resolve(repo, sources_for(repo, cfg, gh), PROJECT_KEYS)
            g = collect(repo.path) if repo.path else GIT_UNAVAILABLE
            render(facts, g, prov)          # same renderer + a provenance badge
```

`collect()` and `rows_html()` are untouched. The new code is `discover()` +
`resolve()` + the five readers. `baseline.json`'s `projects` become just the
`overrides` source (plus a discovery hint) — no longer the source of truth.

## Edge cases the sketch already handles

- **Uncloned GitHub repo** (`path=None`): no git chips, but facts still populate
  from `github()` / a block fetched over the API. Card shows "not cloned locally."
- **Override with no matching repo**: still rendered — `baseline.json` is itself a
  discovery source, so today's behaviour is preserved.
- **Conflicting sources** (block says X, GitHub says Y): higher wins → block;
  `provenance='block'`.
- **`hidden: true`** from any source → dropped in `discover()`.
- **A source throws** (bad YAML, network blip): caught → contributes `{}` → other
  sources still resolve. One bad repo never breaks the whole board.

## Deliberately deferred (not P1)

- **`tags`**: P1 treats it as first-wins scalar like everything else; union-merge
  across sources is a later refinement.
- **Conflict UI** when an auto value drifts under a manual override: P1 just lets
  the override win silently; surfacing the drift comes later.
- **Refresh cadence**: P1 resolves on each regen (same tick as git); smarter
  per-source caching later.
