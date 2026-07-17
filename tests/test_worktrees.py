#!/usr/bin/env python3
"""Worktrees view tests — collection, the safe-to-remove verdict, rendering.
Builds real git repos + real worktrees in a temp dir (the verdict logic is all
git reachability, so faking the git layer would test nothing).
Stdlib only; run: python tests/test_worktrees.py  (exits non-zero on failure)."""
import os, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import views as V


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True).stdout.strip()


def mkrepo(base, name):
    """A git repo with one commit on main and a deterministic identity."""
    d = os.path.join(base, name)
    os.makedirs(d, exist_ok=True)
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "t@example.com")
    git(d, "config", "user.name", "T")
    open(os.path.join(d, "README.md"), "w").write("# hi\n")
    git(d, "add", "-A")
    git(d, "commit", "-qm", "init")
    return d


def commit(d, fname, msg="work"):
    open(os.path.join(d, fname), "w").write("x\n")
    git(d, "add", "-A")
    git(d, "commit", "-qm", msg)
    return git(d, "rev-parse", "HEAD")


def test_parse_porcelain():
    # branch record, detached record, and the attribute flags
    p = V._wt_parse("worktree /a\nHEAD abc123\nbranch refs/heads/main\n\n"
                    "worktree /b\nHEAD def456\ndetached\nlocked\n\n"
                    "worktree /c\nHEAD 000\nprunable gitdir file points nowhere\n")
    assert [w["path"] for w in p] == ["/a", "/b", "/c"]
    assert p[0]["branch"] == "main" and not p[0]["detached"]
    assert p[1]["detached"] and p[1]["locked"] and p[1]["branch"] == ""
    assert p[2]["prunable"]
    # junk never raises, and attribute lines before any worktree are ignored
    assert V._wt_parse("") == []
    assert V._wt_parse("HEAD orphaned\nbranch refs/heads/x\n") == []


