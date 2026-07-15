#!/usr/bin/env python3
"""P1 auto-populate tests — resolver unit tests + end-to-end render integration.
Stdlib only; run: python tests/test_autopopulate.py  (exits non-zero on failure)."""
import os, sys, json, tempfile, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import resolve as R
import generate


def mkrepo(base, name, files=None):
    d = os.path.join(base, name)
    os.makedirs(d)
    subprocess.run(["git", "init", "-q", d], check=True)
    for fn, c in (files or {}).items():
        open(os.path.join(d, fn), "w").write(c)
    return d


def test_mini_yaml():
    y = R.parse_mini_yaml('thesis: "hi there"\ntier: major\nhidden: true\nn: 42\n'
                          'tags: [a, b]\nviz:\n  app: .\n  pipeline: crawl\n')
    assert y["thesis"] == "hi there" and y["tier"] == "major"
    assert y["hidden"] is True and y["n"] == 42 and y["tags"] == ["a", "b"]
    assert y["viz"] == {"app": ".", "pipeline": "crawl"}
    assert R.parse_mini_yaml("tags:\n  - x\n  - y\n")["tags"] == ["x", "y"]


def test_frontmatter():
    fm = '---\nmission-control:\n  thesis: "shelf"\n  viz:\n    app: .\n---\n# T\nbody'
    p = R.parse_mini_yaml(R._frontmatter_block(fm, "mission-control"))
    assert p["thesis"] == "shelf" and p["viz"] == {"app": "."}


def test_readers():
    tmp = tempfile.mkdtemp()
    rj = mkrepo(tmp, "j", {".mission-control.json": json.dumps(
        {"thesis": "jt", "viz": {"app": "x"}, "accounts": "me@x"})})
    b = R.read_block(rj)
    assert b["thesis"] == "jt" and b["viz_app"] == "x" and b["email"] == "me@x"
    assert "viz" not in b and "accounts" not in b

    rp = mkrepo(tmp, "p", {"package.json": json.dumps(
        {"description": "node app", "homepage": "https://p.dev"})})
    m = R.repo_metadata(rp)
    assert m["thesis"] == "node app" and m["prod"] == "https://p.dev"

    rh = mkrepo(tmp, "h", {"CLAUDE.md":
        "# P\n\nDoes a thing.\n\n## Stack\n\nRemix + Postgres\n\nhttps://c.example\n"})
    h = R.heuristics(rh)
    assert h["thesis"] == "Does a thing." and h["stack"] == "Remix + Postgres"
    assert h["prod"] == "https://c.example"


def test_resolve_precedence():
    tmp = tempfile.mkdtemp()
    r = mkrepo(tmp, "all", {
        ".mission-control.json": json.dumps({"thesis": "block", "stack": "bs"}),
        "package.json": json.dumps({"description": "meta", "homepage": "https://m.dev"}),
        "CLAUDE.md": "# x\n\nheur\n\n## Stack\n\nhs\n"})
    cfg = {"projects": [{"name": "all", "path": r, "thesis": "OVR"}]}
    facts, prov = R.resolve({"path": r}, cfg)
    assert facts["thesis"] == "OVR" and prov["thesis"] == "overrides"
    assert facts["stack"] == "bs" and prov["stack"] == "block"
    assert facts["prod"] == "https://m.dev" and prov["prod"] == "metadata"
    assert facts["name"] == "all" and facts["arch"] == "CLAUDE.md"


def test_discover_dedupe_and_ignores():
    tmp = tempfile.mkdtemp()
    root = os.path.join(tmp, "root"); os.makedirs(root)
    r = mkrepo(root, "s", {"README.md": "x"})
    os.makedirs(os.path.join(r, "node_modules", "pkg", ".git"))
    cfg = {"roots": [root], "projects": [{"name": "s", "path": r}]}
    d = R.discover(cfg)
    assert len(d) == 1 and R.identity(d[0]) == os.path.realpath(r)
    assert all("node_modules" not in f for f in R.find_git_dirs(root))


