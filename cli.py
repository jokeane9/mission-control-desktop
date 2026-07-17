#!/usr/bin/env python3
"""orrery — the dashboard as a command.

    orrery status              what needs you, across every repo
    orrery worktrees           every extra checkout + safe-to-remove verdict
    orrery sessions            Claude Code sessions: live, recent, ghosts
    orrery standup             your recent commits, grouped by day
    orrery skills              the Claude Code skills catalog
    orrery <cmd> --json        the same data, pipeable

Why this exists: the window is not always the right surface. A dashboard you
have to *open* loses to a command you can pipe — and a CLI needs no bundle, no
Gatekeeper, and no notarization to run.

This module is a FORMATTER, deliberately. Every command is a thin renderer over
a collect_*() that already backs the GUI (generate.workspace, views.collect_*).
Logic added here would be logic the GUI can't see and no test covers — if a
command needs new behaviour, it belongs in views.py/generate.py where both
surfaces share it. Stdlib only, offline, like the rest of the engine.
"""
import argparse
import datetime
import json
import os
import sys

import generate
import resolve
import views

# ANSI, but only when we're actually talking to a terminal — piping `orrery
# status` into anything must yield clean text, and NO_COLOR is a convention
# worth honouring. https://no-color.org
_TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if _TTY else s


def red(s):    return _c("31", s)
def green(s):  return _c("32", s)
def amber(s):  return _c("33", s)
def blue(s):   return _c("34", s)
def dim(s):    return _c("2", s)
def bold(s):   return _c("1", s)


def resolve_data_dir():
    """Which config the CLI reads. Running from source, generate.DATA is the
    source tree — but the user's REAL config belongs to the installed app, and a
    CLI that reported on a different workspace than the window would be worse
    than useless. Prefer the installed app's dir when it has a config.

    $ORRERY_DATA overrides everything (testing, or a second workspace).
    """
    env = os.environ.get("ORRERY_DATA")
    if env:
        return os.path.expanduser(env)
    app = os.path.join(generate._app_data_base(), generate.APP_NAME)
    if os.path.isfile(os.path.join(app, "baseline.json")):
        return app
    return generate.DATA


def load(args):
    """(cfg, gh_cache) from the resolved data dir."""
    generate.use_data_dir(args.data or resolve_data_dir())
    cfg = generate.load_config()
    cache = resolve.load_github_cache(os.path.join(generate.DATA,
                                                   "github_cache.json"))
    return cfg, cache


def project_dirs(projects):
    """[(name, path), …] for the cloned projects — the shape views.collect_*
    expects."""
    return [(pr["p"]["name"], pr["path"]) for pr in projects if pr["path"]]


