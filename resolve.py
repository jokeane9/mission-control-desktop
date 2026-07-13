#!/usr/bin/env python3
"""Auto-populate resolver — offline, stdlib only. Discovers repos and resolves
each project's card facts from layered sources, highest priority first:

    overrides (baseline.json)  >  block  >  repo metadata  >  heuristics  >  github

The github source (P3.2) reads a cache written out-of-band by github_sync.py — no
network or token here; this module stays offline + stdlib. GitHub repos not cloned
locally appear as cards with path=None. LLM extraction (P4) is still absent.
See project-management/autopopulate-*.md.
"""
import json, os, re, subprocess

# Canonical card fields the renderer consumes. `path` is repo identity, handled
# separately; everything below is what resolve() fills in.
PROJECT_KEYS = ["name", "thesis", "tier", "prod", "prod_note", "stack", "dev",
                "prod_env", "arch", "email", "focus", "viz_app", "viz_pipeline",
                "hidden", "tags"]

_IGNORE_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv",
                "venv", ".next", "target", "vendor", ".cache"}
_URL_RE = re.compile(r"https?://[^\s)\"'>]+")


# --------------------------------------------------------------------------- #
# YAML micro-parser — only the shapes the schema uses (flat scalars, a `tags`
# list, one nested map like `viz`). Anything fancier is ignored, not errored.
# --------------------------------------------------------------------------- #
def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        return v[1:-1]
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def parse_mini_yaml(text):
    """Parse the schema's limited YAML into a dict. Best-effort; never raises."""
    data, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#") or _indent(raw) > 0:
            continue
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        key, val = key.strip(), val.strip()
        if val and not val.startswith("["):
            data[key] = _scalar(val)
        elif val.startswith("["):
            inner = val.strip("[]")
            data[key] = [_scalar(x) for x in inner.split(",") if x.strip()]
        else:
            # empty value → gather the indented block that follows
            block = []
            while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) > 0):
                if lines[i].strip():
                    block.append(lines[i])
                i += 1
            if block and block[0].lstrip().startswith("- "):
                data[key] = [_scalar(b.lstrip()[2:]) for b in block
                             if b.lstrip().startswith("- ")]
            else:
                sub = {}
                for b in block:
                    if ":" in b:
                        k2, _, v2 = b.strip().partition(":")
                        if v2.strip():
                            sub[k2.strip()] = _scalar(v2.strip())
                data[key] = sub
    return data