def test_integration():
    tmp = tempfile.mkdtemp()
    root = os.path.join(tmp, "code"); os.makedirs(root)
    mkrepo(root, "alpha", {"CLAUDE.md": "# A\n\nAlpha does pipelines.\n\n## Stack\n\nZig-Nim-sentinel\n"})
    mkrepo(root, "beta", {"package.json": json.dumps({"description": "Beta app", "homepage": "https://b.dev"})})
    mkrepo(root, "gamma", {".mission-control.json": json.dumps({"thesis": "Gamma block", "tier": "tools"})})
    generate.DATA = tmp        # keep a real dev github_cache.json out of the render
    generate.BASELINE = os.path.join(tmp, "baseline.json")
    generate.INDEX = os.path.join(tmp, "index.html")

    json.dump({"projects": [], "roots": [root]}, open(generate.BASELINE, "w"))
    generate.main()
    h = open(generate.INDEX).read()
    for n in ["alpha", "beta", "gamma", "Alpha does pipelines.", "Zig-Nim-sentinel", "Beta app", "Gamma block"]:
        assert n in h, f"missing {n}"

    json.dump({"projects": [{"name": "alpha", "path": os.path.join(root, "alpha"),
                             "thesis": "OVERRIDE"}], "roots": [root]},
              open(generate.BASELINE, "w"))
    generate.main()
    h = open(generate.INDEX).read()
    assert "OVERRIDE" in h and "Alpha does pipelines." not in h

    open(os.path.join(root, "gamma", ".mission-control.json"), "w").write(json.dumps({"hidden": True}))
    generate.main()
    assert "gamma" not in open(generate.INDEX).read()

    json.dump({"projects": [{"name": "alpha", "path": os.path.join(root, "alpha"), "thesis": "just alpha"}]},
              open(generate.BASELINE, "w"))
    generate.main()
    h = open(generate.INDEX).read()
    assert "just alpha" in h and "beta" not in h and "gamma" not in h
    # no roots → auto-fill OFF → alpha's CLAUDE.md stack must NOT leak in
    assert "Zig-Nim-sentinel" not in h, "auto-fill leaked without roots configured"


def test_auto_maps():
    tmp = tempfile.mkdtemp()
    # detection
    a = mkrepo(tmp, "nextapp", {"package.json": json.dumps({"dependencies": {"next": "14"}})})
    assert generate.detect_viz_app(a) == "."
    r = mkrepo(tmp, "remixapp"); os.makedirs(os.path.join(r, "app", "routes"))
    assert generate.detect_viz_app(r) == "."
    plain = mkrepo(tmp, "plain", {"package.json": json.dumps({"dependencies": {"lodash": "1"}})})
    assert generate.detect_viz_app(plain) is None
    pipe = mkrepo(tmp, "pipe", {"requirements.txt": "openai==1.0\nrequests\n"})
    assert generate.detect_viz_pipeline(pipe) == "."
    assert generate.detect_viz_pipeline(plain) is None

    # _viz_plan: no tools → nothing; explicit works even auto-off; auto detects
    assert generate._viz_plan(a, {}, {}, True) == {}
    stub = os.path.join(tmp, "agentviz.py")
    open(stub, "w").write("import sys; open(sys.argv[2],'w').write('<html>map</html>')\n")
    tools = {"agentviz": stub}
    assert "pipeline" not in generate._viz_plan(pipe, {}, tools, False)      # auto off, no explicit
    assert generate._viz_plan(pipe, {"viz_pipeline": "."}, tools, False)["pipeline"][1] == "."
    assert generate._viz_plan(pipe, {}, tools, True)["pipeline"][1] == "."   # auto-detected

    # end-to-end: detection → run stub → pipeline tab
    old = generate.DATA
    generate.DATA = tmp
    try:
        links = generate.build_viz("pipe", pipe, {}, tools, auto=True)
        assert ("pipeline", "viz/pipe-pipeline.html") in links, links
        assert os.path.isfile(os.path.join(tmp, "viz", "pipe-pipeline.html"))
    finally:
        generate.DATA = old


