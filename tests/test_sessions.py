#!/usr/bin/env python3
"""Sessions view tests — transcript metadata, repo attribution, the worktree
join, and the privacy rule.

Two of these guard things that fail SILENTLY and badly:
  * privacy — the transcripts are the most sensitive thing on the machine. If
    prompt/response content ever reaches the record or the page, nothing errors;
    it just leaks. Pinned explicitly rather than trusted.
  * repo attribution — `~/.claude/projects/<dir>` mangles BOTH `/` and `.` to
    `-`, so un-mangling is ambiguous (killdate.dev vs killdate/dev). We prefix-
    match real cwd values instead; a regression here silently misfiles sessions.

Stdlib only; run: python tests/test_sessions.py
"""
import datetime, json, os, shutil, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import views as V


def ts(hours_ago=0):
    return ((datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=hours_ago))
            .strftime("%Y-%m-%dT%H:%M:%S.000Z"))


def mktranscript(claude, slug, sid, cwd, *, branch="main", hours_ago=0,
                 msgs=2, usage=True, secret="SUPER_SECRET_PROMPT_TEXT"):
    """A realistic transcript: a launch line carrying cwd, some messages with
    content, and a usage line. `secret` is the content that must never surface."""
    d = os.path.join(claude, "projects", slug)
    os.makedirs(d, exist_ok=True)
    lines = [{"type": "queue-operation", "sessionId": sid, "timestamp": ts(hours_ago + 1)},
             {"type": "user", "cwd": cwd, "gitBranch": branch,
              "timestamp": ts(hours_ago + 1), "message": {"content": secret}}]
    for i in range(msgs - 1):
        lines.append({"type": "assistant", "cwd": cwd, "timestamp": ts(hours_ago),
                      "message": {"content": secret, "id": f"m{i}",
                                  **({"usage": {"input_tokens": 10, "output_tokens": 20,
                                                "cache_creation_input_tokens": 1,
                                                "cache_read_input_tokens": 2}}
                                     if usage else {})}})
    p = os.path.join(d, f"{sid}.jsonl")
    with open(p, "w") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")
    return p


def workspace():
    base = tempfile.mkdtemp()
    claude = os.path.join(base, "claude")
    repo = os.path.join(base, "app")
    os.makedirs(repo)
    cache = os.path.join(base, "tok.json")
    return base, claude, repo, cache


# --- privacy ---------------------------------------------------------------- #
def test_no_prompt_content_in_records_or_html():
    """The rule: metadata only — never prompts, never responses, never titles.
    A leak here is silent; nothing would error, the content would just appear."""
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "aaaaaaaa-1", repo, secret="LEAKED_SECRET")
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert len(s) == 1
        blob = json.dumps(s)
        assert "LEAKED_SECRET" not in blob, "prompt content reached the record"
        assert "LEAKED_SECRET" not in V.sessions_html(s), "content reached the page"
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- repo attribution ------------------------------------------------------- #
def test_launch_cwd_wins_over_later_drift():
    """A session cd's around — one real transcript touched four directories. The
    FIRST cwd is the launch dir; later ones must not re-home the session."""
    base, claude, repo, cache = workspace()
    other = os.path.join(base, "elsewhere"); os.makedirs(other)
    try:
        d = os.path.join(claude, "projects", "-app"); os.makedirs(d)
        with open(os.path.join(d, "bbbbbbbb-1.jsonl"), "w") as f:
            f.write(json.dumps({"type": "user", "cwd": repo, "gitBranch": "main",
                                "timestamp": ts(1)}) + "\n")
            f.write(json.dumps({"type": "assistant", "cwd": other,
                                "timestamp": ts(0)}) + "\n")
        s = V.collect_sessions([("app", repo), ("elsewhere", other)], cache,
                               claude_dir=claude)
        assert len(s) == 1 and s[0]["repo"] == "app"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_longest_prefix_wins():
    """A nested repo must win over its parent, or every session in a nested
    checkout is misfiled to the outer one."""
    base, claude, repo, cache = workspace()
    inner = os.path.join(repo, "packages", "inner")
    os.makedirs(inner)
    try:
        mktranscript(claude, "-inner", "cccccccc-1", inner)
        s = V.collect_sessions([("app", repo), ("inner", inner)], cache,
                               claude_dir=claude)
        assert s[0]["repo"] == "inner"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_sessions_outside_dashboard_repos_are_skipped():
    """Scoped to project_dirs, like Worktrees."""
    base, claude, repo, cache = workspace()
    stray = os.path.join(base, "not-a-project"); os.makedirs(stray)
    try:
        mktranscript(claude, "-stray", "dddddddd-1", stray)
        assert V.collect_sessions([("app", repo)], cache, claude_dir=claude) == []
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- the worktree join ------------------------------------------------------ #
def test_session_in_a_live_worktree_is_flagged():
    """The point of the feature: a worktree still on disk after its session
    ended is the ghost the Worktrees view hunts."""
    base, claude, repo, cache = workspace()
    wt = os.path.join(repo, ".claude", "worktrees", "ecstatic-torvalds-b0d3c3")
    os.makedirs(wt)
    try:
        mktranscript(claude, "-app--claude-worktrees-x", "eeeeeeee-1", wt, hours_ago=48)
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert len(s) == 1
        assert s[0]["repo"] == "app"                 # still attributed to the parent
        # realpath: macOS symlinks /var -> /private/var, and collect_sessions
        # normalises so prefix-matching can't miss on that alone.
        assert s[0]["worktree"] == os.path.realpath(wt)
        assert s[0]["worktree_live"] is True
        assert "left a worktree" in V.sessions_html(s)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_session_whose_worktree_was_cleaned_is_not_flagged():
    """Cleaned up = nothing to report. Flagging it would train the user to
    ignore the flag."""
    base, claude, repo, cache = workspace()
    wt = os.path.join(repo, ".claude", "worktrees", "gone")
    try:
        mktranscript(claude, "-app--claude-worktrees-gone", "ffffffff-1", wt,
                     hours_ago=48)
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert len(s) == 1
        assert s[0]["worktree"] == os.path.realpath(wt)
        assert s[0]["worktree_live"] is False
        assert "left a worktree" not in V.sessions_html(s)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_worktree_of():
    wt = "/r/app/.claude/worktrees/brave-hopper"
    assert V._worktree_of(wt) == wt
    assert V._worktree_of(wt + "/src/deep") == wt
    assert V._worktree_of("/r/app/src") == ""