def out(data, args, render):
    """--json prints the raw data; otherwise the human renderer runs."""
    if args.json:
        json.dump(data, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return
    render(data)


# --------------------------------------------------------------------------- #
# status — the attention rollup
# --------------------------------------------------------------------------- #
def _chips(g):
    """The card chips as text, in the same order the GUI shows them."""
    bits = []
    if g.get("uncloned"):
        return [dim("not cloned")]
    if g["dirty"]:
        bits.append(amber(f'{g["dirty"]} uncommitted'))
    if g["ahead"] != "0":
        bits.append(blue(f'{g["ahead"]} unpushed'))
    if g["unmerged"]:
        bits.append(f'{g["unmerged"]} unmerged')
    if g["stashes"]:
        bits.append(f'{g["stashes"]} stashed')
    return bits


def cmd_status(args):
    cfg, cache = load(args)
    projects, totals = generate.workspace(cfg, cache)
    rows = [pr for pr in projects if pr["attn"] or args.all]

    def render(_):
        attn = totals["attn"]
        if attn:
            head = (red(f'⚠ {attn} project{"" if attn == 1 else "s"} need attention')
                    + f' · {totals["dirty"]} uncommitted, {totals["ahead"]} unpushed')
        else:
            head = green("✓ All clear") + dim(f' · {len(projects)} projects')
        print(head)
        if not rows:
            return
        print()
        w = max((len(pr["p"]["name"]) for pr in rows), default=0)
        for pr in rows:
            g, name = pr["g"], pr["p"]["name"]
            mark = red("●") if pr["attn"] else green("●")
            branch = g["branch"] or dim("—")
            chips = "  ".join(_chips(g))
            print(f'{mark} {bold(name.ljust(w))}  {dim(branch[:28].ljust(28))}  {chips}')
        if not args.all and len(projects) > len(rows):
            print(dim(f'\n{len(projects) - len(rows)} clean · --all to show'))

    data = {"totals": totals,
            "projects": [{"name": pr["p"]["name"], "group": pr["p"].get("group", ""),
                          "path": pr["path"], "attention": bool(pr["attn"]),
                          **{k: pr["g"][k] for k in
                             ("branch", "dirty", "ahead", "behind", "unmerged",
                              "stashes", "last_rel", "last_msg")
                             if k in pr["g"]}}
                         for pr in rows]}
    out(data, args, render)
    # Exit 1 when something needs you: `orrery status && deploy` should stop.
    return 1 if totals["attn"] and args.strict else 0


# --------------------------------------------------------------------------- #
# worktrees — the ghost hunt
# --------------------------------------------------------------------------- #
def cmd_worktrees(args):
    cfg, cache = load(args)
    projects, _ = generate.workspace(cfg, cache)
    trees = views.collect_worktrees(project_dirs(projects))

    def render(_):
        if not trees:
            print(green("✓ no extra checkouts") +
                  dim(" — every repo has just its one checkout"))
            return
        risky = [w for w in trees if not w["safe"]]
        print(f'{len(trees)} worktree{"s" if len(trees) != 1 else ""}' +
              (red(f' · {len(risky)} hold unsaved work') if risky
               else green(" · all safe to remove")))
        print()
        cur = None
        for w in trees:
            if w["repo"] != cur:
                cur = w["repo"]
                print(bold(cur))
            branch = "(detached)" if w["detached"] or not w["branch"] else w["branch"]
            age = "—" if w["age_days"] < 0 else f'{w["age_days"]}d'
            verdict = green(w["why"]) if w["safe"] else red(w["why"])
            print(f'  {w["name"][:30].ljust(30)} {dim(branch[:22].ljust(22))} '
                  f'{age.rjust(5)}  {verdict}')
            print(f'  {dim(w["path"])}')
        if risky:
            print(dim(f'\nOnly remove the safe ones:  git -C <repo> worktree remove <path>'))

    out(trees, args, render)
    return 0


# --------------------------------------------------------------------------- #
# standup — what you shipped
# --------------------------------------------------------------------------- #
_SPANS = {"today": 1, "week": 7, "month": 30, "3months": 92}


def cmd_standup(args):
    cfg, cache = load(args)
    projects, _ = generate.workspace(cfg, cache)
    days = _SPANS[args.since]
    commits = views.collect_worklog(project_dirs(projects), days=days)
    # Spans are CALENDAR days including today: "today" = since midnight, "week" =
    # the last 7 days counting today. Hence days-1 — an off-by-one here silently
    # folds yesterday's commits into `--since today`, which is exactly the kind of
    # wrong-but-plausible standup that gets pasted into Slack.
    cutoff = (datetime.datetime.now()
              - datetime.timedelta(days=days - 1)).replace(hour=0, minute=0,
                                                           second=0, microsecond=0)
    commits = [c for c in commits if c["t"] >= cutoff.timestamp()]

    def render(_):
        if not commits:
            print(dim(f"no commits in the last {args.since}"))
            return
        byday = {}
        for c in commits:
            d = datetime.date.fromtimestamp(c["t"]).isoformat()
            byday.setdefault(d, []).append(c)
        n, repos = len(commits), len({c["r"] for c in commits})
        print(dim(f'{n} commit{"s" if n != 1 else ""} across '
                  f'{repos} repo{"s" if repos != 1 else ""} · {args.since}'))
        for day in sorted(byday, reverse=True):
            print(f'\n{bold(day)}')
            for c in byday[day]:
                print(f'  {blue(c["r"][:22].ljust(22))} {c["s"]}')

    out(commits, args, render)
    return 0


# --------------------------------------------------------------------------- #
# sessions — what your agents are doing
# --------------------------------------------------------------------------- #
def cmd_sessions(args):
    cfg, cache = load(args)
    projects, _ = generate.workspace(cfg, cache)
    sessions = views.collect_sessions(
        project_dirs(projects), os.path.join(generate.DATA, "token_cache.json"),
        days=args.days)

    def render(_):
        if not sessions:
            print(dim(f"no Claude Code sessions in the last {args.days} days"))
            return
        live = [s for s in sessions if s["active"]]
        ghosts = [s for s in sessions if s["worktree_live"] and not s["active"]]
        print(f'{len(sessions)} session{"s" if len(sessions) != 1 else ""}'
              + (green(f" · {len(live)} live") if live else "")
              + (amber(f" · {len(ghosts)} left a worktree behind") if ghosts else ""))
        print()
        cur = None
        for s in sessions:
            if s["repo"] != cur:
                cur = s["repo"]
                print(bold(cur))
            mark = green("●") if s["active"] else dim("○")
            when = green("live") if s["active"] else views._ago(s["age_min"])
            bits = [f'{s["msgs"]} msgs', f'{views._knum(s["tokens"])} tok']
            if s["worktree_live"]:
                bits.append(amber("left a worktree"))
            print(f'  {mark} {s["id"]}  {dim((s["branch"] or "—")[:18].ljust(18))} '
                  f'{when.rjust(8)}  {dim(" · ".join(bits))}')
        if ghosts:
            print(dim("\nSessions that left a worktree ended without cleaning up — "
                      "see `orrery worktrees`."))

    out(sessions, args, render)
    return 0


# --------------------------------------------------------------------------- #
# skills — the catalog
# --------------------------------------------------------------------------- #
def cmd_skills(args):
    cfg, cache = load(args)
    projects, _ = generate.workspace(cfg, cache)
    grouped = views.collect_skills(project_dirs(projects))
    if args.search:
        q = args.search.lower()
        grouped = [(label, [s for s in entries
                            if q in s["name"].lower() or q in s["desc"].lower()])
                   for label, entries in grouped]
        grouped = [(l, e) for l, e in grouped if e]

    def render(_):
        total = sum(len(e) for _, e in grouped)
        if not total:
            print(dim("no skills found"))
            return
        print(dim(f"{total} skills"))
        for label, entries in grouped:
            print(f'\n{bold(label)} {dim(f"({len(entries)})")}')
            w = max((len(s["name"]) for s in entries), default=0)
            for s in entries:
                print(f'  {s["name"].ljust(w)}  {dim(s["desc"][:70])}')

    out([{"group": l, "skills": e} for l, e in grouped], args, render)
    return 0


# --------------------------------------------------------------------------- #
def build_parser():
    # --json/--data are declared on each SUBCOMMAND, not the root, because that's
    # the form people type: `orrery status --json`. Declaring them in both places
    # doesn't work — argparse parses a subcommand into a fresh namespace and
    # copies it over the root's, so an unset store_true silently overwrites the
    # root's True and `orrery --json status` prints human text into your pipe.
    # One place, no ambiguity: `orrery --json status` is a clean parse error.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", metavar="DIR",
                        help="config dir (default: the installed app's config)")
    common.add_argument("--json", action="store_true",
                        help="machine-readable output")

    p = argparse.ArgumentParser(
        prog="orrery",
        description="Every project's live state, from the terminal.")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("status", parents=[common],
                       help="what needs you, across every repo")
    s.add_argument("--all", action="store_true", help="include clean projects")
    s.add_argument("--strict", action="store_true",
                   help="exit 1 if any project needs attention")
    s.set_defaults(fn=cmd_status)

    w = sub.add_parser("worktrees", parents=[common],
                       help="extra checkouts + safe-to-remove verdicts")
    w.set_defaults(fn=cmd_worktrees)

    d = sub.add_parser("standup", parents=[common],
                       help="your recent commits, by day")
    d.add_argument("--since", choices=sorted(_SPANS), default="week")
    d.set_defaults(fn=cmd_standup)

    e = sub.add_parser("sessions", parents=[common],
                       help="Claude Code sessions: live, recent, and what they left")
    e.add_argument("--days", type=int, default=views.SESSIONS_DAYS,
                   help=f"history window (default {views.SESSIONS_DAYS})")
    e.set_defaults(fn=cmd_sessions)

    k = sub.add_parser("skills", parents=[common],
                       help="the Claude Code skills catalog")
    k.add_argument("search", nargs="?", help="filter by name/description")
    k.set_defaults(fn=cmd_skills)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 0
    try:
        return args.fn(args)
    except BrokenPipeError:                  # `orrery status | head` — not an error
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