def _frontmatter_block(text, key):
    """Return the dedented sub-block under `key:` inside a leading --- frontmatter
    fence, so a nested `viz:` sits one level down and the mini-parser handles it."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm = text[3:end].splitlines()
    for idx, line in enumerate(fm):
        if line.strip().startswith(key + ":") and not line.split(":", 1)[1].strip():
            base = _indent(fm[idx + 1]) if idx + 1 < len(fm) else 0
            out = []
            for line2 in fm[idx + 1:]:
                if line2.strip() and _indent(line2) < base:
                    break
                out.append(line2[base:] if len(line2) >= base else line2)
            return "\n".join(out)
    return None


# --------------------------------------------------------------------------- #
# Source readers — each returns a partial {field: value}; {} on anything missing
# or malformed. None ever raises: a broken repo contributes nothing.
# --------------------------------------------------------------------------- #
def _normalize(d):
    """Map schema aliases onto canonical keys the renderer uses."""
    out = dict(d)
    viz = out.pop("viz", None)
    if isinstance(viz, dict):
        if viz.get("app"):
            out.setdefault("viz_app", viz["app"])
        if viz.get("pipeline"):
            out.setdefault("viz_pipeline", viz["pipeline"])
    if "accounts" in out:
        out.setdefault("email", out.pop("accounts"))
    return {k: v for k, v in out.items() if k in PROJECT_KEYS}


def read_block(path):
    """Structured block: .mission-control.json → .yml/.yaml → CLAUDE/AGENTS.md
    frontmatter. First one found wins."""
    try:
        j = os.path.join(path, ".mission-control.json")
        if os.path.isfile(j):
            return _normalize(json.load(open(j, encoding="utf-8")))
        for name in (".mission-control.yml", ".mission-control.yaml"):
            f = os.path.join(path, name)
            if os.path.isfile(f):
                return _normalize(parse_mini_yaml(open(f, encoding="utf-8").read()))
        for name in ("CLAUDE.md", "AGENTS.md"):
            f = os.path.join(path, name)
            if os.path.isfile(f):
                sub = _frontmatter_block(open(f, encoding="utf-8").read(),
                                         "mission-control")
                if sub:
                    return _normalize(parse_mini_yaml(sub))
    except Exception:
        pass
    return {}


def repo_metadata(path):
    """package.json / pyproject / git remote homepage."""
    out = {}
    try:
        pj = os.path.join(path, "package.json")
        if os.path.isfile(pj):
            d = json.load(open(pj, encoding="utf-8"))
            if d.get("description"):
                out["thesis"] = d["description"]
            if d.get("homepage"):
                out["prod"] = d["homepage"]
    except Exception:
        pass
    try:
        r = subprocess.run(["git", "-C", path, "config", "--get", "remote.origin.url"],
                           capture_output=True, text=True, timeout=5)
        url = r.stdout.strip()
        if url and "prod" not in out and "github.com" not in url and url.startswith("http"):
            out["prod"] = url
    except Exception:
        pass
    return out


def heuristics(path):
    """Conservative prose parse of CLAUDE.md / README.md. When unsure, stay silent
    — a wrong guess is worse than an empty field."""
    if not path:
        return {}
    out = {}
    for name in ("CLAUDE.md", "README.md"):
        f = os.path.join(path, name)
        if not os.path.isfile(f):
            continue
        try:
            text = open(f, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if text.startswith("---"):                      # strip frontmatter
            end = text.find("\n---", 3)
            if end != -1:
                text = text[end + 4:]
        lines = text.splitlines()
        # thesis = first prose paragraph (not a heading, list, or blank)
        for ln in lines:
            s = ln.strip()
            if s and not s.startswith(("#", "-", "*", ">", "|", "`")):
                out["thesis"] = s[:140]
                break
        # stack = first non-empty line under a Stack/Tech heading
        for idx, ln in enumerate(lines):
            if re.match(r"#+\s+(stack|tech)", ln.strip(), re.I):
                for nxt in lines[idx + 1:]:
                    if nxt.strip():
                        out["stack"] = nxt.strip().lstrip("-* ").strip()[:120]
                        break
                break
        m = _URL_RE.search(text)                        # prod = first url
        if m and "github.com" not in m.group(0):
            out.setdefault("prod", m.group(0))
        break                                           # CLAUDE.md wins over README
    return out


def overrides(repo, cfg):
    """The matching baseline.json entry — the manual override, always highest.
    Matched by local path (baseline entries are path-based). Uncloned GitHub
    repos have no path and so no override in P3.2."""
    rpath = repo.get("path")
    if not rpath:
        return {}
    rp = os.path.realpath(rpath)
    for p in cfg.get("projects", []):
        pp = p.get("path", "")
        if pp and os.path.realpath(os.path.expanduser(pp)) == rp:
            return {k: v for k, v in p.items() if k in PROJECT_KEYS}
    return {}


def github(repo, cache):
    """Facts from the synced GitHub cache (P3.2), matched by identity. Lowest
    priority — every local source wins. Within this source the fetched block
    beats GitHub metadata, so an uncloned repo's own block still leads."""
    if not cache:
        return {}
    rid = identity(repo)
    entry = next((g for g in cache.get("repos", []) if g.get("identity") == rid), None)
    if not entry:
        return {}
    out = {}
    if entry.get("description"):
        out["thesis"] = entry["description"]
    if entry.get("homepage"):
        out["prod"] = entry["homepage"]
    if entry.get("topics"):
        out["tags"] = entry["topics"]
    out.update(_normalize(entry.get("block") or {}))
    return {k: v for k, v in out.items()
            if k in PROJECT_KEYS and v not in (None, "", [], {})}