def test_no_worktrees_is_empty():
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "solo")
        assert V.collect_worktrees([("solo", r)]) == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_clean_worktree_on_branch_is_safe():
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "app")
        wt = os.path.join(tmp, "app-feature")
        git(r, "worktree", "add", "-q", "-b", "feature", wt)
        commit(wt, "f.txt")                     # committed → on branch `feature`
        got = V.collect_worktrees([("app", r)])
        assert len(got) == 1                    # main checkout excluded
        w = got[0]
        assert w["repo"] == "app" and w["name"] == "app-feature"
        assert w["branch"] == "feature" and not w["detached"]
        assert w["dirty"] == 0 and w["unmerged"] == 1
        # removing the folder doesn't delete branch `feature` — the work survives
        assert w["safe"] and w["why"] == V.WT_SAFE
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_uncommitted_work_is_never_safe():
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "app")
        wt = os.path.join(tmp, "app-dirty")
        git(r, "worktree", "add", "-q", "-b", "dirty", wt)
        open(os.path.join(wt, "scratch.txt"), "w").write("unsaved\n")
        w = V.collect_worktrees([("app", r)])[0]
        assert w["dirty"] == 1
        assert not w["safe"] and w["why"] == "NO — 1 uncommitted file"
        # plural reads right too
        open(os.path.join(wt, "scratch2.txt"), "w").write("unsaved\n")
        w = V.collect_worktrees([("app", r)])[0]
        assert w["dirty"] == 2 and w["why"] == "NO — 2 uncommitted files"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_detached_head_off_branch_is_never_safe():
    """The case that actually loses work: a clean worktree whose commits are
    reachable from no branch at all. Removing it makes them unreachable."""
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "app")
        wt = os.path.join(tmp, "app-ghost")
        git(r, "worktree", "add", "-q", "--detach", wt)
        commit(wt, "orphan.txt", "work nobody branched")
        w = V.collect_worktrees([("app", r)])[0]
        assert w["detached"] and w["branch"] == ""
        assert w["dirty"] == 0                  # clean tree — but still not safe
        assert not w["contained"]
        assert not w["safe"] and w["why"] == "NO — commit is not on any branch"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_detached_head_still_on_a_branch_is_safe():
    """Detached but parked on a commit some branch already contains → the work
    is reachable without this folder, so it's safe."""
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "app")
        head = git(r, "rev-parse", "HEAD")      # main's tip
        wt = os.path.join(tmp, "app-park")
        git(r, "worktree", "add", "-q", "--detach", wt, head)
        w = V.collect_worktrees([("app", r)])[0]
        assert w["detached"] and w["contained"]
        assert w["safe"] and w["why"] == V.WT_SAFE
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_locked_worktree_is_not_safe():
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "app")
        wt = os.path.join(tmp, "app-locked")
        git(r, "worktree", "add", "-q", "-b", "held", wt)
        git(r, "worktree", "lock", wt)
        w = V.collect_worktrees([("app", r)])[0]
        assert w["locked"] and not w["safe"] and "locked" in w["why"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_deleted_folder_is_prunable_and_safe():
    """The folder is already gone; only the registration lingers. Nothing left
    to lose — say so rather than reporting a phantom clean checkout."""
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "app")
        wt = os.path.join(tmp, "app-gone")
        git(r, "worktree", "add", "-q", "-b", "gone", wt)
        shutil.rmtree(wt)
        w = V.collect_worktrees([("app", r)])[0]
        assert w["prunable"] and w["age_days"] == -1
        assert w["safe"] and "prune" in w["why"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_unmerged_count_and_age():
    tmp = tempfile.mkdtemp()
    try:
        r = mkrepo(tmp, "app")
        wt = os.path.join(tmp, "app-ahead")
        git(r, "worktree", "add", "-q", "-b", "ahead", wt)
        for i in range(3):
            commit(wt, f"c{i}.txt", f"c{i}")
        w = V.collect_worktrees([("app", r)])[0]
        assert w["unmerged"] == 3                # 3 commits not on main
        assert w["age_days"] == 0                # just created
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sorted_oldest_first_across_repos():
    tmp = tempfile.mkdtemp()
    try:
        a, b = mkrepo(tmp, "a"), mkrepo(tmp, "b")
        wa, wb = os.path.join(tmp, "a-wt"), os.path.join(tmp, "b-wt")
        git(a, "worktree", "add", "-q", "-b", "x", wa)
        git(b, "worktree", "add", "-q", "-b", "y", wb)
        old = time.time() - 68 * 86400          # the 68-day ghost
        os.utime(wa, (old, old))
        got = V.collect_worktrees([("a", a), ("b", b)])
        assert len(got) == 2
        assert got[0]["repo"] == "a" and got[0]["age_days"] == 68
        assert got[1]["age_days"] == 0          # ghosts float to the top
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_html_empty_state():
    h = V.worktrees_html([])
    assert "no extra checkouts" in h and "vempty" in h
    assert ".claude/worktrees/" in h            # explains where ghosts come from


def test_html_renders_verdicts_and_escapes():
    rows = [{"repo": "app", "repo_path": "/r/app", "path": "/r/app-x",
             "name": "app-x", "branch": "feat", "detached": False,
             "age_days": 68, "dirty": 2, "unmerged": 3, "locked": False,
             "prunable": False, "contained": True, "safe": False,
             "why": "NO — 2 uncommitted files"},
            {"repo": "app", "repo_path": "/r/app", "path": "/r/app-<y>",
             "name": "app-<y>", "branch": "", "detached": True,
             "age_days": 0, "dirty": 0, "unmerged": 0, "locked": False,
             "prunable": False, "contained": True, "safe": True,
             "why": V.WT_SAFE}]
    h = V.worktrees_html(rows)
    assert "wtverdict no" in h and "wtverdict ok" in h
    assert "68d" in h and "2 uncommitted" in h and "3 unmerged" in h
    assert "(detached)" in h and "wtbranch det" in h
    assert "1 hold unsaved work" in h           # header summarises the risk
    assert "git -C /r/app worktree remove" in h
    assert "app-&lt;y&gt;" in h and "<y>" not in h      # escaped, no raw markup


def test_html_all_safe_header():
    rows = [{"repo": "app", "repo_path": "/r/app", "path": "/r/app-x",
             "name": "app-x", "branch": "feat", "detached": False,
             "age_days": 1, "dirty": 0, "unmerged": 0, "locked": False,
             "prunable": False, "contained": True, "safe": True,
             "why": V.WT_SAFE}]
    h = V.worktrees_html(rows)
    assert "all safe to remove" in h and "1 extra checkout across 1 repo" in h


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