# --- liveness + window ------------------------------------------------------ #
def test_active_vs_stale():
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "11111111-1", repo, hours_ago=0)
        mktranscript(claude, "-app", "22222222-2", repo, hours_ago=10)
        s = {x["id"]: x for x in V.collect_sessions([("app", repo)], cache,
                                                    claude_dir=claude)}
        assert s["11111111"]["active"] is True
        assert s["22222222"]["active"] is False
        assert s["22222222"]["age_min"] >= 60 * 9
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_window_excludes_old_sessions():
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "33333333-3", repo, hours_ago=24 * 60)
        assert V.collect_sessions([("app", repo)], cache, claude_dir=claude,
                                  days=30) == []
        assert len(V.collect_sessions([("app", repo)], cache, claude_dir=claude,
                                      days=90)) == 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_newest_first():
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "aaaa1111-1", repo, hours_ago=20)
        mktranscript(claude, "-app", "bbbb2222-2", repo, hours_ago=1)
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert [x["id"] for x in s] == ["bbbb2222", "aaaa1111"]
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- shared cache ----------------------------------------------------------- #
def test_one_parse_feeds_tokens_and_sessions():
    """Sessions and the Work Log share a cache entry. If they ever diverge, the
    transcripts get walked twice — hundreds of MB, on the render path."""
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "99999999-9", repo, msgs=3)
        tok = V.collect_tokens(cache, claude_dir=claude)
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert tok and s
        entry = next(iter(json.load(open(cache))["files"].values()))
        assert set(entry) == {"size", "mtime", "days", "meta"}
        assert json.load(open(cache))["v"] == V._CACHE_V
        # the session's token total matches what the Work Log counted
        assert s[0]["tokens"] == sum(sum(v) for v in tok.values())
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_stale_cache_version_is_rebuilt_not_trusted():
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "88888888-8", repo)
        json.dump({"v": 1, "files": {"/old": {"days": {}}}}, open(cache, "w"))
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert len(s) == 1                       # rebuilt, not read from v1
        assert json.load(open(cache))["v"] == V._CACHE_V
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- rendering -------------------------------------------------------------- #
def test_html_empty_state():
    h = V.sessions_html([])
    assert "no recent sessions" in h and "vempty" in h
    assert "never prompts" in h              # states the privacy rule to the user


def test_html_escapes_paths():
    base, claude, repo, cache = workspace()
    try:
        rows = [{"id": "aaaa", "repo": "<script>", "cwd": "/r/<x>", "branch": "b",
                 "started": "", "ended": "", "age_min": 5, "mins": 2, "msgs": 1,
                 "tokens": 10, "worktree": "", "worktree_live": False,
                 "active": False}]
        h = V.sessions_html(rows)
        assert "&lt;script&gt;" in h and "<script>" not in h
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_malformed_transcript_never_raises():
    base, claude, repo, cache = workspace()
    try:
        d = os.path.join(claude, "projects", "-app"); os.makedirs(d)
        open(os.path.join(d, "bad.jsonl"), "w").write("{not json\n\n{}\n")
        assert V.collect_sessions([("app", repo)], cache, claude_dir=claude) == []
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
