#!/usr/bin/env python3
"""GitHub sync (P3.2, app-side). With the keychain token, list the user's repos,
pull metadata + fetch each repo's structured block / agent docs, and write
github_cache.json in the data dir. Network + token stay here; generate.py and
resolve.py only read the cache — the sync/cache boundary from the plan.

stdlib only (urllib); imported by app.py, invoked on an explicit Sync."""
import base64, json, os, time, urllib.parse, urllib.request

import generate      # per-user data dir (generate.DATA), load_config
import github_auth   # keychain token
import resolve       # normalize_remote, block parsers (shared with the resolver)

API = "https://api.github.com"
_MAX_PAGES = 10                       # cap at 1000 repos
# Mirrors resolve.BLOCK_JSON/BLOCK_YAML order — new name first, legacy accepted.
# One request per name, so keep the list to the spellings actually in the wild.
_BLOCK_FILES = (".orrery.json", ".orrery.yml",
                ".mission-control.json", ".mission-control.yml",
                "CLAUDE.md", "AGENTS.md")


def cache_path():
    return os.path.join(generate.DATA, "github_cache.json")


def _get(path_or_url, token, params=None):
    url = path_or_url if path_or_url.startswith("http") else API + path_or_url
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Mission-Control"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _list_repos(token, gh_cfg):
    repos, page = [], 1
    while page <= _MAX_PAGES:
        data = _get("/user/repos", token,
                    {"per_page": 100, "page": page, "sort": "pushed"})
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    if not gh_cfg.get("include_private", True):
        repos = [r for r in repos if not r.get("private")]
    owners = [o.lower() for o in gh_cfg.get("owners", [])]
    if owners:
        repos = [r for r in repos
                 if r.get("owner", {}).get("login", "").lower() in owners]
    exclude = set(gh_cfg.get("exclude", []))
    if exclude:
        repos = [r for r in repos if r.get("name") not in exclude]
    return repos


def _fetch_block(token, full_name, ref):
    """Fetch the first present block file and parse it (reusing resolve's
    parsers). One request per candidate; 404s are skipped. {} if none."""
    for fn in _BLOCK_FILES:
        try:
            data = _get(f"/repos/{full_name}/contents/{fn}", token, {"ref": ref})
            content = base64.b64decode(data.get("content", "")).decode("utf-8", "ignore")
        except Exception:
            continue
        if fn.endswith(".json"):
            try:
                return json.loads(content)
            except Exception:
                continue
        elif fn.endswith((".yml", ".yaml")):
            return resolve.parse_mini_yaml(content)
        else:  # CLAUDE.md / AGENTS.md frontmatter
            for key in resolve.BLOCK_KEYS:
                sub = resolve._frontmatter_block(content, key)
                if sub:
                    return resolve.parse_mini_yaml(sub)
    return {}


def sync():
    """List → per-repo metadata + block → write the cache. {ok, count} / error."""
    token = github_auth.get_token()
    if not token:
        return {"ok": False, "error": "Not connected to GitHub."}
    gh_cfg = (generate.load_config().get("github") or {})
    try:
        repos = _list_repos(token, gh_cfg)
    except Exception as e:
        return {"ok": False, "error": f"GitHub request failed: {e}"}

    out = []
    for r in repos:
        full = r.get("full_name")
        try:
            block = _fetch_block(token, full, r.get("default_branch") or "") if full else {}
        except Exception:
            block = {}                                 # one repo failing never sinks the sync
        out.append({
            "identity": resolve.normalize_remote(r.get("clone_url", "")),
            "remote": r.get("clone_url", ""),
            "name": r.get("name"),
            "full_name": full,
            "description": r.get("description") or "",
            "homepage": r.get("homepage") or "",
            "topics": r.get("topics") or [],
            "language": r.get("language") or "",
            "default_branch": r.get("default_branch") or "",
            "private": bool(r.get("private")),
            "html_url": r.get("html_url") or "",
            "pushed_at": r.get("pushed_at") or "",
            "block": block,
        })

    cache = {"synced_at": int(time.time()), "repos": out}
    tmp = cache_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.replace(tmp, cache_path())
    return {"ok": True, "count": len(out)}


def clear_cache():
    try:
        os.remove(cache_path())
    except Exception:
        pass
