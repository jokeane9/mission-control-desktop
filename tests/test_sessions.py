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
import datetime, json, os, shutil, subprocess, sys, tempfile

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


def mkfootprint(claude, slug, sid, cwd, *, edits=(), branches=("main",),
                prs=(), bash=0, hours_ago=1, secret="SECRET_PROMPT"):
    """A transcript with real footprint signal: tool_use edits, extra branches,
    pr-link records, Bash calls. `secret` seeds prompt content that must not leak
    into the footprint."""
    d = os.path.join(claude, "projects", slug)
    os.makedirs(d, exist_ok=True)
    lines = [{"type": "user", "cwd": cwd, "gitBranch": branches[0],
              "timestamp": ts(hours_ago + 1), "message": {"content": secret}}]
    for br in branches[1:]:                       # branch drift across the session
        lines.append({"type": "user", "cwd": cwd, "gitBranch": br,
                      "timestamp": ts(hours_ago), "message": {"content": secret}})
    tool_blocks = []
    for fp in edits:
        tool_blocks.append({"type": "tool_use", "name": "Edit",
                            "input": {"file_path": fp}})
    for _ in range(bash):
        tool_blocks.append({"type": "tool_use", "name": "Bash",
                            "input": {"command": secret}})   # command must not leak
    if tool_blocks:
        lines.append({"type": "assistant", "cwd": cwd, "timestamp": ts(hours_ago),
                      "message": {"content": tool_blocks, "id": "a1",
                                  "usage": {"input_tokens": 5, "output_tokens": 5,
                                            "cache_creation_input_tokens": 0,
                                            "cache_read_input_tokens": 0}}})
    for num in prs:
        lines.append({"type": "pr-link", "sessionId": sid, "timestamp": ts(hours_ago),
                      "prNumber": str(num), "prUrl": f"https://github.com/o/r/pull/{num}",
                      "prRepository": "o/r"})
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


# --- footprint (#49): a session's identity from what it did ----------------- #
def test_footprint_files_dirs_branches_prs_tools():
    base, claude, repo, cache = workspace()
    try:
        mkfootprint(claude, "-app", "fp000001", repo,
                    edits=[os.path.join(repo, "src", "auth.py"),
                           os.path.join(repo, "src", "auth.py"),   # edited twice
                           os.path.join(repo, "docs", "README.md")],
                    branches=["main", "feat/auth", "fix/typo"],
                    prs=[41, 42], bash=7)
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)[0]
        assert s["files"][0] == "auth.py"            # most-edited first
        assert set(s["files"]) == {"auth.py", "README.md"}
        assert set(s["dirs"]) == {"src", "docs"}
        assert s["branches"] == ["main", "feat/auth", "fix/typo"]
        assert [p["num"] for p in s["prs"]] == ["41", "42"]
        assert s["prs"][0]["url"].endswith("/pull/41")
        assert s["tools"].get("Edit") == 3 and s["tools"].get("Bash") == 7
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_footprint_never_leaks_prompt_or_command_content():
    """The privacy wall extends to the footprint: it records file PATHS and tool
    NAMES, never the Bash command text or the prompt that drove them."""
    base, claude, repo, cache = workspace()
    try:
        mkfootprint(claude, "-app", "fp000002", repo,
                    edits=[os.path.join(repo, "x.py")], bash=3,
                    prs=[9], secret="LEAKED_bash_and_prompt_body")
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert "LEAKED_bash_and_prompt_body" not in json.dumps(s)
        assert "LEAKED_bash_and_prompt_body" not in V.sessions_html(s)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_footprint_trimmed_to_top_n():
    """A session that edits hundreds of files keeps only the headline few."""
    base, claude, repo, cache = workspace()
    try:
        edits = [os.path.join(repo, f"f{i}.py") for i in range(40)]
        mkfootprint(claude, "-app", "fp000003", repo, edits=edits)
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)[0]
        assert len(s["files"]) == V._FP_FILES
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_footprint_renders_and_pr_links_are_clickable():
    base, claude, repo, cache = workspace()
    try:
        mkfootprint(claude, "-app", "fp000004", repo,
                    edits=[os.path.join(repo, "cli.py")],
                    branches=["main", "b2"], prs=[7])
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        h = V.sessions_html(s)
        assert "cli.py" in h                          # footprint on the page
        assert "2 branches" in h                      # multi-branch collapses
        assert 'href="https://github.com/o/r/pull/7"' in h and "PR #7" in h
        assert 'target="_blank"' in h                 # opens externally
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_read_only_session_has_empty_footprint():
    """A session that edited nothing (a read/plan run) shouldn't invent one —
    the row falls back to showing where it ran."""
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "ro000001", repo)   # no tool_use
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)[0]
        assert s["files"] == [] and s["dirs"] == [] and s["prs"] == []
    finally:
        shutil.rmtree(base, ignore_errors=True)


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


