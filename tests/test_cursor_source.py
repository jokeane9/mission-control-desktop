#!/usr/bin/env python3
"""CursorSource + multi-source Sessions.

Builds a real SQLite DB in Cursor's shape (cursorDiskKV with composerData: and
bubbleId: rows) — the extraction is all about that schema, so a mock would test
nothing. Covers the honest empties (Cursor records no tokens/PRs/worktrees), the
privacy wall (the DB is full of prompt/response text; the reader touches only
paths/names/timestamps), repo attribution, and the source merge.

Stdlib only (sqlite3 is stdlib); run: python tests/test_cursor_source.py
"""
import datetime, json, os, shutil, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import views as V


def _ms(dt):
    return int(dt.timestamp() * 1000)


def build_db(path, composers):
    """composers: list of dicts describing a session. Writes a Cursor-shaped DB."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
    for c in composers:
        cid = c["id"]
        hdrs = [{"bubbleId": f"b{i}", "type": 1 if i % 2 else 2}
                for i in range(c.get("msgs", 2))]
        data = {
            "composerId": cid,
            "fullConversationHeadersOnly": hdrs if c.get("msgs", 2) else [],
            "createdAt": _ms(c["created"]),
            "lastUpdatedAt": _ms(c["updated"]),
            "usageData": {},                 # Cursor leaves this empty → no tokens
            "pullRequests": [],              # empty → no PRs
        }
        if c.get("repo_path"):
            data["trackedGitRepos"] = [{
                "repoPath": c["repo_path"],
                "branches": [{"branchName": b, "lastInteractionAt": _ms(c["updated"])}
                             for b in c.get("branches", [])],
            }]
            if c.get("branches"):
                data["committedToBranch"] = c["branches"][0]
        con.execute("INSERT INTO cursorDiskKV VALUES (?,?)",
                    (f"composerData:{cid}", json.dumps(data)))
        # bubbles: edit tool calls carry the file path in params; result is CONTENT
        for i, fp in enumerate(c.get("edits", [])):
            bub = {"toolFormerData": {
                "name": "edit_file_v2",
                "params": json.dumps({"relativeWorkspacePath": fp,
                                      "noCodeblock": True}),
                "result": c.get("secret", "SECRET_FILE_CONTENTS"),   # must not leak
            }, "text": c.get("secret", "SECRET_PROMPT_BODY")}         # must not leak
            con.execute("INSERT INTO cursorDiskKV VALUES (?,?)",
                        (f"bubbleId:{cid}|b{i}", json.dumps(bub)))
        for i in range(c.get("reads", 0)):   # non-edit tool calls, for the profile
            bub = {"toolFormerData": {"name": "read_file_v2", "params": "{}"}}
            con.execute("INSERT INTO cursorDiskKV VALUES (?,?)",
                        (f"bubbleId:{cid}|r{i}", json.dumps(bub)))
    con.commit()
    con.close()


def workspace():
    base = tempfile.mkdtemp()
    repo = os.path.join(base, "shelf"); os.makedirs(repo)
    db = os.path.join(base, "state.vscdb")
    now = datetime.datetime.now()
    return base, repo, db, now


# --- extraction ------------------------------------------------------------- #
def test_extracts_a_real_cursor_session():
    base, repo, db, now = workspace()
    try:
        build_db(db, [{
            "id": "cur00001", "repo_path": repo, "branches": ["feat/billing"],
            "created": now - datetime.timedelta(hours=2),
            "updated": now - datetime.timedelta(hours=1), "msgs": 40,
            "edits": [os.path.join(repo, "app", "billing.tsx"),
                      os.path.join(repo, "app", "billing.tsx"),
                      os.path.join(repo, "lib", "stripe.ts")],
            "reads": 5,
        }])
        s = V.CursorSource(db_path=db).sessions([("shelf", repo)], now,
                                                now - datetime.timedelta(days=30))
        assert len(s) == 1
        r = s[0]
        assert r["source"] == "cursor"
        assert r["repo"] == "shelf"
        assert r["id"] == "cur00001"
        assert r["branch"] == "feat/billing" and r["branches"] == ["feat/billing"]
        assert r["files"][0] == "billing.tsx"          # most-edited first
        assert set(r["files"]) == {"billing.tsx", "stripe.ts"}
        assert set(r["dirs"]) == {"app", "lib"}
        assert r["tools"].get("edit_file_v2") == 3 and r["tools"].get("read_file_v2") == 5
        assert r["msgs"] == 40
        # honest empties — Cursor records none of these
        assert r["tokens"] == 0 and r["prs"] == [] and r["worktree"] == ""
        assert r["worktree_live"] is False
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_privacy_no_prompt_or_file_content_leaks():
    """The DB is full of prompt/response/file text. The reader must surface only
    paths, names, timestamps. A leak here is silent."""
    base, repo, db, now = workspace()
    try:
        build_db(db, [{
            "id": "cur00002", "repo_path": repo, "branches": ["main"],
            "created": now - datetime.timedelta(hours=3),
            "updated": now - datetime.timedelta(hours=2), "msgs": 6,
            "edits": [os.path.join(repo, "secret.py")],
            "secret": "LEAKED_CURSOR_CONTENT",
        }])
        s = V.CursorSource(db_path=db).sessions([("shelf", repo)], now,
                                                now - datetime.timedelta(days=30))
        assert "LEAKED_CURSOR_CONTENT" not in json.dumps(s)
        assert "LEAKED_CURSOR_CONTENT" not in V.sessions_html(s)
        assert s[0]["files"] == ["secret.py"]          # the path is fine — it's metadata
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_empty_drafts_and_foreign_repos_skipped():
    base, repo, db, now = workspace()
    other = os.path.join(base, "not-mine"); os.makedirs(other)
    try:
        build_db(db, [
            {"id": "draft001", "repo_path": repo, "created": now, "updated": now,
             "msgs": 0},                                # empty draft
            {"id": "forgn001", "repo_path": other, "created": now, "updated": now,
             "msgs": 5},                                # real, but foreign repo
        ])
        s = V.CursorSource(db_path=db).sessions([("shelf", repo)], now,
                                                now - datetime.timedelta(days=30))
        assert s == []
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_cutoff_excludes_old_sessions():
    base, repo, db, now = workspace()
    try:
        build_db(db, [{"id": "oldcur01", "repo_path": repo, "branches": ["main"],
                       "created": now - datetime.timedelta(days=90),
                       "updated": now - datetime.timedelta(days=88), "msgs": 5}])
        wide = V.CursorSource(db_path=db).sessions([("shelf", repo)], now,
                                                   now - datetime.timedelta(days=365))
        narrow = V.CursorSource(db_path=db).sessions([("shelf", repo)], now,
                                                     now - datetime.timedelta(days=30))
        assert len(wide) == 1 and narrow == []
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_missing_db_is_empty_not_an_error():
    assert V.CursorSource(db_path="/no/such/state.vscdb").sessions(
        [("x", "/x")], datetime.datetime.now(),
        datetime.datetime.now() - datetime.timedelta(days=30)) == []


# --- default_sources -------------------------------------------------------- #
def test_default_sources_adds_cursor_only_when_db_present():
    base, repo, db, now = workspace()
    try:
        names = lambda cur: [s.name for s in V.default_sources(
            os.path.join(base, "tok.json"), claude_dir=base, cursor_db=cur)]
        assert names("/no/such.db") == ["claude"]      # absent → claude only
        build_db(db, [])
        assert names(db) == ["claude", "cursor"]        # present → both
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- merge / collect_sessions ----------------------------------------------- #
class _FakeSource:
    def __init__(self, name, recs, boom=False):
        self.name, self._recs, self._boom = name, recs, boom
    def sessions(self, project_dirs, now, cutoff):
        if self._boom:
            raise RuntimeError("schema drift")
        return self._recs


def test_merge_sorts_and_tags_and_survives_a_flaky_source():
    now = datetime.datetime.now()
    claude = {"source": "claude", "age_min": 100, "active": False,
              "worktree_live": False, "id": "c", "repo": "r"}
    cursor = {"source": "cursor", "age_min": 5, "active": True,
              "worktree_live": False, "id": "u", "repo": "r"}
    out = V.collect_sessions([("r", "/r")], "/tmp/x", days=30, sources=[
        _FakeSource("claude", [claude]),
        _FakeSource("cursor", [cursor]),
        _FakeSource("broken", [], boom=True),          # must be swallowed
    ])
    assert [s["source"] for s in out] == ["cursor", "claude"]   # newest first
    assert len(out) == 2                                # broken source dropped, not fatal


# --- rendering -------------------------------------------------------------- #
def _row(source, age=10):
    return {"id": source[:4], "source": source, "repo": "shelf", "cwd": "/shelf",
            "branch": "main", "branches": ["main"], "files": ["a.py"], "dirs": ["src"],
            "prs": [], "tools": {}, "started": "", "ended": "", "age_min": age,
            "mins": 5, "msgs": 3, "tokens": 0, "worktree": "", "worktree_live": False,
            "active": age <= 30}


def test_html_shows_source_badges_and_filter():
    h = V.sessions_html([_row("claude"), _row("cursor", 20)],
                        sources_present=["claude", "cursor"])
    assert "ssrc claude" in h and "ssrc cursor" in h        # both badges
    assert "sessfilter" in h and "sessFilter(this,'cursor')" in h
    assert "1 Claude" in h and "1 Cursor" in h              # per-tool subtitle


def test_html_no_filter_with_a_single_source():
    h = V.sessions_html([_row("claude")], sources_present=["claude"])
    assert "sessfilter" not in h                            # one tool → no filter clutter


def test_html_detected_but_quiet_empty_state():
    """Cursor present, zero sessions in window: filter still lists it (an honest
    empty on select), and the empty copy names what was read."""
    h = V.sessions_html([], sources_present=["claude", "cursor"])
    assert "Cursor" in h and "vempty" in h and "never prompts" in h


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
