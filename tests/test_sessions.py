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
