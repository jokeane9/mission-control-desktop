#!/usr/bin/env python3
"""Top-level views tests — Skills catalog and Work Log collection + rendering.
Stdlib only; run: python tests/test_views.py  (exits non-zero on failure)."""
import os, subprocess, sys, tempfile, time

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