def test_worktree_entered_after_the_first_cwd_is_still_caught():
    """A session's cwd MIGRATES: a real transcript was seen starting in a
    worktree at 05:47 and ending in the parent repo at 23:53. So reading only
    the first cwd makes catching a worktree depend on line ordering — it would
    silently miss any session that entered one after its opening line. Worktrees
    are collected from every cwd, not just the first.
    """
    base, claude, repo, cache = workspace()
    wt = os.path.join(repo, ".claude", "worktrees", "late-arrival")
    os.makedirs(wt)
    try:
        d = os.path.join(claude, "projects", "-app"); os.makedirs(d)
        with open(os.path.join(d, "aaaaaaaa-9.jsonl"), "w") as f:
            # opens in the PARENT — the old first-cwd-only logic stopped here
            f.write(json.dumps({"type": "user", "cwd": repo, "gitBranch": "main",
                                "timestamp": ts(3)}) + "\n")
            # and only later enters the worktree
            f.write(json.dumps({"type": "assistant", "cwd": wt,
                                "timestamp": ts(2)}) + "\n")
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert len(s) == 1
        assert s[0]["repo"] == "app"                       # attribution unchanged
        assert s[0]["worktree"] == os.path.realpath(wt), "missed a late worktree"
        assert s[0]["worktree_live"] is True
        assert "left a worktree" in V.sessions_html(s)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_live_worktree_wins_over_a_cleaned_one():
    """A session may touch several. The one still on disk is the only actionable
    one, so it's the one reported."""
    base, claude, repo, cache = workspace()
    gone = os.path.join(repo, ".claude", "worktrees", "cleaned-up")
    live = os.path.join(repo, ".claude", "worktrees", "still-here")
    os.makedirs(live)
    try:
        d = os.path.join(claude, "projects", "-app"); os.makedirs(d)
        with open(os.path.join(d, "bbbbbbbb-9.jsonl"), "w") as f:
            f.write(json.dumps({"type": "user", "cwd": gone,
                                "timestamp": ts(3)}) + "\n")
            f.write(json.dumps({"type": "assistant", "cwd": live,
                                "timestamp": ts(2)}) + "\n")
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        assert s[0]["worktree"] == os.path.realpath(live)
        assert s[0]["worktree_live"] is True
    finally:
        shutil.rmtree(base, ignore_errors=True)


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


# --- live-process registry + end-session control plane --------------------- #
def _mkreg(claude, sid, pid):
    """Write one ~/.claude/sessions/<pid>.json live-registry entry."""
    d = os.path.join(claude, "sessions")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{pid}.json"), "w") as f:
        json.dump({"pid": pid, "sessionId": sid, "cwd": "/x",
                   "startedAt": 1, "kind": "interactive"}, f)


