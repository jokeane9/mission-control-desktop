#!/usr/bin/env python3
"""orrery CLI tests — arg parsing, data-dir resolution, output contracts.

Three of these pin bugs found by actually running the thing (see #38):
  * `orrery status --json` — --json only existed on the root parser, so it had
    to precede the subcommand. Nobody types `orrery --json status`.
  * `--since today` included yesterday (off-by-one on the cutoff) — a standup
    that's wrong but plausible is worse than one that's obviously broken.
  * piping into `head` raised BrokenPipeError.

Builds a real git repo + a real config in a temp dir. Stdlib only; run:
    python tests/test_cli.py
"""
import io, json, os, shutil, subprocess, sys, tempfile, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import cli
import generate


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True).stdout.strip()


def commit(repo, msg, hours_ago=0):
    """Commit at a controlled time — the standup tests are all about dates."""
    import datetime
    stamp = (datetime.datetime.now()
             - datetime.timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S")
    git(repo, "add", "-A")
    subprocess.run(["git", "-C", repo, "commit", "-qm", msg],
                   env={**os.environ, "GIT_AUTHOR_DATE": stamp,
                        "GIT_COMMITTER_DATE": stamp}, capture_output=True)


def mkworkspace():
    """A temp dir holding: a data dir with baseline.json, and one real repo.

    The seed commit is backdated 10 days on purpose — dated *today* it would
    quietly make "no commits today" impossible to test, and any --since assertion
    would pass for the wrong reason.
    """
    base = tempfile.mkdtemp()
    data = os.path.join(base, "data"); os.makedirs(data)
    repo = os.path.join(base, "app"); os.makedirs(repo)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    open(os.path.join(repo, "README.md"), "w").write("# hi\n")
    commit(repo, "init", hours_ago=24 * 10)
    json.dump({"projects": [{"name": "app", "path": repo, "group": "G"}]},
              open(os.path.join(data, "baseline.json"), "w"))
    return base, data, repo


def run(argv):
    """Invoke the CLI, capturing stdout. Returns (exit_code, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(argv)
    return code, buf.getvalue()


# --- arg parsing ------------------------------------------------------------ #
def test_json_flag_works_after_subcommand():
    """The bug: --json lived only on the root parser, so `orrery status --json`
    — the form everyone actually types — was a parse error.

    It must be True only when asked for: a stray --json that silently defaults
    False would print human text into a pipe, and one that defaults True would
    print escape codes into a parser.
    """
    p = cli.build_parser()
    for sub in ("status", "worktrees", "standup", "skills"):
        assert p.parse_args([sub, "--json"]).json is True, sub
        assert p.parse_args([sub]).json is False, sub


def test_data_flag_after_subcommand():
    p = cli.build_parser()
    assert p.parse_args(["status", "--data", "/tmp/x"]).data == "/tmp/x"


def test_no_command_prints_help_not_a_crash():
    code, o = run([])
    assert code == 0 and "usage" in o.lower()


def test_bad_since_is_rejected():
    try:
        cli.build_parser().parse_args(["standup", "--since", "decade"])
        assert False, "should have rejected an unknown span"
    except SystemExit:
        pass


# --- data dir resolution ---------------------------------------------------- #
def test_env_var_wins():
    """$ORRERY_DATA overrides everything — the escape hatch for a second
    workspace, and what the tests themselves lean on."""
    old = os.environ.get("ORRERY_DATA")
    os.environ["ORRERY_DATA"] = "/tmp/somewhere"
    try:
        assert cli.resolve_data_dir() == "/tmp/somewhere"
    finally:
        os.environ.pop("ORRERY_DATA", None)
        if old:
            os.environ["ORRERY_DATA"] = old


def test_falls_back_to_source_dir_when_app_has_no_config():
    """With no installed app config present, the CLI reads the source tree — the
    dev workflow keeps working."""
    old = os.environ.pop("ORRERY_DATA", None)
    real = generate._app_data_base
    generate._app_data_base = lambda: tempfile.mkdtemp()      # empty → no config
    try:
        assert cli.resolve_data_dir() == generate.DATA
    finally:
        generate._app_data_base = real
        if old:
            os.environ["ORRERY_DATA"] = old


def test_prefers_installed_app_config():
    """The important one: a CLI reporting on a DIFFERENT workspace than the
    window would be worse than no CLI."""
    old = os.environ.pop("ORRERY_DATA", None)
    fake_base = tempfile.mkdtemp()
    appdir = os.path.join(fake_base, generate.APP_NAME)
    os.makedirs(appdir)
    open(os.path.join(appdir, "baseline.json"), "w").write("{}")
    real = generate._app_data_base
    generate._app_data_base = lambda: fake_base
    try:
        assert cli.resolve_data_dir() == appdir
    finally:
        generate._app_data_base = real
        shutil.rmtree(fake_base, ignore_errors=True)
        if old:
            os.environ["ORRERY_DATA"] = old


# --- status ----------------------------------------------------------------- #
def test_status_json_contract():
    base, data, repo = mkworkspace()
    try:
        code, o = run(["status", "--all", "--json", "--data", data])
        d = json.loads(o)                       # must be parseable — it's the API
        assert code == 0
        assert set(d) == {"totals", "projects"}
        assert set(d["totals"]) >= {"dirty", "unmerged", "ahead", "attn"}
        app = next(p for p in d["projects"] if p["name"] == "app")
        assert app["group"] == "G" and app["branch"] == "main"
        assert app["attention"] is False        # clean repo
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_status_clean_says_all_clear():
    base, data, repo = mkworkspace()
    try:
        code, o = run(["status", "--data", data])
        assert code == 0 and "All clear" in o
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_status_flags_dirty_repo():
    base, data, repo = mkworkspace()
    try:
        open(os.path.join(repo, "scratch.txt"), "w").write("x\n")
        code, o = run(["status", "--data", data])
        assert "need" in o and "1 uncommitted" in o
        d = json.loads(run(["status", "--json", "--data", data])[1])
        assert d["totals"]["attn"] == 1 and d["totals"]["dirty"] == 1
        assert d["projects"][0]["attention"] is True
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_strict_exits_nonzero_only_when_attention():
    """`orrery status --strict && deploy` has to stop on unsaved work."""
    base, data, repo = mkworkspace()
    try:
        assert run(["status", "--strict", "--data", data])[0] == 0
        open(os.path.join(repo, "dirty.txt"), "w").write("x\n")
        assert run(["status", "--strict", "--data", data])[0] == 1
        # without --strict it stays 0 — it's a report, not a gate
        assert run(["status", "--data", data])[0] == 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- standup ---------------------------------------------------------------- #
def test_standup_today_excludes_yesterday():
    """The off-by-one: cutoff was now-days, so `--since today` (days=1) reached
    back to YESTERDAY midnight. Spans are calendar days INCLUDING today."""
    base, data, repo = mkworkspace()
    try:
        open(os.path.join(repo, "old.txt"), "w").write("x\n")
        commit(repo, "YESTERDAY_WORK", hours_ago=30)   # yesterday by any reading
        today = run(["standup", "--since", "today", "--data", data])[1]
        assert "YESTERDAY_WORK" not in today
        week = run(["standup", "--since", "week", "--data", data])[1]
        assert "YESTERDAY_WORK" in week          # but the week still sees it
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_standup_empty_is_graceful():
    base, data, repo = mkworkspace()
    try:
        code, o = run(["standup", "--since", "today", "--data", data])
        assert code == 0 and "no commits" in o
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- worktrees -------------------------------------------------------------- #
def test_worktrees_reports_and_verdicts():
    base, data, repo = mkworkspace()
    try:
        code, o = run(["worktrees", "--data", data])
        assert code == 0 and "no extra checkouts" in o
        wt = os.path.join(base, "app-ghost")
        git(repo, "worktree", "add", "-q", "--detach", wt)
        open(os.path.join(wt, "orphan.txt"), "w").write("x\n")
        git(wt, "add", "-A"); git(wt, "commit", "-qm", "unreachable work")
        o = run(["worktrees", "--data", data])[1]
        assert "not on any branch" in o          # the verdict that saves work
        d = json.loads(run(["worktrees", "--json", "--data", data])[1])
        assert len(d) == 1 and d[0]["safe"] is False
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- output hygiene --------------------------------------------------------- #
def test_no_ansi_when_not_a_tty():
    """Piped output must be clean text — tests capture stdout, so _TTY is False
    and there must be no escape codes to break `| grep`."""
    base, data, repo = mkworkspace()
    try:
        o = run(["status", "--all", "--data", data])[1]
        assert "\033[" not in o
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
