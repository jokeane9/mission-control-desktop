# Auto-populate: the `orrery` structured block (P1)

Design draft for [#15](https://github.com/jokeane9/orrery/issues/15),
phase 1. The **reliable** path for a repo to describe its own card — explicit,
exact, versioned next to the code. Heuristic parsing of prose is a bonus on top;
this block is what a repo owner writes when they want the card *right*.

Adding the block is always optional. A repo with no block still appears (populated
from metadata/heuristics); the block just overrides those guesses.

---

## Where it can live (two carriers)

A repo may use either. If both are present, the dedicated file wins (it's the more
explicit choice), then the CLAUDE.md/AGENTS.md frontmatter.

**1. A dedicated file at repo root** — `.orrery.yml` (or `.json`).
Fields are top-level:

```yaml
# .orrery.yml
thesis: "Velocio Visibility Index — multi-brand SaaS, live"
tier: major
prod: https://app.vizidex.app
stack: "Remix + Tailwind + shadcn · Supabase"
arch: DEPLOY-ENV.md
```

**2. A `orrery:` key in the YAML frontmatter of `CLAUDE.md` / `AGENTS.md`**
— co-located with the agent doc, namespaced so it can't collide with anything else
the frontmatter carries:

```markdown
---
orrery:
  thesis: "Shopify competitor-intel app pivoting to a promo control plane"
  tier: major
  prod: https://shelfplugin.com
  prod_note: "AWS ~$75/mo · crawls off"
  stack: "Remix + Polaris · Python crawler on ECS · Postgres"
  focus: "Gate-0 pitch test"
  viz:
    app: "."
    pipeline: "crawl"
---

# Shelf — Claude Context
...
```

Everything a block omits falls through to the lower-priority sources
(repo metadata → heuristic parse → GitHub). See "Resolution order" below.

---

## Field reference

All fields optional. Types are strings unless noted.

| Field | Type | Default when omitted | Notes |
|---|---|---|---|
| `name` | string | repo dir name, else git remote name | Display name + sidebar label. |
| `thesis` | string | first paragraph of CLAUDE.md/README (heuristic) | One line: what this project is. |
| `tier` | enum-ish | `minor` | Suggested: `major` · `minor` · `tools` · `archived`. Free string; drives grouping/accent. |
| `prod` | URL | git remote homepage / GitHub `homepage` | Production URL. Must be `http(s)://`. |
| `prod_note` | string | — | Hosting · rough cost, e.g. "AWS ~$75/mo". |
| `stack` | string | `package.json`/`pyproject` deps summary (heuristic) | Tech stack in a phrase. |
| `dev` | string | — | How to run it locally. |
| `prod_env` | string | — | How production is deployed. |
| `arch` | repo-relative path | first of `ARCHITECTURE.md`, `CLAUDE.md`, `README.md` | Doc whose `##` headings become the card's outline. |
| `email` / `accounts` | string | — | Accounts/domains/logins note. `accounts` is the preferred alias; `email` accepted for back-compat with `baseline.json`. |
| `focus` | string | — | The one thing being pushed on now. |
| `tags` | string[] | `[]` | Optional labels. |
| `viz` | object | auto-detect (P2) | `{ app?: <repo-relative path>, pipeline?: <repo-relative path> }`. Drives the architecture/pipeline map tabs. Omit → P2 auto-detects. |
| `hidden` | boolean | `false` | `true` excludes this repo from the dashboard even if discovered. |
| `version` | integer | `1` | Block schema version, for forward-compat. |

**Forward-compat rule:** unknown keys are ignored (warn in a debug log, never
error), so newer blocks stay readable by older Orrery builds.

---

## Resolution order (how a field's value is chosen)

Highest wins; each field resolves independently:

1. **Manual override** — `baseline.json` / the in-app editor. Always wins.
2. **This structured block** — dedicated file, then CLAUDE.md/AGENTS.md frontmatter.
3. **Repo metadata** — `package.json` name/description, git remote, `pyproject.toml`.
4. **Heuristic parse** — first paragraph → thesis, `## Stack` section → stack, first URL → prod.
5. **GitHub metadata** (if connected) — description, homepage, topics, language.

So the block sits just under manual overrides: authoritative for anything it sets,
transparent for anything it leaves out. Every card field is tagged `auto` vs
`overridden` in the UI so the source is visible.

---

## Examples

**Minimal** — name + thesis, everything else auto-derived:

```yaml
# .orrery.yml
thesis: "AI WooCommerce diagnostics — WP plugin → Claude root-cause analysis"
tier: major
```

**Opt out** — a repo you never want on the board:

```yaml
# .orrery.yml
hidden: true
```

**Full, via CLAUDE.md frontmatter** — see the Shelf example above.

---

## Validation (JSON Schema, draft-07)

Ships with the app and can run in a repo's own CI to catch typos before commit:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "orrery project block",
  "type": "object",
  "additionalProperties": true,
  "properties": {
    "version":   { "type": "integer", "minimum": 1 },
    "name":      { "type": "string" },
    "thesis":    { "type": "string" },
    "tier":      { "type": "string" },
    "prod":      { "type": "string", "format": "uri", "pattern": "^https?://" },
    "prod_note": { "type": "string" },
    "stack":     { "type": "string" },
    "dev":       { "type": "string" },
    "prod_env":  { "type": "string" },
    "arch":      { "type": "string" },
    "accounts":  { "type": "string" },
    "email":     { "type": "string" },
    "focus":     { "type": "string" },
    "tags":      { "type": "array", "items": { "type": "string" } },
    "hidden":    { "type": "boolean" },
    "viz": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "app":      { "type": "string" },
        "pipeline": { "type": "string" }
      }
    }
  }
}
```

`additionalProperties: true` at the top level is deliberate — it's how the
forward-compat rule (ignore unknown keys) is enforced.

---

## Notes for implementation

- The block maps 1:1 onto today's `baseline.json` project shape, so P1 can reuse
  the existing `PROJECT_FIELDS` and render path unchanged — discovery just becomes
  another source feeding the same card.
- Reading a dedicated `.orrery.yml` and reading a doc's `##` outline are
  both already-solved shapes (`load_config`, `arch_outline`), so P1 is mostly a
  new resolver in front of the existing renderer, not new UI.
- YAML frontmatter parsing is the one new dependency; keep it minimal (a tiny
  vendored parser or stdlib-only subset) to preserve the "stdlib, no deps" stance
  of `generate.py`.