def load_github_cache(path):
    """Read github_cache.json (written out-of-band by github_sync.py). {} if absent."""
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# Identity + discovery + resolve
# --------------------------------------------------------------------------- #
def _git_remote(path):
    try:
        r = subprocess.run(["git", "-C", path, "config", "--get", "remote.origin.url"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""


def normalize_remote(url):
    """Canonical repo id `host/owner/repo` — lowercased, no scheme/user/.git — so
    a local clone's remote matches a GitHub clone_url for dedup."""
    if not url:
        return ""
    u = url.strip()
    u = re.sub(r"^git@([^:/]+):", r"\1/", u)   # scp-style ssh → host/path
    u = re.sub(r"^\w+://", "", u)              # strip scheme
    u = re.sub(r"^[^@/]+@", "", u)             # strip user@ (ssh:// form)
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u.lower()


def identity(repo):
    """Remote (normalized) if the repo has one — bridges local clone ↔ GitHub —
    else the real local path, else the name. Repos carry a precomputed `remote`."""
    rem = repo.get("remote")
    if rem:
        return rem
    p = repo.get("path")
    return os.path.realpath(p) if p else (repo.get("name") or "")


def _is_git(path):
    return bool(path) and os.path.isdir(os.path.join(path, ".git"))


def find_git_dirs(root, max_depth=4):
    """Walk `root` for repos, bounded: cap depth, skip heavy/build dirs, and don't
    descend into a repo once found."""
    root = os.path.expanduser(root)
    found = []
    if not os.path.isdir(root):
        return found
    base_depth = root.rstrip(os.sep).count(os.sep)
    for cur, dirs, _files in os.walk(root):
        if cur.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
            continue
        if ".git" in dirs:
            found.append(cur)
            dirs[:] = []                                # don't recurse into a repo
            continue
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
    return found


def discover(cfg, cache=None):
    """Candidate repos = baseline entries + scanned roots (local) ∪ synced GitHub
    repos, deduped by identity (git remote, else path). A GitHub repo already
    cloned locally merges into the local card (the github source fills its gaps);
    the rest render as uncloned (path=None)."""
    seen, local = set(), []

    def add(path):
        repo = {"path": path, "remote": normalize_remote(_git_remote(path))}
        rid = identity(repo)
        if rid and rid not in seen:
            seen.add(rid)
            local.append(repo)

    for p in cfg.get("projects", []):
        if p.get("path"):
            add(os.path.expanduser(p["path"]))
    for r in cfg.get("roots", []):
        for path in find_git_dirs(r):
            add(path)
    result = [r for r in local if _is_git(r["path"])]
    seen = {identity(r) for r in result}
    for g in (cache or {}).get("repos", []):
        rid = g.get("identity") or normalize_remote(g.get("remote", ""))
        if rid and rid not in seen:
            seen.add(rid)
            result.append({"path": None, "remote": rid, "gh": g})
    return result


def resolve(repo, cfg, auto=True, cache=None):
    """Return (facts, provenance). Per field: first non-empty source wins.

    `auto` (roots set) gates the local file sources; `cache` (GitHub synced) gates
    the github source. An uncloned repo has path=None — only overrides + github
    apply. With neither opted in, it's baseline overrides only, as before."""
    path = repo.get("path")
    sources = [("overrides", overrides(repo, cfg))]
    if auto and path:
        sources += [
            ("block", read_block(path)),
            ("metadata", repo_metadata(path)),
            ("heuristic", heuristics(path)),
        ]
    if cache:
        sources.append(("github", github(repo, cache)))
    facts, prov = {}, {}
    for key in PROJECT_KEYS:
        for name, values in sources:
            v = values.get(key)
            if v not in (None, "", [], {}):
                facts[key], prov[key] = v, name
                break
    gh = repo.get("gh") or {}
    facts.setdefault("name", (os.path.basename(path.rstrip(os.sep)) if path
                              else gh.get("name")) or "repo")
    prov.setdefault("name", "computed")
    facts["arch"] = facts.get("arch") or (
        _first_existing(path, ["ARCHITECTURE.md", "CLAUDE.md", "README.md"]) if path else "")
    facts["path"] = path
    facts["github_url"] = gh.get("html_url", "")   # uncloned-repo link
    facts["clone_url"] = gh.get("remote", "")      # uncloned-repo Clone action
    return facts, prov


def _first_existing(path, names):
    for n in names:
        if os.path.isfile(os.path.join(path, n)):
            return n
    return ""