def test_provenance_badge():
    # prov_mark: manual/absent → no badge; heuristic → guess; others → auto
    assert generate.prov_mark({"stack": "overrides"}, "stack") == ""
    assert generate.prov_mark(None, "stack") == ""
    assert 'class="prov"' in generate.prov_mark({"prod": "metadata"}, "prod")
    assert 'class="prov guess"' in generate.prov_mark({"stack": "heuristic"}, "stack")

    tmp = tempfile.mkdtemp()
    root = os.path.join(tmp, "code"); os.makedirs(root)
    d = mkrepo(root, "svc", {"CLAUDE.md": "# Svc\n\nDoes things.\n\n## Stack\n\nGo\n"})
    generate.DATA = tmp        # keep a real dev github_cache.json out of the render
    generate.BASELINE = os.path.join(tmp, "b.json")
    generate.INDEX = os.path.join(tmp, "i.html")

    # roots on, one manual override → heuristic thesis badged, override unbadged
    json.dump({"roots": [root], "projects": [{"name": "svc", "path": d, "prod_env": "MANUAL"}]},
              open(generate.BASELINE, "w"))
    generate.main()
    h = open(generate.INDEX).read()
    assert 'class="prov guess"' in h                       # heuristic thesis/stack
    seg = h[h.index("MANUAL"): h.index("MANUAL") + 80]
    assert "prov" not in seg                               # manual override → no badge

    # roots off → no badges at all (existing users unaffected)
    json.dump({"projects": [{"name": "svc", "path": d, "thesis": "m", "stack": "s"}]},
              open(generate.BASELINE, "w"))
    generate.main()
    assert 'class="prov' not in open(generate.INDEX).read()


def test_auto_groups():
    F = [
        {"name": "shelf", "path": "/p/shelf"},
        {"name": "shelf-site", "path": "/p/shelf-site"},
        {"name": "shelf-workbench", "path": "/p/shelf-workbench"},   # prefix family "shelf"
        {"name": "dspy", "path": "/p/dspy"},                        # lone -> ungrouped
        {"name": "alpha", "path": "/p/alpha", "github_url": "https://github.com/widgets/alpha"},
        {"name": "beta",  "path": "/p/beta",  "github_url": "https://github.com/widgets/beta"},   # owner family
        {"name": "one", "path": "/p/sub/one"},
        {"name": "two", "path": "/p/sub/two"},                      # parent-dir family "sub"
        {"name": "curated", "path": "/p/curated", "group": "mine"}, # manual -> untouched
    ]
    g = R.auto_groups(F)
    assert g["shelf"] == g["shelf-site"] == g["shelf-workbench"] == "shelf"
    assert "dspy" not in g                                          # singleton stays ungrouped
    assert g["alpha"] == g["beta"] == "widgets"                    # owner family (no shared name prefix)
    assert g["one"] == g["two"] == "sub"                           # non-dominant parent folder
    assert "curated" not in g                                       # manual group never overwritten

    # a too-generic / short prefix is not a family even with >= 2 repos
    g2 = R.auto_groups([{"name": "api-x", "path": "/p/api-x"},
                        {"name": "api-y", "path": "/p/api-y"}])
    assert "api-x" not in g2 and "api-y" not in g2
    # `group` is a resolvable key so a manual override flows through resolve()
    assert "group" in R.PROJECT_KEYS


def test_grouped_sidebar_render():
    tmp = tempfile.mkdtemp()
    root = os.path.join(tmp, "code"); os.makedirs(root)
    for n in ["shelf", "shelf-site", "shelf-workbench", "loner"]:
        mkrepo(root, n)
    generate.DATA = tmp
    generate.BASELINE = os.path.join(tmp, "baseline.json")
    generate.INDEX = os.path.join(tmp, "index.html")
    json.dump({"projects": [], "roots": [root]}, open(generate.BASELINE, "w"))
    generate.main()
    h = open(generate.INDEX).read()
    assert 'class="sgrouphd"' in h and "toggleGroup" in h          # grouped, collapsible
    assert 'id="ghd-shelf"' in h                                   # the shelf family header
    assert 'id="ghd-ungrouped"' in h                              # the loner falls here


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\nALL {len(tests)} AUTO-POPULATE TESTS PASS")
