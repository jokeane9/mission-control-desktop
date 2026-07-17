#!/usr/bin/env python3
"""generate.collect() + the attention rollup — the "what needs you" signal.

This is the function whose miscount shipped as #44: it counted every unmerged
*remote* branch, so a repo cloned to read (langflow: 1884 open PR branches) read
as "needs attention" forever, and two-thirds of a real workspace lit up. The
signal had no test; now the upstream-clone case is pinned.

Builds real git repos — a bare "upstream" with many branches, and a clone of it
— because the whole bug lives in the difference between local and remote
branches, which a faked git layer wouldn't have. Stdlib only; run:
    python tests/test_collect.py
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import generate


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True).stdout.strip()


def mkrepo(base, name):
    d = os.path.join(base, name)
    os.makedirs(d)
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "t@example.com")
    git(d, "config", "user.name", "T")
    open(os.path.join(d, "README.md"), "w").write("# hi\n")
    git(d, "add", "-A"); git(d, "commit", "-qm", "init")
    return d


def branch_commit(repo, branch, fname):
    git(repo, "checkout", "-q", "-b", branch)
    open(os.path.join(repo, fname), "w").write("x\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", f"work on {branch}")
    git(repo, "checkout", "-q", "main")


def test_upstream_clone_is_not_flagged():
    """The #44 case: a repo you cloned to READ. Upstream has many open branches;
    you have none locally. It must count 0 unmerged and not need attention —
    those are other people's PRs you'll never merge."""
    base = tempfile.mkdtemp()
    try:
        up = mkrepo(base, "upstream")
        for i in range(20):                          # 20 open "PR" branches
            branch_commit(up, f"pr-{i}", f"f{i}.txt")
        clone = os.path.join(base, "clone")
        subprocess.run(["git", "clone", "-q", up, clone], capture_output=True)
        git(clone, "config", "user.email", "t@example.com")

        remote = git(clone, "branch", "-r", "--no-merged", "main")
        assert len([l for l in remote.splitlines() if "HEAD" not in l]) >= 20, \
            "fixture check: the remote branches must exist to be miscounted"

        d = generate.collect(clone)
        assert d["unmerged"] == 0, f"upstream branches counted: {d['unmerged']}"
        assert d["dirty"] == 0
        attn = d["dirty"] or d["unmerged"] or d["stashes"] or d["ahead"] != "0"
        assert not attn, "a clean upstream clone must not need attention"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_local_unmerged_branches_still_count():
    """Your own WIP must still register — the fix narrows the count, it doesn't
    silence it. Two local feature branches → 2."""
    base = tempfile.mkdtemp()
    try:
        repo = mkrepo(base, "mine")
        branch_commit(repo, "feature-a", "a.txt")
        branch_commit(repo, "feature-b", "b.txt")
        d = generate.collect(repo)
        assert d["unmerged"] == 2, f"expected 2 local unmerged, got {d['unmerged']}"
        attn = d["dirty"] or d["unmerged"] or d["stashes"] or d["ahead"] != "0"
        assert attn, "real unmerged work should need attention"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_merged_local_branch_does_not_count():
    """A local branch already folded into main is done, not pending."""
    base = tempfile.mkdtemp()
    try:
        repo = mkrepo(base, "mine")
        branch_commit(repo, "done", "d.txt")
        git(repo, "merge", "-q", "done")
        d = generate.collect(repo)
        assert d["unmerged"] == 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_clean_repo_on_main_is_all_clear():
    base = tempfile.mkdtemp()
    try:
        repo = mkrepo(base, "clean")
        d = generate.collect(repo)
        assert d["branch"] == "main"
        assert d["dirty"] == 0 and d["unmerged"] == 0 and d["stashes"] == 0
        assert d["ahead"] == "0"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_dirty_and_stash_still_detected():
    """The fix is scoped to `unmerged` — the other attention signals are untouched."""
    base = tempfile.mkdtemp()
    try:
        repo = mkrepo(base, "busy")
        open(os.path.join(repo, "scratch.txt"), "w").write("wip\n")
        d = generate.collect(repo)
        assert d["dirty"] == 1
        git(repo, "stash", "-u")
        assert generate.collect(repo)["stashes"] == 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_workspace_attention_totals_ignore_upstream(tmp=None):
    """End to end through generate.workspace(): a workspace of two upstream
    clones and one repo with real WIP should report attn=1, not 3."""
    base = tempfile.mkdtemp()
    try:
        up = mkrepo(base, "upstream")
        for i in range(5):
            branch_commit(up, f"pr-{i}", f"f{i}.txt")
        clones = []
        for n in ("read-a", "read-b"):
            c = os.path.join(base, n)
            subprocess.run(["git", "clone", "-q", up, c], capture_output=True)
            git(c, "config", "user.email", "t@example.com")
            clones.append(c)
        mine = mkrepo(base, "mine")
        branch_commit(mine, "wip", "w.txt")

        cfg = {"projects": [
            {"name": "read-a", "path": clones[0]},
            {"name": "read-b", "path": clones[1]},
            {"name": "mine", "path": mine},
        ]}
        projects, totals = generate.workspace(cfg)
        assert totals["attn"] == 1, f"expected 1 needing attention, got {totals['attn']}"
        flagged = [pr["p"]["name"] for pr in projects if pr["attn"]]
        assert flagged == ["mine"], flagged
    finally:
        shutil.rmtree(base, ignore_errors=True)


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