def _throwaway():
    """A real child process we own — cross-platform (no `sleep` binary needed)."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


def _dead_pid():
    """A pid that is definitely not running: spawn a child, end it, reap it."""
    p = _throwaway()
    p.terminate()
    p.wait()
    return p.pid


def test_live_registry_keeps_alive_drops_dead():
    base = tempfile.mkdtemp()
    claude = os.path.join(base, ".claude")
    try:
        _mkreg(claude, "alive-sid", os.getpid())    # this test process — alive
        _mkreg(claude, "dead-sid", _dead_pid())      # stale file, pid gone
        reg = V._live_registry(claude)
        assert "alive-sid" in reg and reg["alive-sid"]["pid"] == os.getpid()
        assert "dead-sid" not in reg                 # verified against the OS, not trusted
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_end_session_refuses_unregistered_pid():
    base = tempfile.mkdtemp()
    claude = os.path.join(base, ".claude")
    try:
        _mkreg(claude, "sid", _dead_pid())           # registry owns some pid
        other = _dead_pid()                          # a different, unregistered pid
        r = V.end_session(other, claude_dir=claude)  # must be refused, no signal
        assert r["ok"] is False and "no longer running" in r["error"]
        r2 = V.end_session("not-a-number", claude_dir=claude)
        assert r2["ok"] is False and "Invalid" in r2["error"]
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_end_session_terminates_registered_pid():
    base = tempfile.mkdtemp()
    claude = os.path.join(base, ".claude")
    proc = _throwaway()
    try:
        _mkreg(claude, "sid", proc.pid)
        assert V._pid_alive(proc.pid)
        r = V.end_session(proc.pid, claude_dir=claude)
        assert r["ok"] is True, r
        proc.wait(timeout=5)                         # SIGTERM should stop it
        assert proc.poll() is not None and not V._pid_alive(proc.pid)
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        shutil.rmtree(base, ignore_errors=True)


def test_custom_title_becomes_the_session_title():
    """A type:"custom-title" line (which carries no cwd/timestamp/usage) is
    captured and leads the row; the UUID drops to a secondary id — and the
    conversation body still never leaks."""
    base, claude, repo, cache = workspace()
    try:
        d = os.path.join(claude, "projects", "-app")
        os.makedirs(d)
        with open(os.path.join(d, "tt000001.jsonl"), "w") as f:
            f.write(json.dumps({"type": "user", "cwd": repo, "gitBranch": "main",
                                "timestamp": ts(1),
                                "message": {"content": "SECRET_BODY"}}) + "\n")
            f.write(json.dumps({"type": "custom-title", "sessionId": "tt000001",
                                "customTitle": "Fix the checkout bug"}) + "\n")
            f.write(json.dumps({"type": "assistant", "cwd": repo, "timestamp": ts(0),
                                "message": {"content": "SECRET_BODY", "id": "m0",
                                            "usage": {"input_tokens": 1, "output_tokens": 1,
                                                      "cache_creation_input_tokens": 0,
                                                      "cache_read_input_tokens": 0}}}) + "\n")
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)[0]
        assert s["title"] == "Fix the checkout bug"
        h = V.sessions_html([s])
        assert "Fix the checkout bug" in h        # the human title leads the row
        assert "wtsid" in h                       # UUID demoted to secondary id
        assert "SECRET_BODY" not in json.dumps(s) and "SECRET_BODY" not in h
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_session_without_custom_title_falls_back_to_id():
    base, claude, repo, cache = workspace()
    try:
        mktranscript(claude, "-app", "nt000001", repo, hours_ago=0)
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)[0]
        assert s["title"] == ""
        h = V.sessions_html([s])
        assert "nt000001" in h                    # the id still leads
        assert "wtsid" not in h                   # no secondary-id span without a title
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _rec(sid, running, age_min, pid=0, **kw):
    r = {"id": sid, "title": "", "source": "claude", "repo": "app", "cwd": "/r",
         "branch": "main", "branches": [], "files": [], "dirs": [],
         "prs": [], "tools": {}, "started": "", "ended": "",
         "age_min": age_min, "mins": 1, "msgs": 1, "tokens": 10, "worktree": "",
         "worktree_live": False, "active": age_min <= 30, "running": running, "pid": pid}
    r.update(kw)
    return r


def test_html_subtitle_counts_running_not_just_active():
    rows = [_rec("aaaa", True, 2, 111),      # running, live
            _rec("bbbb", True, 200, 222),    # running but quiet -> idle (was invisible
                                             # to the old 'active' count)
            _rec("cccc", False, 5000)]       # finished, in the graveyard
    h = V.sessions_html(rows)
    assert "2 running" in h                  # subtitle counts both live processes
    assert h.count("&#9209; End") == 2       # End control on both running rows
    assert "Live &amp; active" in h and "Repo graveyard" in h
    assert ">live</span>" in h and ">idle</span>" in h   # lifecycle pills, not a flat label


def test_two_sections_split_running_from_done():
    """Running sessions land in Live & active (flat, cross-repo); non-running
    ones in the Repo graveyard grouped by home repo."""
    rows = [_rec("run1", True, 3, 11, repo="alpha"),
            _rec("don1", False, 100, repo="alpha"),
            _rec("don2", False, 200, repo="beta")]
    h = V.sessions_html(rows)
    # graveyard groups by repo → both repo headers present, live section present
    assert "Live &amp; active" in h and "Repo graveyard" in h
    assert h.index("Live &amp; active") < h.index("Repo graveyard")   # order: now → history
    assert ">alpha<" in h and ">beta<" in h            # graveyard repo group headers
    assert 'class="sstate amber"' not in h             # nothing stuck here
    # the running one carries a green (alive) pill; done ones are grey/at-rest
    assert 'class="sstate green"' in h
    # the flat live row states its home repo; graveyard rows (grouped) do not
    assert h.count('class="wtrepo home"') == 1
    assert 'class="wtrepo home">alpha<' in h


def test_pr_overflow_shows_plus_n_more_never_drops():
    """A session with more PRs than fit shows the first _PR_SHOWN inline and a
    "+N more" chip — nothing silently drops off the end (the old prs[:5] bug)."""
    base, claude, repo, cache = workspace()
    try:
        mkfootprint(claude, "-app", "pr000009", repo,
                    edits=[os.path.join(repo, "x.py")], prs=list(range(1, 10)))
        s = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        h = V.sessions_html(s)
        assert h.count('class="wtchip pr"') == V._PR_SHOWN   # exactly 6 clickable chips
        assert "+3 more" in h                                # overflow named, not dropped
        assert "PR #9" in h                                  # the rest live in the hover title
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_scheduled_routines_are_filtered_out():
    """A session whose title matches a configured scheduled-routine slug is a
    routine, not interactive work — dropped from the view (managed in Claude
    Code). A normal session, and one with no title, both stay."""
    base, claude, repo, cache = workspace()
    try:
        os.makedirs(os.path.join(claude, "scheduled-tasks", "fix-article-twice-weekly"))
        d = os.path.join(claude, "projects", "-app")
        os.makedirs(d)

        def tx(sid, title):
            with open(os.path.join(d, f"{sid}.jsonl"), "w") as f:
                f.write(json.dumps({"type": "user", "cwd": repo, "gitBranch": "main",
                                    "timestamp": ts(1), "message": {"content": "x"}}) + "\n")
                if title:
                    f.write(json.dumps({"type": "custom-title", "sessionId": sid,
                                        "customTitle": title}) + "\n")
                f.write(json.dumps({"type": "assistant", "cwd": repo, "timestamp": ts(0),
                                    "message": {"content": "x", "id": sid + "m",
                                                "usage": {"input_tokens": 1, "output_tokens": 1,
                                                          "cache_creation_input_tokens": 0,
                                                          "cache_read_input_tokens": 0}}}) + "\n")
        tx("rout0001", "Fix article twice weekly")   # matches the routine slug -> dropped
        tx("work0001", "Refactor the auth module")   # real interactive work -> kept
        tx("bare0001", "")                            # no title -> never matches -> kept
        secs = V.collect_sessions([("app", repo)], cache, claude_dir=claude)
        titles = {s.get("title") for s in secs}
        assert "Fix article twice weekly" not in titles
        assert "Refactor the auth module" in titles
        assert len(secs) == 2
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_norm_routine_folds_case_and_separators():
    assert V._norm_routine("Fix article twice weekly") == "fix-article-twice-weekly"
    assert V._norm_routine("fix-article-twice-weekly") == "fix-article-twice-weekly"
    assert V._norm_routine("") == ""


def test_cross_repo_prs_are_tagged_and_badged():
    """A session whose PRs land in another repo names that repo — as a badge on
    the row and a tag on the PR chip — so cross-repo work (e.g. #226 in
    wp-diagnostic from a primadigital session) no longer looks misfiled. A PR in
    the home repo stays untagged."""
    base, claude, repo, cache = workspace()
    try:
        d = os.path.join(claude, "projects", "-primadigital")
        os.makedirs(d)
        with open(os.path.join(d, "xr000001.jsonl"), "w") as f:
            f.write(json.dumps({"type": "user", "cwd": repo, "gitBranch": "main",
                                "timestamp": ts(1), "message": {"content": "x"}}) + "\n")
            f.write(json.dumps({"type": "pr-link", "sessionId": "xr000001", "timestamp": ts(0),
                                "prNumber": "10", "prUrl": "https://github.com/me/primadigital/pull/10",
                                "prRepository": "me/primadigital"}) + "\n")
            f.write(json.dumps({"type": "pr-link", "sessionId": "xr000001", "timestamp": ts(0),
                                "prNumber": "226", "prUrl": "https://github.com/me/wp-diagnostic/pull/226",
                                "prRepository": "me/wp-diagnostic"}) + "\n")
        s = V.collect_sessions([("primadigital", repo)], cache, claude_dir=claude)
        h = V.sessions_html(s)
        assert 'class="wtrepo"' in h and "wp-diagnostic" in h   # the other repo is badged
        assert '<span class="rp">wp-diagnostic</span>' in h     # the #226 chip names its repo
        assert '>PR #10 <span class="rp">' not in h             # the home-repo PR stays untagged
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
