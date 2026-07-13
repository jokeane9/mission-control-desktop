#!/usr/bin/env python3
"""P3.2 GitHub sync tests — sync() with mocked HTTP writes a well-formed cache,
and generate.main() renders uncloned repos + merges a locally-cloned one. No
network. Stdlib only. Run: python tests/test_github_sync.py"""
import os, sys, json, base64, tempfile, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import generate
import github_auth
import github_sync as GS


def test_sync_writes_cache():
    tmp = tempfile.mkdtemp()
    generate.DATA = tmp
    generate.BASELINE = os.path.join(tmp, "baseline.json")
    json.dump({"github": {}}, open(generate.BASELINE, "w"))

    def fake_get(path_or_url, token, params=None):
        if "/user/repos" in path_or_url:
            if (params or {}).get("page", 1) > 1:
                return []
            return [{"full_name": "o/app", "name": "app",
                     "clone_url": "https://github.com/o/app.git",
                     "description": "an app", "homepage": "https://app.dev",
                     "topics": ["x"], "language": "Python", "default_branch": "main",
                     "private": False, "html_url": "https://github.com/o/app",
                     "pushed_at": "2026-01-01", "owner": {"login": "o"}}]
        if "/contents/.mission-control.json" in path_or_url:
            return {"content": base64.b64encode(json.dumps({"stack": "Go"}).encode()).decode()}
        raise Exception("404")

    orig_get, orig_tok = GS._get, github_auth.get_token
    GS._get = fake_get
    github_auth.get_token = lambda: "tok"
    try:
        r = GS.sync()
        assert r == {"ok": True, "count": 1}, r
        cache = json.load(open(GS.cache_path()))
        e = cache["repos"][0]
        assert e["identity"] == "github.com/o/app"
        assert e["description"] == "an app" and e["block"] == {"stack": "Go"}
        assert "synced_at" in cache
        # not connected → clean error, no crash
        github_auth.get_token = lambda: None
        assert GS.sync()["ok"] is False
    finally:
        GS._get, github_auth.get_token = orig_get, orig_tok


def test_render_uncloned_and_merge():
    tmp = tempfile.mkdtemp()
    code = os.path.join(tmp, "code"); os.makedirs(code)
    # a locally-cloned repo whose remote matches a cache entry
    d = os.path.join(code, "app"); os.makedirs(d)
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "remote", "add", "origin",
                    "https://github.com/o/app.git"], check=True)

    generate.DATA = tmp
    generate.BASELINE = os.path.join(tmp, "baseline.json")
    generate.INDEX = os.path.join(tmp, "index.html")
    json.dump({"roots": [code]}, open(generate.BASELINE, "w"))
    json.dump({"synced_at": 1, "repos": [
        {"identity": "github.com/o/app", "remote": "https://github.com/o/app.git",
         "name": "app", "description": "cloud desc for app", "homepage": "",
         "topics": [], "html_url": "https://github.com/o/app", "block": {}},
        {"identity": "github.com/o/ghost", "remote": "https://github.com/o/ghost.git",
         "name": "ghost", "description": "only on github", "homepage": "",
         "topics": [], "html_url": "https://github.com/o/ghost", "block": {}},
    ]}, open(os.path.join(tmp, "github_cache.json"), "w"))

    generate.main()
    h = open(generate.INDEX).read()
    # both cards present
    assert "app" in h and "ghost" in h
    # uncloned repo shows the not-cloned chip + its GitHub link, no git chips
    assert "not cloned" in h and "github.com/o/ghost" in h
    assert "only on github" in h                       # gh description as thesis
    # the cloned repo merged (one card) and picked up the gh description as a gap-fill
    assert "cloud desc for app" in h
    assert h.count(">ghost<") <= 3                     # not duplicated


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\nALL {len(tests)} GITHUB SYNC TESTS PASS")
