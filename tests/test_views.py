#!/usr/bin/env python3
"""Top-level views tests — Skills catalog and Work Log collection + rendering.
Stdlib only; run: python tests/test_views.py  (exits non-zero on failure)."""
import datetime, json, os, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import views as V


def mkskill(base, *parts, name=None, desc="does a thing", extra=""):
    d = os.path.join(base, *parts)
    os.makedirs(d, exist_ok=True)
    fm = "---\n"
    if name:
        fm += f"name: {name}\n"
    fm += f"description: {desc}\n{extra}---\n# body\n"
    open(os.path.join(d, "SKILL.md"), "w").write(fm)
    return d


def test_frontmatter():
    fm = V.parse_frontmatter('---\nname: deploy\ndescription: "ship it"\n---\nbody')
    assert fm["name"] == "deploy" and fm["description"] == "ship it"
    # folded multi-line description (`>` block scalar)
    fm = V.parse_frontmatter("---\nname: x\ndescription: >\n  line one\n  line two\n---\n")
    assert fm["description"] == "line one line two"
    # no frontmatter at all
    assert V.parse_frontmatter("# just a heading\n") == {}
    # continuation lines glue onto the previous key
    fm = V.parse_frontmatter("---\ndescription: starts here\n  and continues\n---\n")
    assert fm["description"] == "starts here and continues"


def test_one_line_truncation():
    long = "word " * 100
    line = V._one_line(long)
    assert len(line) <= V.DESC_MAX and line.endswith("…")
    assert V._one_line("  spaced\n  out  ") == "spaced out"


def test_collect_and_group():
    tmp = tempfile.mkdtemp()
    claude = os.path.join(tmp, "dot-claude")
    # plugin skill: marketplaces/<mkt>/plugins/<plugin>/skills/<skill>/SKILL.md
    mkskill(claude, "plugins", "marketplaces", "mkt", "plugins", "ptools",
            "skills", "fix", name="fix", desc="fixes things")
    # claude-only plugin skill → invoke hint "auto"
    mkskill(claude, "plugins", "marketplaces", "mkt", "external_plugins", "ext",
            "skills", "bg", name="bg", extra="user-invocable: false\n")
    # project-local skill
    proj = os.path.join(tmp, "proj")
    mkskill(proj, ".claude", "skills", "deploy", name="deploy", desc="ships prod")
    # user-level skill, no `name:` → falls back to the folder name
    mkskill(claude, "skills", "note", desc="user skill")

    grouped = V.collect_skills([("proj", proj)], claude_dir=claude)
    labels = [g for g, _ in grouped]
    assert labels == ["plugin · ext  (mkt)", "plugin · ptools  (mkt)",
                      "project · proj", "user · ~/.claude/skills"]
    by = dict(grouped)
    assert by["plugin · ptools  (mkt)"][0]["invoke"] == "/ptools:fix"
    assert by["plugin · ext  (mkt)"][0]["invoke"] == "auto"
    assert by["project · proj"][0]["invoke"] == "/deploy"
    assert by["user · ~/.claude/skills"][0]["name"] == "note"

    # missing dirs → empty catalog, no error
    assert V.collect_skills([], claude_dir=os.path.join(tmp, "nope")) == []


def test_skills_html():
    grouped = [("plugin · p  (m)", [{"name": "a", "desc": "d <b>", "invoke": "/p:a"}])]
    h = V.skills_html(grouped)
    assert "skillFilter" in h and "d &lt;b&gt;" in h and "/p:a" in h
    assert 'class="sgcount">1<' in h
    # empty catalog renders the hint, not a crash
    assert "No SKILL.md" in V.skills_html([])


def mkrepo(base, name, email="1234+me@noreply.x.test"):   # regex-hostile, like GitHub's
    d = os.path.join(base, name)
    os.makedirs(d)
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", email], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Me"], check=True)
    return d


def mkcommit(repo, msg, epoch, email="1234+me@noreply.x.test"):
    env = dict(os.environ,
               GIT_AUTHOR_DATE=f"@{epoch} +0000", GIT_COMMITTER_DATE=f"@{epoch} +0000",
               GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_EMAIL=email,
               GIT_AUTHOR_NAME="Me", GIT_COMMITTER_NAME="Me")
    subprocess.run(["git", "-C", repo, "commit", "--allow-empty", "-q", "-m", msg],
                   env=env, check=True)


def test_collect_worklog():
    tmp = tempfile.mkdtemp()
    now = int(time.time())
    r1 = mkrepo(tmp, "one")
    # chronological, like a real repo — `--since` prunes traversal at the first
    # too-old commit, so an old commit at the tip would hide everything below it
    mkcommit(r1, "ancient", now - 200 * 86400)          # outside the window
    mkcommit(r1, "older work", now - 5 * 86400)
    mkcommit(r1, "someone else", now - 3000, email="upstream@fork.test")
    mkcommit(r1, "recent work", now - 3600)
    r2 = mkrepo(tmp, "two")                             # empty repo → no crash
    cs = V.collect_worklog([("one", r1), ("two", r2)])
    msgs = [c["s"] for c in cs]
    assert msgs == ["recent work", "older work"]        # newest first, mine only
    assert cs[0]["r"] == "one" and cs[0]["t"] == now - 3600
    assert V.collect_worklog([]) == []


