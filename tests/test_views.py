#!/usr/bin/env python3
"""Top-level views tests — Skills catalog parsing, grouping, rendering.
Stdlib only; run: python tests/test_views.py  (exits non-zero on failure)."""
import os, sys, tempfile

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