def test_today_line():
    now = int(time.time())
    line = V.today_line([{"r": "a", "t": now, "s": "x"},
                         {"r": "b", "t": now, "s": "y"},
                         {"r": "a", "t": now - 40 * 86400, "s": "old"}])
    assert "2 commits" in line and "2 repos" in line
    assert V.today_line([]) == "Today · no commits yet"
    one = V.today_line([{"r": "a", "t": now, "s": "x"}])
    assert "1 commit</b>" in one and "1 repo</b>" in one   # singular forms


def test_worklog_html():
    h = V.worklog_html([{"r": "one", "t": 1700000000, "s": "close </script> tag"}])
    assert "<\\/script> tag" in h                       # embedded JSON can't break out
    assert "copyStandup" in h and "wlRender()" in h and 'id="wlchart"' in h
    assert 'id="wltokchart"' not in h                   # no token data → no 2nd chart
    h = V.worklog_html([], tokens={"2026-07-01": [10, 20, 30, 99999]})
    assert 'id="wltokchart"' in h
    assert '"2026-07-01": 60' in h                      # in+out+cache_w, reads excluded


def _usage_line(msg_id, ts, out_tokens):
    return json.dumps({"type": "assistant", "timestamp": ts, "requestId": "r-" + msg_id,
                       "message": {"id": msg_id, "usage": {
                           "input_tokens": 100, "output_tokens": out_tokens,
                           "cache_creation_input_tokens": 10,
                           "cache_read_input_tokens": 5000}}}) + "\n"


def test_collect_tokens():
    tmp = tempfile.mkdtemp()
    proj = os.path.join(tmp, "claude", "projects", "-Users-x-proj")
    os.makedirs(proj)
    day = datetime.date.today().isoformat()
    ts = day + "T10:00:00.000Z"
    f = os.path.join(proj, "session.jsonl")
    with open(f, "w") as fh:
        fh.write('{"type":"user","timestamp":"%s"}\n' % ts)      # no usage → skipped
        fh.write(_usage_line("m1", ts, 50))                       # streamed twice:
        fh.write(_usage_line("m1", ts, 70))                       # last one wins
        fh.write(_usage_line("m2", ts, 30))
        fh.write("not json at all\n")
    cache = os.path.join(tmp, "token_cache.json")
    claude = os.path.join(tmp, "claude")

    tok = V.collect_tokens(cache, claude_dir=claude)
    localday = (datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                .astimezone().date().isoformat())
    assert tok[localday] == [200, 100, 20, 10000]       # m1 deduped (70+30 out)

    # unchanged file → served from the cache (doctor it to prove reuse)
    c = json.load(open(cache))
    key = next(iter(c["files"]))
    c["files"][key]["days"] = {localday: [1, 2, 3, 4]}
    json.dump(c, open(cache, "w"))
    assert V.collect_tokens(cache, claude_dir=claude)[localday] == [1, 2, 3, 4]

    # file grows → reparsed, real numbers come back
    with open(f, "a") as fh:
        fh.write(_usage_line("m3", ts, 1))
    tok = V.collect_tokens(cache, claude_dir=claude)
    assert tok[localday] == [300, 101, 30, 15000]

    # no transcripts at all → empty dict, no crash
    assert V.collect_tokens(os.path.join(tmp, "c2.json"),
                            claude_dir=os.path.join(tmp, "nope")) == {}


ROADMAP_MD = """# proj — Roadmap

intro prose, not an item

## Now — unblocks launch

- [ ] **Ship [the thing](docs/thing.md)** — `now` item one
- [x] already done, hidden
- [ ] now item two

## Next

1. next item, numbered
- [ ] next item two

## Later

- later item (not shown as now/next)
"""


def test_parse_roadmap():
    s = V.parse_roadmap(ROADMAP_MD)
    assert s["now"] == ["Ship the thing — now item one", "now item two"]
    assert s["next"] == ["next item, numbered", "next item two"]
    assert s["top"][0] == "Ship the thing — now item one"   # checked item skipped
    # headingless file → only `top`
    s = V.parse_roadmap("# t\n\n## Ideas\n\n- idea one\n- idea two\n")
    assert s["now"] == [] and s["next"] == [] and s["top"] == ["idea one", "idea two"]


def test_collect_and_render_roadmaps():
    tmp = tempfile.mkdtemp()
    a = os.path.join(tmp, "a"); os.makedirs(os.path.join(a, "project-management"))
    open(os.path.join(a, "project-management", "ROADMAP.md"), "w").write(ROADMAP_MD)
    b = os.path.join(tmp, "b"); os.makedirs(b)          # no roadmap → omitted
    c = os.path.join(tmp, "c"); os.makedirs(c)
    open(os.path.join(c, "ROADMAP.md"), "w").write("# c\n- only <item>\n")
    rms = V.collect_roadmaps([("a", a), ("b", b), ("c", c)])
    assert [r["name"] for r in rms] == ["a", "c"]
    assert rms[0]["rel"] == "project-management/ROADMAP.md" and rms[1]["rel"] == "ROADMAP.md"
    h = V.roadmaps_html(rms)
    assert "Ship the thing" in h and "only &lt;item&gt;" in h      # escaped
    assert h.count('class="rmsec"') == 3                # a: Now+Next · c: Top items
    assert "2 projects with a ROADMAP.md" in h
    assert "No ROADMAP.md found" in V.roadmaps_html([])


if __name__ == "__main__":
    fails = 0
    for fn in sorted(k for k in list(globals()) if k.startswith("test_")):
        try:
            globals()[fn]()
            print(f"ok   {fn}")
        except AssertionError as e:
            print(f"FAIL {fn}: {e}")
            fails += 1
    sys.exit(1 if fails else 0)
