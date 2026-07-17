#!/usr/bin/env python3
"""Orrery — one dark shell, every project's live state + maps.
Usage: ./generate.py [--open] [--watch]   (stdlib only, no deps)
Git data live from each repo · human facts from baseline.json · maps via vizstack/agentviz.
Design language matches codebase-viz/vizstack (GitHub-dark, SF Mono).
"""
import json, subprocess, os, sys, html, datetime, time, shutil, webbrowser
from pathlib import Path
import resolve  # sibling: discover() + resolve() — offline auto-populate (P1)
import views    # sibling: top-level views (Skills catalog, …)

APP_NAME = "Orrery"
LEGACY_APP_NAME = "Mission Control"     # pre-2.0 name; see _migrate_data_dir()
FROZEN = getattr(sys, "frozen", False)          # True inside a PyInstaller build
HERE = (os.path.dirname(os.path.abspath(sys.executable)) if FROZEN
        else os.path.dirname(os.path.abspath(__file__)))
REFRESH_MIN = 15
VIZ_MAX_AGE_H = 6
MOD = "⌘" if sys.platform == "darwin" else "Ctrl+"   # shortcut label


def resource_path(name):
    """Bundled read-only resource (sample config, icon)."""
    base = getattr(sys, "_MEIPASS", HERE)
    return os.path.join(base, name)


def _app_data_base():
    """The OS's per-user app-data root."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    if os.name == "nt":
        return os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))


def _migrate_data_dir(base, new):
    """v2.0.0 renamed the app, and the data dir is keyed off the name — so an
    upgrading user's config would sit orphaned under the old one and the app
    would open empty, looking like it lost their work. Move it across, once.

    Only fires when the new dir doesn't exist yet and the old one does, so it
    can never clobber newer data. Copy-then-leave rather than move: if anything
    here fails, the old dir is still intact and the user can be pointed at it.
    Best-effort by design — a failed migration must not stop the app booting.
    Removal criterion: drop this once no supported version predates 2.0.0."""
    old = os.path.join(base, LEGACY_APP_NAME)
    if os.path.exists(new) or not os.path.isdir(old):
        return False
    try:
        shutil.copytree(old, new)
        return True
    except Exception as e:                       # never fatal: a fresh dir works
        print(f"[{APP_NAME}] could not migrate config from {old}: {e}",
              file=sys.stderr)
        try:
            os.makedirs(new, exist_ok=True)
        except OSError:
            pass
        return False


def _data_dir():
    """Where config + generated output live. Running from source: next to the
    script (unchanged dev workflow). Installed app: per-user app-data dir,
    because the bundle itself is read-only once signed/installed."""
    if not FROZEN:
        return HERE
    base = _app_data_base()
    d = os.path.join(base, APP_NAME)
    _migrate_data_dir(base, d)                   # pre-2.0 config, if any
    os.makedirs(d, exist_ok=True)
    return d


DATA = _data_dir()
BASELINE = os.path.join(DATA, "baseline.json")
INDEX = os.path.join(DATA, "index.html")
NOTES = os.path.join(DATA, "pm_notes.md")   # PM scratchpad — local, gitignored


# The editable per-project fields, in form order. Single source of truth: the
# in-app editor form is generated from this list. (key, label, placeholder,
# required). Fields not listed here — e.g. viz_app/viz_pipeline — are preserved
# on edit but not shown in the form.
PROJECT_FIELDS = [
    ("name",     "Name",      "short-name",                        True),
    ("path",     "Path",      "~/code/my-app  (a local git repo)", True),
    ("tier",     "Tier",      "major / tools / minor",             False),
    ("group",    "Group",     "sidebar group (blank = auto-organize)", False),
    ("thesis",   "Thesis",    "one line: what this project is",    False),
    ("prod",     "Prod URL",  "https://example.com",               False),
    ("prod_note","Prod note", "hosting · rough monthly cost",      False),
    ("stack",    "Stack",     "Remix + Postgres",                  False),
    ("dev",      "Dev",       "how you run it locally",            False),
    ("prod_env", "Prod env",  "how production is deployed",        False),
    ("arch",     "Arch doc",  "README.md",                         False),
    ("email",    "Accounts",  "domains / logins (optional)",       False),
    ("focus",    "Focus",     "the one thing you're pushing on",   False),
]


def load_config():
    """Read baseline.json; on first run of an installed app, seed it from the
    bundled sample so the dashboard opens with instructions, not an error."""
    if not os.path.isfile(BASELINE):
        sample = resource_path("baseline.sample.json")
        if os.path.isfile(sample):
            shutil.copy(sample, BASELINE)
        else:
            json.dump({"projects": []}, open(BASELINE, "w"), indent=2)
    return json.load(open(BASELINE))


def save_config(cfg):
    """Write baseline.json back (pretty, atomic-ish via a temp file + replace)."""
    tmp = BASELINE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, BASELINE)


def upsert_project(project, original=None):
    """Add or update one project from the editor. Merges onto any existing
    record (so fields not in the form — viz_app etc. — survive). `original` is
    the name before an edit, so a rename replaces rather than duplicates.
    Returns (ok, error_message)."""
    name = (project.get("name") or "").strip()
    if not name:
        return False, "Name is required."
    if not (project.get("path") or "").strip():
        return False, "Path is required."
    cfg = load_config()
    projects = cfg.setdefault("projects", [])
    key = original or name
    idx = next((i for i, p in enumerate(projects) if p.get("name") == key), None)
    # block a rename/add that collides with a different existing project
    clash = next((i for i, p in enumerate(projects)
                  if p.get("name") == name and i != idx), None)
    if clash is not None:
        return False, f"A project named “{name}” already exists."
    clean = {k: v for k, v in project.items() if str(v).strip() != ""}
    if idx is not None:
        projects[idx] = {**projects[idx], **clean}
    else:
        projects.append(clean)
    save_config(cfg)
    return True, ""


def delete_project(name):
    """Remove a project by name. Returns True if something was removed."""
    cfg = load_config()
    before = len(cfg.get("projects", []))
    cfg["projects"] = [p for p in cfg.get("projects", []) if p.get("name") != name]
    save_config(cfg)
    return len(cfg["projects"]) < before

def git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo] + list(args),
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""

def default_branch(repo):
    ref = git(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    if ref:
        return ref.rsplit("/", 1)[-1]
    for b in ("main", "master"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{b}"):
            return b
    return ""

def collect(repo):
    d = {}
    d["branch"] = git(repo, "branch", "--show-current") or "(detached)"
    status = git(repo, "status", "--short")
    d["dirty"] = len([l for l in status.splitlines() if l.strip()])
    d["last_rel"] = git(repo, "log", "-1", "--format=%cr")
    d["last_msg"] = git(repo, "log", "-1", "--format=%s")[:72]
    ab = git(repo, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    d["behind"], d["ahead"] = (ab.split() + ["0", "0"])[:2] if ab else ("0", "0")
    base = default_branch(repo)
    # LOCAL branches not merged into the default branch — your own work in
    # progress. Not `-r`: remote branches are every open PR in the repo, so a
    # project cloned to read (langflow: 1884, dspy: 366) would read as "needs
    # attention" forever. You can't merge a branch you never checked out; the
    # ones you can are local. (HEAD guard covers the detached-HEAD placeholder.)
    unmerged = git(repo, "branch", "--no-merged", base) if base else ""
    d["unmerged"] = len([l for l in unmerged.splitlines()
                         if l.strip() and "HEAD" not in l])
    d["stashes"] = len(git(repo, "stash", "list").splitlines())
    return d

def arch_outline(path, arch_rel, limit=4):
    if not arch_rel:
        return ""
    f = os.path.join(path, arch_rel)
    if not os.path.isfile(f):
        return ""
    heads = []
    try:
        for line in open(f, encoding="utf-8", errors="ignore"):
            if line.startswith("## ") and not line.startswith("###"):
                h = line[3:].strip().lstrip("0123456789. ")
                if h:
                    heads.append(h)
            if len(heads) >= limit:
                break
    except Exception:
        return ""
    return " · ".join(heads)

def detect_viz_app(path):
    """vizstack maps Remix/Next apps. Detect one cheaply from package.json deps
    or a routes dir; return '.' (the app root) or None."""
    pj = os.path.join(path, "package.json")
    if os.path.isfile(pj):
        try:
            d = json.load(open(pj, encoding="utf-8"))
            deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
            if any(k == "next" or k == "remix" or k.startswith("@remix-run/")
                   for k in deps):
                return "."
        except Exception:
            pass
    if os.path.isdir(os.path.join(path, "app", "routes")):   # Remix convention
        return "."
    return None


def detect_viz_pipeline(path):
    """agentviz maps Python LLM/agent pipelines. Detect one from dep manifests
    mentioning an LLM SDK; return '.' or None."""
    for f in ("requirements.txt", "pyproject.toml", "setup.py"):
        p = os.path.join(path, f)
        if os.path.isfile(p):
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read().lower()
                if any(s in txt for s in ("openai", "anthropic", "langchain")):
                    return "."
            except Exception:
                pass
    return None


def _viz_plan(path, p, cfg_tools, auto):
    """Which viz tools to run: {kind: (cmd, target)}. A target comes from explicit
    config (viz_app/viz_pipeline) or, when `auto`, from detection. Tools absent
    from `cfg_tools` or missing on disk are skipped."""
    plan = {}
    vizstack = os.path.expanduser(cfg_tools.get("vizstack", ""))
    if vizstack and os.path.isfile(vizstack):
        target = p.get("viz_app") or (detect_viz_app(path) if auto else None)
        if target:
            plan["app"] = (["node", vizstack], target)
    agentviz = os.path.expanduser(cfg_tools.get("agentviz", ""))
    if agentviz and os.path.isfile(agentviz):
        target = p.get("viz_pipeline") or (detect_viz_pipeline(path) if auto else None)
        if target:
            py = shutil.which("python3") or shutil.which("python") or "python3"
            plan["pipeline"] = ([py, agentviz], target)
    return plan


def build_viz(name, path, p, cfg_tools, auto=False):
    """Architecture/pipeline map tabs. Targets are explicit (viz_app/viz_pipeline)
    or auto-detected when `auto` is on; users without the tools get no map tabs."""
    links = []
    os.makedirs(os.path.join(DATA, "viz"), exist_ok=True)
    for kind, (cmd, target) in _viz_plan(path, p, cfg_tools, auto).items():
        out = os.path.join(DATA, "viz", f"{name}-{kind}.html")
        stale = (not os.path.isfile(out)
                 or time.time() - os.path.getmtime(out) > VIZ_MAX_AGE_H * 3600)
        if stale:
            try:
                subprocess.run(cmd + [os.path.join(path, target), out],
                               capture_output=True, timeout=90)
            except Exception:
                pass
        if os.path.isfile(out):
            label = "architecture" if kind == "app" else "pipeline"
            links.append((label, f"viz/{name}-{kind}.html"))
    return links

# Stand-in git state for an uncloned GitHub repo (no local checkout to scan).
GIT_UNCLONED = {"branch": "", "dirty": 0, "last_rel": "", "last_msg": "",
                "behind": "0", "ahead": "0", "unmerged": 0, "stashes": 0,
                "uncloned": True}


def chips(g):
    if g.get("uncloned"):
        return '<span class="chip">not cloned</span>'
    def c(text, kind=""):
        return f'<span class="chip {kind}">{html.escape(str(text))}</span>'
    out = [c(g["branch"], "blue" if g["branch"] not in ("main", "master") else "")]
    out.append(c(f'{g["dirty"]} uncommitted', "amber") if g["dirty"] else c("clean", "green"))
    if g["unmerged"]:
        out.append(c(f'{g["unmerged"]} unmerged', "amber"))
    if g["stashes"]:
        out.append(c(f'{g["stashes"]} stash', "amber"))
    if g["ahead"] != "0":
        out.append(c(f'↑{g["ahead"]} ahead', "amber"))
    if g["behind"] != "0":
        out.append(c(f'↓{g["behind"]} behind', "blue"))
    return "".join(out)

# Provenance badge labels: (visible text, tooltip). Heuristic values are marked
# "guess" in amber to signal they were inferred from prose, not stated.
_PROV_LABEL = {
    "block":     ("auto",  "from a .orrery / CLAUDE.md block"),
    "metadata":  ("auto",  "from package.json / git remote"),
    "heuristic": ("guess", "guessed from CLAUDE.md / README prose"),
    "computed":  ("auto",  "derived (e.g. the folder name)"),
    "github":    ("auto",  "from GitHub"),
}


def prov_mark(prov, key):
    """A small 'auto'/'guess' badge for an auto-derived field. Empty for a manual
    override or when provenance is unavailable — so overridden fields read plain."""
    src = (prov or {}).get(key)
    if not src or src == "overrides":
        return ""
    label, tip = _PROV_LABEL.get(src, ("auto", "auto-filled"))
    cls = "prov guess" if src == "heuristic" else "prov"
    return f'<span class="{cls}" title="{html.escape(tip)}">{label}</span>'


def rows_html(p, g, path, prov=None):
    esc = html.escape
    def row(label, val, key=None):
        if not val:
            return ""
        mark = prov_mark(prov, key) if key else ""
        return (f'<div class="row"><span class="lbl">{label}</span>'
                f'<span class="val">{val}{mark}</span></div>')
    prod, prod_note = p.get("prod", ""), p.get("prod_note", "")
    if prod:
        site = f'<a href="{esc(prod)}" target="_blank">{esc(prod.replace("https://",""))}</a>'
        if prod_note:
            site += f' <span class="sub">· {esc(prod_note)}</span>'
    else:
        site = f'<span class="sub">{esc(prod_note or "—")}</span>'
    arch_rel = p.get("arch", "")
    arch = (f'<a href="{esc(Path(path, arch_rel).as_uri())}">{esc(arch_rel)}</a>'
            if arch_rel else "")
    outline = arch_outline(path, arch_rel)
    archval = f'{esc(outline)} <span class="sub">·</span> {arch}' if outline and arch else arch
    focus = p.get("focus", "")
    return (row("Site", site, "prod")
            + (row("Email", esc(p.get("email", "")), "email") if p.get("email") else "")
            + row("Dev", esc(p.get("dev", "")), "dev")
            + row("Prod", esc(p.get("prod_env", "")), "prod_env")
            + row("Stack", esc(p.get("stack", "")), "stack")
            + row("Arch", archval, "arch")
            + (row("GitHub", f'<a href="{esc(p["github_url"])}" target="_blank">'
                             f'{esc(p["github_url"].replace("https://", ""))}</a>')
               if p.get("github_url") else "")
            + row("Last", f'<span class="sub">{esc(g["last_msg"])}</span>')
            + (f'<div class="focus">{row("Focus", esc(focus), "focus")}</div>' if focus else ""))


def group_slug(s):
    """Stable id for a group name (shared by the sidebar header and card filter)."""
    return "".join(c if c.isalnum() else "-" for c in (s or "").lower()).strip("-") or "x"


_TIER_RANK = {"major": 0, "tools": 1, "minor": 2}


def use_data_dir(path):
    """Re-point the module at another data dir. BASELINE/INDEX/NOTES are derived
    from DATA at import, so setting DATA alone would desync them. The CLI uses
    this to read the *installed app's* config instead of the source tree's."""
    global DATA, BASELINE, INDEX, NOTES
    DATA = path
    BASELINE = os.path.join(DATA, "baseline.json")
    INDEX = os.path.join(DATA, "index.html")
    NOTES = os.path.join(DATA, "pm_notes.md")


def workspace(cfg, gh_cache=None, with_maps=False):
    """(projects, totals) — every non-hidden project, resolved, triage-sorted,
    with the attention rollup. The single source of truth for "what needs you":
    the HTML render and the CLI both call this, so they can never disagree about
    which repos need you or what the totals are.

    `with_maps` is the GUI-only viz step — it shells out to node/python per repo,
    so the CLI leaves it off and stays fast.
    """
    gh_cache = gh_cache or {}
    projects, totals = [], {"dirty": 0, "unmerged": 0, "ahead": 0, "attn": 0}
    # Discover repos (baseline + scanned `roots` + synced GitHub) and resolve each
    # card's facts from layered sources. Explicit values always win.
    auto = bool(cfg.get("roots"))   # local auto-fill is opt-in: only when roots is set
    for repo in resolve.discover(cfg, gh_cache):
        path = repo.get("path")
        facts, prov = resolve.resolve(repo, cfg, auto=auto, cache=gh_cache)
        if facts.get("hidden"):
            continue
        if path:
            g = collect(path)
            maps = (build_viz(facts["name"], path, facts, cfg.get("tools", {}),
                              auto=auto) if with_maps else [])
        else:                                           # uncloned GitHub repo
            g = dict(GIT_UNCLONED)
            maps = []
        attn = (not g.get("uncloned")
                and (g["dirty"] or g["unmerged"] or g["stashes"] or g["ahead"] != "0"))
        totals["dirty"] += g["dirty"]; totals["unmerged"] += g["unmerged"]
        totals["ahead"] += int(g["ahead"]) if g["ahead"].isdigit() else 0
        totals["attn"] += 1 if attn else 0
        projects.append({"p": facts, "g": g, "maps": maps, "path": path,
                         "attn": attn, "prov": prov})

    # Auto-organize: infer a sidebar group for any project the user hasn't
    # grouped by hand. Manual groups (resolved above) always win.
    autog = resolve.auto_groups([pr["p"] for pr in projects])
    for pr in projects:
        grp = autog.get(pr["p"]["name"])
        if grp:
            pr["p"]["group"] = grp
            pr["prov"]["group"] = "heuristic"

    # Triage order: needs-attention first, then by tier (major > tools > minor),
    # stable within — so the overview grid and each sidebar group read top-down
    # by urgency instead of raw discovery order.
    projects.sort(key=lambda pr: (not pr["attn"],
                                  _TIER_RANK.get((pr["p"].get("tier") or "").lower(), 3)))
    return projects, totals


def main():
    cfg = load_config()
    # Read-only cache written out-of-band by github_sync.py (P3.2). {} if not
    # synced — GitHub work never happens in the render path.
    gh_cache = resolve.load_github_cache(os.path.join(DATA, "github_cache.json"))
    projects, totals = workspace(cfg, gh_cache, with_maps=True)

    esc = html.escape
    side, cards, details = [], [], []
    for i, pr in enumerate(projects):
        p, g, maps = pr["p"], pr["g"], pr["maps"]
        n = esc(p["name"])
        dot = f'<span class="dot amber"></span>' if pr["attn"] else '<span class="dot green"></span>'
        badge = f'<span class="scount">{g["dirty"]}</span>' if g["dirty"] else ""
        # inner content only; the ⌘ key + wrapper are added after grouping, so
        # the shortcut number follows the final (grouped) sidebar order
        pr["sinner"] = f'{dot}<span class="sname">{n}</span>{badge}'
        accent = ' accent' if pr["attn"] else ""
        gslug = group_slug(p.get("group") or "other")
        # blank thesis on an auto-discovered repo → fall back to the last commit
        blurb = esc(p.get("thesis") or g.get("last_msg") or "")
        cards.append(f'''<div class="card{accent}" data-group="{gslug}" data-proj="{n}" tabindex="0" role="button" onclick="nav('{n}')">
  <div class="ctop"><span class="cname">{n}</span><span class="age">{esc(g["last_rel"] or "")}</span></div>
  <div class="thesis">{blurb}</div>
  <div class="chips">{chips(g)}</div>
</div>''')
        tabs = ['<span class="tab on" onclick="tab(this,null)">overview</span>']
        panes = [f'<div class="pane on"><div class="dcard">'
                 f'<div class="chips" style="margin-bottom:10px">{chips(g)}</div>'
                 f'{rows_html(p, g, pr["path"], pr["prov"])}</div></div>']
        for label, url in maps:
            tabs.append(f'<span class="tab" onclick="tab(this,\'{esc(url)}\')">{esc(label)} map</span>')
            panes.append('<div class="pane"><iframe data-src="' + esc(url) + '"></iframe></div>')
        if pr["path"]:                              # cloned repo → edit/delete
            dbtns = (f'<button class="dbtn" onclick="openEditor(\'{n}\')">Edit</button>'
                     f'<button class="dbtn danger" onclick="removeProject(\'{n}\')">Delete</button>')
        else:                                       # uncloned GitHub repo → clone
            cu = esc(p.get("clone_url", ""))
            dbtns = f'<button class="dbtn" onclick="ghClone(\'{cu}\')">Clone</button>' if cu else ""
        details.append(f'''<div class="view" id="v-{n}">
  <div class="dhead"><span class="dname">{n}</span><span class="dthesis">{esc(p.get("thesis", ""))}{prov_mark(pr["prov"], "thesis")}</span>
    <span class="dbtns editonly">{dbtns}</span></div>
  <div class="tabs">{"".join(tabs)}</div>
  {"".join(panes)}
</div>''')

    # --- grouped, collapsible sidebar (auto-organized; Ungrouped last). The ⌘
    # shortcut number and NAMES follow the final flattened sidebar order. ---
    gorder, groups = [], {}
    for pr in projects:
        key = (pr["p"].get("group") or "").strip()
        if key not in groups:
            groups[key] = []
            gorder.append(key)
        groups[key].append(pr)
    gorder = [k for k in gorder if k] + ([""] if "" in groups else [])  # ungrouped last
    has_groups = any(gorder)                                            # any named group
    flat = [pr for key in gorder for pr in groups[key]]
    for idx, pr in enumerate(flat):
        fn = esc(pr["p"]["name"])
        skey = f'<span class="skey">⌘{idx + 1}</span>' if idx < 9 else ""
        pr["sitem"] = (f'<div class="sitem" id="s-{fn}" tabindex="0" role="button" '
                       f'draggable="true" data-proj="{fn}" onclick="nav(\'{fn}\')">'
                       f'{pr["sinner"]}{skey}</div>')
    if not has_groups:
        side = [pr["sitem"] for pr in flat]            # flat list, unchanged behaviour
    else:
        blocks = []
        for key in gorder:
            label = "Other" if key == "" else key
            gid = group_slug(label)
            body = "".join(pr["sitem"] for pr in groups[key])
            # rollup: a collapsed group still signals it holds a repo needing you
            attn_dot = ('<span class="dot amber gattn" title="a project here needs you"></span>'
                        if any(pr["attn"] for pr in groups[key]) else "")
            blocks.append(
                f'<div class="sgroup" data-gid="{gid}">'
                f'<div class="sgrouphd" id="ghd-{gid}" draggable="true" role="button" '
                f'tabindex="0" onclick="openFolder(\'{gid}\',this)">'
                f'<span class="chev" title="collapse" '
                f'onclick="event.stopPropagation();toggleGroup(\'{gid}\')">▾</span>'
                f'<span class="gname">{esc(label)}</span>{attn_dot}'
                f'<span class="gcount">{len(groups[key])}</span></div>'
                f'<div class="sgroupbody" id="g-{gid}">{body}</div></div>')
        side = ['<div id="sidegroups">' + "".join(blocks) + '</div>']
    flat_names = [pr["p"]["name"] for pr in flat]

    if not projects:
        cards.append(
            '<div class="card" style="cursor:default"><div class="ctop">'
            '<span class="cname">No projects yet</span></div>'
            '<div class="thesis">Click <b>＋ Add project</b> in the sidebar, or add '
            'a folder to scan under <code>"roots"</code> in the config to '
            f'auto-discover repos:<br><code style="font-size:11px">{esc(BASELINE)}'
            '</code></div></div>')

    # Top-level views (sidebar items above the project list, like overview).
    project_dirs = [(pr["p"]["name"], pr["path"]) for pr in projects if pr["path"]]
    top_side, top_views = [], []

    def top_view(vid, label, body):
        top_side.append(f'<div class="sitem" id="s-{vid}" onclick="nav(\'{vid}\')">'
                        f'<span class="dot dim"></span><span class="sname">{label}</span></div>')
        top_views.append(f'<div class="view" id="v-{vid}">{body}</div>')

    top_view("skills", "skills",
             views.skills_html(views.collect_skills(project_dirs)))
    worklog = views.collect_worklog(project_dirs)
    tokens = views.collect_tokens(os.path.join(DATA, "token_cache.json"))
    top_view("worklog", "work log", views.worklog_html(worklog, tokens))
    top_view("roadmap", "roadmap",
             views.roadmaps_html(views.collect_roadmaps(project_dirs)))
    worktrees = views.collect_worktrees(project_dirs)
    top_view("worktrees", "worktrees", views.worktrees_html(worktrees))
    # Same token_cache.json the Work Log uses: one parse of the transcripts feeds
    # both views, so the second one is nearly free.
    top_view("sessions", "sessions",
             views.sessions_html(views.collect_sessions(
                 project_dirs, os.path.join(DATA, "token_cache.json"))))
    top_view("pm", "pm", views.notes_html(views.load_notes(NOTES)))

    now_dt = datetime.datetime.now()
    now = now_dt.strftime("%a %b %d · %H:%M")
    stats = (f'Projects <b>{len(projects)}</b> · Needs attention <b>{totals["attn"]}</b> · '
             f'Uncommitted <b>{totals["dirty"]}</b> · Unmerged branches <b>{totals["unmerged"]}</b> · '
             f'Unpushed <b>{totals["ahead"]}</b>')

    tpl = """<!doctype html><html><head><meta charset="utf-8">
<title>Orrery</title>
<!-- periodic reload is JS-driven (mcReload) so it can defer while the PM scratchpad has unsaved edits -->
<style>
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2129;--border:#21262d;--border2:#30363d;
  --ink:#c9d1d9;--muted:#8b949e;--faint:#868f9c;--faintline:#6e7681;--blue:#58a6ff;--green:#3fb950;--amber:#d29922;
  --mono:'SF Mono','Fira Code','Cascadia Code',Consolas,ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
/* keyboard focus is visible everywhere; mouse users never see it */
:focus-visible{outline:2px solid var(--blue);outline-offset:2px;border-radius:4px}
[tabindex],.sitem,.tab,.card,.fbtn,.sgrouphd,.crumblink{cursor:pointer}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
/* dark, muted scrollbars — the default WebKit ones render bright against the theme */
::-webkit-scrollbar{width:11px;height:11px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:7px;
  border:3px solid transparent;background-clip:padding-box}
::-webkit-scrollbar-thumb:hover{background:var(--faint)}
::-webkit-scrollbar-corner{background:transparent}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--mono);font-size:13px;
  -webkit-font-smoothing:antialiased;height:100vh;display:flex;flex-direction:column;overflow:hidden}
.app{flex:1;display:flex;min-height:0}
.side{width:212px;flex:none;border-right:1px solid var(--border);padding:14px 0;overflow-y:auto;background:#0f1319}
.brand{font-size:12px;font-weight:700;color:var(--blue);padding:2px 16px 12px;letter-spacing:.02em}
.shead{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);
  padding:10px 16px 6px}
.sitem{display:flex;align-items:center;gap:8px;padding:6px 16px;cursor:pointer;color:var(--muted)}
.sitem:hover{background:var(--panel);color:var(--ink)}
.sitem.on{background:var(--panel2);color:var(--ink);box-shadow:inset 2px 0 0 var(--blue)}
.sname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dot{width:6px;height:6px;border-radius:50%;flex:none}
.dot.green{background:var(--green)}.dot.amber{background:var(--amber)}.dot.dim{background:var(--border2)}
.scount{font-size:10px;color:var(--amber);border:1px solid #4d3800;background:#2a2100;
  border-radius:8px;padding:0 6px}
.skey{font-size:9px;color:var(--faint)}
.main{flex:1;display:flex;flex-direction:column;min-width:0}
.view{display:none;flex:1;min-height:0;flex-direction:column;overflow-y:auto;padding:20px 24px}
.view.on{display:flex}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;align-content:start}
.card{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:14px 16px;cursor:pointer}
.card:hover{border-color:var(--border2);background:var(--panel2)}
.card.accent{box-shadow:inset 3px 0 0 var(--amber);background:linear-gradient(90deg,rgba(210,153,34,.06),transparent 40%)}
.ctop{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.cname{font-weight:700;color:var(--blue)}
.age{font-size:10px;color:var(--faint);white-space:nowrap}
.thesis{font-size:11px;color:var(--muted);margin:5px 0 10px;line-height:1.5;
  font-family:-apple-system,'Segoe UI','Helvetica Neue',sans-serif}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  border-radius:4px;padding:2px 7px;background:#21262d;color:var(--muted)}
.chip.blue{background:#1a2a3a;color:var(--blue)}
.chip.green{background:#12261e;color:var(--green)}
.chip.amber{background:#2a2100;color:var(--amber)}
.dhead{display:flex;align-items:baseline;gap:14px;margin-bottom:12px}
.dname{font-size:16px;font-weight:700;color:var(--blue)}
.dthesis{font-size:12px;color:var(--muted);font-family:-apple-system,'Segoe UI','Helvetica Neue',sans-serif}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:14px}
.tab{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);
  padding:7px 12px;cursor:pointer;border-bottom:2px solid transparent}
.tab:hover{color:var(--ink)}
.tab.on{color:var(--blue);border-bottom-color:var(--blue)}
.pane{display:none;flex:1;min-height:0}
.pane.on{display:flex;flex-direction:column}
.pane iframe{flex:1;min-height:70vh;width:100%;border:1px solid var(--border);border-radius:8px;background:var(--bg)}
.dcard{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px 18px;max-width:760px}
.row{display:flex;gap:12px;margin-top:8px;font-size:12px;line-height:1.5}
.lbl{flex:0 0 46px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;
  color:var(--faint);padding-top:3px}
.val{flex:1;min-width:0;font-family:-apple-system,'Segoe UI','Helvetica Neue',sans-serif;font-size:12.5px}
.val a{color:var(--blue);text-decoration:none}
.val a:hover{text-decoration:underline}
.prov{font-size:8px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;font-family:var(--mono);
  color:var(--faint);border:1px solid var(--border2);border-radius:3px;padding:0 4px;margin-left:6px;
  vertical-align:1px;cursor:default}
.prov.guess{color:var(--amber);border-color:#4d3800}
.sub{color:var(--muted)}
.focus{margin-top:10px;border-top:1px solid var(--border);padding-top:4px}
/* --- top-level views (Skills, …) --- */
.vsearch{width:100%;max-width:520px;font:inherit;font-size:12.5px;color:var(--ink);
  background:var(--panel);border:1px solid var(--border2);border-radius:6px;
  padding:7px 10px;margin-bottom:14px}
.vsearch:focus{outline:none;border-color:var(--blue)}
.vsearch::placeholder{color:var(--faint)}
.vempty{color:var(--muted);font-size:12px}
.sgroup{background:var(--panel);border:1px solid var(--border);border-radius:8px;
  padding:10px 14px;margin-bottom:12px;max-width:980px}
.sgtitle{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--faint);padding:2px 0 6px;display:flex;align-items:center;gap:8px}
.sgcount{font-size:9px;color:var(--muted);border:1px solid var(--border2);
  border-radius:8px;padding:0 6px}
.skrow{display:flex;gap:12px;align-items:baseline;padding:5px 0;border-top:1px solid var(--border)}
.skname{flex:0 0 230px;color:var(--blue);font-weight:700;font-size:12px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.skdesc{flex:1;min-width:0;color:var(--muted);font-size:11.5px;
  font-family:-apple-system,'Segoe UI','Helvetica Neue',sans-serif;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.skhint{flex:none;font-size:10px;color:var(--blue);opacity:.85}
.skhint.auto{color:var(--faint);opacity:1}
/* --- sidebar project groups (collapsible; auto-organized) --- */
.sgrouphd{display:flex;align-items:center;gap:6px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;color:var(--faint);
  padding:9px 16px 5px;cursor:pointer;user-select:none}
.sgrouphd:hover{color:var(--muted)}
.sgrouphd .chev{font-size:9px;display:inline-block;transition:transform .12s;
  width:16px;text-align:center;margin:-4px 0;padding:4px 0;border-radius:3px}
.sgrouphd .chev:hover{background:var(--border)}
.sgrouphd.collapsed .chev{transform:rotate(-90deg)}
.sgrouphd.collapsed+.sgroupbody{display:none}
.sgrouphd.active{color:var(--blue);box-shadow:inset 2px 0 0 var(--blue)}
.gname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gattn{width:6px;height:6px;flex:none}
.gcount{font-size:9px;color:var(--faint);border:1px solid var(--border2);
  border-radius:8px;padding:0 5px;font-weight:400}
/* drag-and-drop: reorder groups, move a project between groups */
.sgroup.dragging{opacity:.4}
.sitem.dragging{opacity:.4}
.sgroup.dropinto>.sgrouphd{box-shadow:inset 0 0 0 1px var(--blue)}
.sgrouphd[draggable=true]{cursor:grab}
/* folder breadcrumb (main area, shown when a group folder is open) */
.crumb{display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:12px}
.crumblink{color:var(--blue);cursor:pointer}
.crumblink:hover{text-decoration:underline}
.crumbsep{color:var(--faint);font-size:10px}
.crumbnow{font-weight:700;text-transform:uppercase;letter-spacing:.06em;font-size:10px;color:var(--ink)}
/* --- work log --- */
.todayline{font-size:12px;color:var(--muted);margin-bottom:12px}
.todayline b{color:var(--ink)}
.todayline .warn{color:var(--amber);font-weight:700}
.todayline .ok{color:var(--green);font-weight:700}
.wlbar{display:flex;align-items:center;gap:6px;margin-bottom:14px;max-width:980px}
.fbtn{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--faint);padding:4px 10px;cursor:pointer;border:1px solid var(--border);
  border-radius:5px;background:transparent}
.fbtn:hover{color:var(--ink);background:var(--panel)}
.fbtn.on{color:var(--blue);border-color:var(--blue);background:#1a2a3a}
.standup{margin-left:auto;font:inherit;font-size:10.5px;color:var(--ink);background:#1a212b;
  border:1px solid var(--border);border-radius:5px;padding:4px 10px;cursor:pointer}
.standup:hover{background:#232c38;border-color:#3a4657}
.wlchart{position:relative;background:var(--panel);border:1px solid var(--border);
  border-radius:8px;padding:10px 14px;margin-bottom:12px;max-width:980px}
.wlsvg{display:block;width:100%;height:auto}
.wlgrid{stroke:var(--border);stroke-width:1}
.wllbl{fill:var(--faint);font-family:var(--mono);font-size:9px}
.wlmark{fill:var(--blue);opacity:.55}
.wlmark:hover{opacity:.9}
.wlmark2{fill:var(--green);opacity:.5}
.wlmark2:hover{opacity:.9}
.wlcap{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin:0 0 4px 2px;max-width:980px}
.wlcapsub{font-weight:400;letter-spacing:.02em;text-transform:none;color:var(--faint)}
.wltip{display:none;position:absolute;z-index:5;pointer-events:none;font-size:10.5px;
  color:var(--ink);background:var(--panel2);border:1px solid var(--border2);
  border-radius:5px;padding:3px 8px;white-space:nowrap}
.wlrow{display:flex;gap:12px;align-items:baseline;padding:4px 0;border-top:1px solid var(--border)}
.wlrepo{flex:0 0 150px;color:var(--blue);font-weight:700;font-size:11px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.wlmsg{flex:1;min-width:0;color:var(--muted);font-size:11.5px;
  font-family:-apple-system,'Segoe UI','Helvetica Neue',sans-serif;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.wltime{flex:none;font-size:10px;color:var(--faint)}
/* --- roadmap --- */
.rmlink{margin-left:auto;font-size:9px;font-weight:400;letter-spacing:0;text-transform:none;
  color:var(--blue);text-decoration:none}
.rmlink:hover{text-decoration:underline}
.rmsec{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--amber);padding:8px 0 2px}
.rmitem{font-size:11.5px;color:var(--muted);padding:3px 0 3px 14px;line-height:1.45;
  font-family:-apple-system,'Segoe UI','Helvetica Neue',sans-serif;position:relative}
.rmitem::before{content:'▸';position:absolute;left:0;color:var(--faint);font-size:9px;top:5px}
.rmmore{font-size:10px;color:var(--faint);padding:2px 0 2px 14px}
/* --- worktrees --- */
.wtcount{margin-left:auto;font-size:9px;font-weight:400;letter-spacing:0;
  color:var(--faint);background:var(--panel2);border:1px solid var(--border2);
  border-radius:9px;padding:1px 6px}
.wtrow{padding:7px 0;border-top:1px solid var(--border)}
.wtmain{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.wtname{font-size:12px;font-weight:700;color:var(--ink)}
.wtbranch{font-size:10.5px;color:var(--blue)}
.wtbranch.det{color:var(--amber)}
.wtage{font-size:10px;color:var(--faint)}
.wtverdict{margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.02em}
.wtverdict.ok{color:var(--green)}
.wtverdict.no{color:#ff6b6b}
.wtpath{font-size:10px;color:var(--faint);margin-top:2px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.wtchips{display:flex;gap:6px;margin-top:4px}
.wtchips:empty{display:none}
.wtchip{font-size:9.5px;color:var(--muted);background:var(--panel2);
  border:1px solid var(--border2);border-radius:9px;padding:1px 7px}
.wtchip.amber{color:var(--amber);border-color:var(--amber)}
.wthint{font-size:10px;color:var(--faint);padding:8px 0 2px;border-top:1px solid var(--border);
  margin-top:6px}
.wthint code{color:var(--muted);font-size:10px}
.wtdim{color:var(--faint);font-size:11px;line-height:1.5;display:inline-block;margin-top:8px}
/* --- PM scratchpad --- */
.pmstatus{font-size:10px;color:var(--faint);margin-left:auto;align-self:center}
.pmstatus.ok{color:var(--green)}
.pmstatus.err{color:#ff6b6b}
.pmpad{flex:1;min-height:360px;width:100%;max-width:980px;resize:none;
  font-family:var(--mono);font-size:12.5px;line-height:1.6;color:var(--ink);
  background:var(--panel);border:1px solid var(--border);border-radius:8px;
  padding:14px 16px;tab-size:2}
.pmpad:focus{outline:none;border-color:var(--blue)}
.pmpad::placeholder{color:var(--faint)}
.pmpad[readonly]{opacity:.85;cursor:default}
.pmhint{font-size:10px;color:var(--faint);margin:8px 0 0 2px;max-width:980px}
.statusbar{flex:none;border-top:1px solid var(--border);background:#0f1319;padding:7px 16px;
  font-size:10.5px;color:var(--muted);display:flex;justify-content:space-between}
.statusbar b{color:var(--ink);font-weight:700}
.sbright{display:flex;align-items:center;gap:12px}
.statusbar button{font:inherit;font-size:10.5px;color:var(--ink);background:#1a212b;
  border:1px solid var(--border);border-radius:5px;padding:3px 9px;cursor:pointer;
  display:inline-flex;align-items:center;gap:5px;transition:background .12s,border-color .12s}
.statusbar button:hover{background:#232c38;border-color:#3a4657}
.statusbar button:active{background:#2b3644}
.statusbar button:disabled{opacity:.55;cursor:default}
.statusbar button .spin{display:inline-block}
.statusbar button.busy .spin{animation:sbspin .7s linear infinite}
@keyframes sbspin{to{transform:rotate(360deg)}}
/* --- config editor (shown only under the pywebview bridge) --- */
/* Higher specificity than the control rules below, so editor controls stay
   hidden until reveal() drops `nobridge` from <body>. */
body.nobridge .editonly{display:none}
body:not(.nobridge) .nobridgeonly{display:none}
.addbtn{margin:6px 12px 0;font:inherit;font-size:11px;color:var(--blue);background:transparent;
  border:1px dashed var(--border2);border-radius:5px;padding:5px 8px;cursor:pointer;width:calc(100% - 24px)}
.addbtn:hover{background:var(--panel);border-color:var(--blue)}
.dbtns{margin-left:auto;display:flex;gap:6px}
.dbtn{font:inherit;font-size:10px;color:var(--muted);background:#1a212b;border:1px solid var(--border);
  border-radius:5px;padding:3px 10px;cursor:pointer}
.dbtn:hover{background:#232c38;color:var(--ink)}
.dbtn.danger:hover{color:#ff6b6b;border-color:#5a2a2a}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;align-items:center;
  justify-content:center;z-index:50}
.modal.on{display:flex}
.sheet{background:var(--panel);border:1px solid var(--border2);border-radius:10px;width:520px;
  max-width:calc(100vw - 40px);max-height:calc(100vh - 60px);overflow-y:auto;padding:20px 22px;
  box-shadow:0 12px 40px rgba(0,0,0,.5)}
.sheet h3{margin:0 0 14px;font-size:14px;color:var(--blue)}
.field{margin-bottom:10px}
.field label{display:block;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;
  color:var(--faint);margin-bottom:4px}
.field label .req{color:var(--amber)}
.field input{width:100%;font:inherit;font-size:12.5px;color:var(--ink);background:var(--bg);
  border:1px solid var(--border2);border-radius:6px;padding:7px 9px;
  font-family:-apple-system,'Segoe UI','Helvetica Neue',sans-serif}
.field input:focus{outline:none;border-color:var(--blue)}
.ferr{color:#ff6b6b;font-size:11px;min-height:15px;margin:2px 0 6px}
.factions{display:flex;justify-content:flex-end;gap:8px;margin-top:4px}
.factions button{font:inherit;font-size:12px;border-radius:6px;padding:7px 15px;cursor:pointer;
  border:1px solid var(--border2)}
.btn-cancel{background:transparent;color:var(--muted)}
.btn-cancel:hover{color:var(--ink);background:var(--panel2)}
.btn-save{background:#1f6feb;border-color:#1f6feb;color:#fff;font-weight:700}
.btn-save:hover{background:#2a7bff}
.btn-save:disabled{opacity:.6;cursor:default}
.ghstat{padding:8px 14px 0;font-size:10px;color:var(--muted);line-height:1.5}
.ghstat b{color:var(--ink)}
.ghsub{color:var(--faint);margin:1px 0 3px}
.ghstat a{color:var(--blue);cursor:pointer}
.ghstat a:hover{text-decoration:underline}
</style>
<body class="nobridge">
<div class="app">
  <div class="side">
    <div class="brand">orrery</div>
    <div class="sitem on" id="s-overview" onclick="nav('overview')"><span class="dot green"></span><span class="sname">overview</span><span class="skey">⌘0</span></div>
    %%TOPSIDE%%
    <div class="shead">Projects (%%COUNT%%)</div>
    %%SIDE%%
    <button class="addbtn editonly" onclick="openEditor()">＋ Add project</button>
    <div class="editonly" id="ghbox"></div>
  </div>
  <div class="main">
    <div class="view on" id="v-overview"><div class="todayline">%%TODAY%%</div>
      <div class="crumb" id="crumb" style="display:none"><span class="crumblink" tabindex="0" role="button" onclick="clearFolder()">‹ All projects</span><span class="crumbsep">▸</span><span class="crumbnow" id="crumbnow"></span></div>
      <div class="grid">%%CARDS%%</div></div>
    %%TOPVIEWS%%
    %%DETAILS%%
  </div>
</div>
<div class="statusbar"><span>%%STATS%%</span><span class="sbright"><span id="freshness" data-gen="%%GENTS%%" data-min="%%MIN%%">updated %%NOW%% · reload %%MIN%%m · ⌘0 overview · ⌘1–9 projects</span><button id="refreshgit" onclick="refreshGit(this)" title="Rescan all repos now (⌘R)"><span class="spin">⟳</span> Refresh git</button></span></div>
<div class="modal" id="editor" onclick="if(event.target===this)closeEditor()"><div class="sheet">
  <h3 id="editortitle">Add project</h3>
  <div id="editorfields"></div>
  <div class="ferr" id="editorerr"></div>
  <div class="factions">
    <button class="btn-cancel" onclick="closeEditor()">Cancel</button>
    <button class="btn-save" id="editorsave" onclick="submitEditor()">Save</button>
  </div>
</div></div>
<div class="modal" id="ghmodal" onclick="if(event.target===this)closeGitHub()"><div class="sheet">
  <h3>Connect GitHub</h3>
  <div class="field"><label>Fine-grained token <span class="req">*</span></label>
    <input type="password" id="ghtoken" spellcheck="false" placeholder="github_pat_…"></div>
  <div style="font-size:11px;color:var(--muted);line-height:1.5;margin-bottom:8px">
    Create one with <b>Metadata: read</b> + <b>Contents: read</b> at
    github.com/settings/tokens. It's stored in your OS keychain — never in the config file.</div>
  <div class="ferr" id="gherr"></div>
  <div class="factions">
    <button class="btn-cancel" onclick="closeGitHub()">Cancel</button>
    <button class="btn-save" id="ghsave" onclick="ghConnect()">Connect</button>
  </div>
</div></div>
<script>
// Freshness guard: git data is a snapshot from generation time. If the file
// stops being regenerated (menubar app quit / watcher died), the meta-refresh
// keeps reloading a stale snapshot — so flag it loudly instead of trusting it.
(function(){var el=document.getElementById('freshness');if(!el)return;
 var gen=parseInt(el.getAttribute('data-gen'),10),min=parseInt(el.getAttribute('data-min'),10);
 function tick(){var age=Date.now()/1000-gen;
   if(age>min*60*2){var m=Math.round(age/60);
     el.style.color='#ff6b6b';el.style.fontWeight='700';
     el.textContent='⚠ STALE — git snapshot is '+m+'m old (regen not running)';}}
 tick();setInterval(tick,30000);})();
// Periodic reload to pick up fresh git data — but NEVER while the PM scratchpad
// has unsaved edits or focus, so a background refresh can't eat what you're
// typing (replaces the old blunt <meta refresh>).
function mcReload(){
  var pad=document.getElementById('pmpad');
  var dirty=(typeof PM_SAVED!=='undefined'&&!PM_SAVED)||(pad&&document.activeElement===pad);
  if(dirty){setTimeout(mcReload,4000);return;}   // check back until the pad settles
  location.reload();
}
setTimeout(mcReload,%%SECS%%*1000);
var NAMES=%%NAMES%%;
var FIELDS=%%FIELDS%%;          // [key,label,placeholder,required] — form source of truth
var PROJECTS_RAW=%%PROJECTS_RAW%%;   // raw config entries, for prefilling edits
function clearFolder(){
  document.querySelectorAll('#v-overview .card').forEach(function(c){c.style.display='';});
  var cr=document.getElementById('crumb');if(cr)cr.style.display='none';
  document.querySelectorAll('.sgrouphd.active').forEach(function(h){h.classList.remove('active');});
}
function openFolder(gid,hd){
  nav('overview');                              // grid visible (also clears prior folder)
  var label=hd?hd.querySelector('.gname').textContent:gid, shown=0;
  document.querySelectorAll('#v-overview .card').forEach(function(c){
    var on=c.getAttribute('data-group')===gid; c.style.display=on?'':'none'; if(on)shown++;
  });
  var cn=document.getElementById('crumbnow');if(cn)cn.textContent=label+'  '+shown;
  var cr=document.getElementById('crumb');if(cr)cr.style.display='flex';
  if(hd)hd.classList.add('active');
  location.hash='g/'+gid;
}
function nav(n){
  clearFolder();
  document.querySelectorAll('.view').forEach(function(v){v.classList.remove('on')});
  document.querySelectorAll('.sitem').forEach(function(s){s.classList.remove('on')});
  var v=document.getElementById('v-'+n), s=document.getElementById('s-'+n);
  if(!v){v=document.getElementById('v-overview');s=document.getElementById('s-overview');n='overview';}
  v.classList.add('on'); if(s)s.classList.add('on');
  location.hash = n==='overview' ? '' : 'p/'+n;
}
function tab(el,url){
  var view=el.closest('.view');
  view.querySelectorAll('.tab').forEach(function(t){t.classList.remove('on')});
  view.querySelectorAll('.pane').forEach(function(p){p.classList.remove('on')});
  el.classList.add('on');
  var idx=[].indexOf.call(el.parentNode.children,el);
  var pane=view.querySelectorAll('.pane')[idx];
  pane.classList.add('on');
  var f=pane.querySelector('iframe');
  if(f&&!f.src)f.src=f.dataset.src;
}
function toggleGroup(gid){
  var hd=document.getElementById('ghd-'+gid);if(!hd)return;
  hd.classList.toggle('collapsed');
  try{var c=JSON.parse(localStorage.getItem('mcGroups')||'{}');
    c[gid]=hd.classList.contains('collapsed');
    localStorage.setItem('mcGroups',JSON.stringify(c));}catch(e){}
}
// restore collapsed groups from last session
(function(){try{var c=JSON.parse(localStorage.getItem('mcGroups')||'{}');
  Object.keys(c).forEach(function(gid){if(c[gid]){
    var hd=document.getElementById('ghd-'+gid);if(hd)hd.classList.add('collapsed');}});
}catch(e){}})();
// keyboard: Enter/Space activates any focusable nav element (div-based controls)
document.addEventListener('keydown',function(e){
  if((e.key==='Enter'||e.key===' ')&&e.target.matches&&
     e.target.matches('.sitem,.tab,.card,.fbtn,.sgrouphd,.crumblink,.chev')){
    e.preventDefault();e.target.click();
  }
});
// --- sidebar drag: reorder groups; drag a project into another group ---
(function(){
  var cont=document.getElementById('sidegroups'); if(!cont)return;
  var dragEl=null,dragType=null;
  var esc=function(s){return (window.CSS&&CSS.escape)?CSS.escape(s):s;};
  function saveOrder(){try{localStorage.setItem('mcGroupOrder',JSON.stringify(
    [].map.call(cont.querySelectorAll('.sgroup'),function(g){return g.getAttribute('data-gid');})));}catch(e){}}
  function saveItems(){var m={};cont.querySelectorAll('.sgroup').forEach(function(g){
    var gid=g.getAttribute('data-gid');
    g.querySelectorAll('.sitem').forEach(function(it){m[it.getAttribute('data-proj')]=gid;});});
    try{localStorage.setItem('mcItemGroup',JSON.stringify(m));}catch(e){}}
  function cardTo(proj,gid){var c=document.querySelector('#v-overview .card[data-proj="'+esc(proj)+'"]');
    if(c)c.setAttribute('data-group',gid);}
  function recount(){cont.querySelectorAll('.sgroup').forEach(function(g){
    var n=g.querySelectorAll('.sitem').length,c=g.querySelector('.gcount');
    if(c)c.textContent=n; g.style.display=n?'':'none';});}
  cont.addEventListener('dragstart',function(e){
    var it=e.target.closest('.sitem'),hd=e.target.closest('.sgrouphd');
    if(it){dragType='item';dragEl=it;}
    else if(hd){dragType='group';dragEl=hd.parentNode;}
    else return;
    e.dataTransfer.effectAllowed='move';try{e.dataTransfer.setData('text/plain','x');}catch(_){}
    setTimeout(function(){if(dragEl)dragEl.classList.add('dragging');},0);
  });
  cont.addEventListener('dragend',function(){
    if(dragEl)dragEl.classList.remove('dragging');
    cont.querySelectorAll('.dropinto').forEach(function(x){x.classList.remove('dropinto');});
    dragEl=null;dragType=null;});
  cont.addEventListener('dragover',function(e){
    if(!dragEl)return; e.preventDefault(); e.dataTransfer.dropEffect='move';
    var g=e.target.closest('.sgroup'); if(!g)return;
    if(dragType==='group'){ if(g===dragEl)return;
      var r=g.getBoundingClientRect();
      cont.insertBefore(dragEl,(e.clientY<r.top+r.height/2)?g:g.nextSibling);
    }else{ cont.querySelectorAll('.dropinto').forEach(function(x){x.classList.remove('dropinto');});
      g.classList.add('dropinto'); }});
  cont.addEventListener('drop',function(e){
    if(!dragEl)return; e.preventDefault();
    var g=e.target.closest('.sgroup');
    if(dragType==='group'){ saveOrder(); }
    else if(dragType==='item'&&g){
      g.querySelector('.sgroupbody').appendChild(dragEl);
      cardTo(dragEl.getAttribute('data-proj'), g.getAttribute('data-gid'));
      recount(); saveItems(); }
    cont.querySelectorAll('.dropinto').forEach(function(x){x.classList.remove('dropinto');});});
  // restore saved arrangement (item placement, then group order)
  try{
    var im=JSON.parse(localStorage.getItem('mcItemGroup')||'{}');
    Object.keys(im).forEach(function(proj){
      var it=cont.querySelector('.sitem[data-proj="'+esc(proj)+'"]'), body=document.getElementById('g-'+im[proj]);
      if(it&&body){body.appendChild(it);cardTo(proj,im[proj]);}});
    JSON.parse(localStorage.getItem('mcGroupOrder')||'[]').forEach(function(gid){
      var g=cont.querySelector('.sgroup[data-gid="'+esc(gid)+'"]'); if(g)cont.appendChild(g);});
    recount();
  }catch(e){}
})();
function skillFilter(q){
  q=q.trim().toLowerCase();
  document.querySelectorAll('#v-skills .sgroup').forEach(function(g){
    var vis=0;
    g.querySelectorAll('.skrow').forEach(function(r){
      var on=!q||r.getAttribute('data-q').indexOf(q)>=0;
      r.style.display=on?'':'none';if(on)vis++;
    });
    g.style.display=vis?'':'none';
  });
}
function refreshGit(btn){
  // Rescan every repo's git and rewrite the page. In the pywebview app this
  // calls back into Python (real git scan) then reloads; in a plain browser
  // (no bridge) it just reloads the file the menubar timer keeps fresh.
  if(btn){btn.disabled=true;btn.classList.add('busy');
    var lbl=btn.childNodes[btn.childNodes.length-1];lbl.textContent=' rescanning…';}
  function reload(){location.reload();}
  if(window.pywebview&&window.pywebview.api&&window.pywebview.api.refresh){
    window.pywebview.api.refresh().then(reload).catch(reload);
  } else { reload(); }
}
document.addEventListener('keydown',function(e){
  if(!(e.metaKey||e.ctrlKey))return;
  if(e.key==='r'||e.key==='R'){refreshGit(document.getElementById('refreshgit'));e.preventDefault();return;}
  if(e.key==='0'){nav('overview');e.preventDefault();}
  var i=parseInt(e.key,10);
  if(i>=1&&i<=NAMES.length){nav(NAMES[i-1]);e.preventDefault();}
});
(function(){var h=location.hash.replace('#','');
  if(h.indexOf('p/')===0)nav(h.slice(2));
  else if(h.indexOf('g/')===0){var gid=h.slice(2),hd=document.getElementById('ghd-'+gid);openFolder(gid,hd);}
})();

// --- config editor (only usable through the pywebview Python bridge) ---
(function(){
  // reveal Add/Edit/Delete controls only when the bridge exists (packaged app);
  // in a plain browser they'd have nothing to write to. Dropping the body class
  // lets each control fall back to its natural display.
  function reveal(){document.body.classList.remove('nobridge');ghRefresh();
    var pad=document.getElementById('pmpad');if(pad)pad.removeAttribute('readonly');}
  if(window.pywebview&&window.pywebview.api){reveal();}
  else{window.addEventListener('pywebviewready',reveal);}
})();
var EDIT_ORIG=null;
function bridge(){return window.pywebview&&window.pywebview.api;}
function openEditor(name){
  EDIT_ORIG=name||null;
  var data={};
  if(name){for(var i=0;i<PROJECTS_RAW.length;i++){if(PROJECTS_RAW[i].name===name){data=PROJECTS_RAW[i];break;}}}
  document.getElementById('editortitle').textContent=name?('Edit '+name):'Add project';
  var box=document.getElementById('editorfields');box.innerHTML='';
  FIELDS.forEach(function(f){
    var key=f[0],label=f[1],ph=f[2],req=f[3];
    var div=document.createElement('div');div.className='field';
    var lab=document.createElement('label');lab.textContent=label;
    if(req){var s=document.createElement('span');s.className='req';s.textContent=' *';lab.appendChild(s);}
    var inp=document.createElement('input');inp.type='text';inp.id='f-'+key;
    inp.value=data[key]!=null?String(data[key]):'';inp.placeholder=ph;inp.setAttribute('spellcheck','false');
    inp.addEventListener('keydown',function(e){if(e.key==='Enter')submitEditor();});
    div.appendChild(lab);div.appendChild(inp);box.appendChild(div);
  });
  document.getElementById('editorerr').textContent='';
  var sv=document.getElementById('editorsave');sv.disabled=false;sv.textContent='Save';
  document.getElementById('editor').classList.add('on');
  var first=document.getElementById('f-'+FIELDS[0][0]);if(first)first.focus();
}
function closeEditor(){document.getElementById('editor').classList.remove('on');}
function submitEditor(){
  var proj={},err=document.getElementById('editorerr');
  FIELDS.forEach(function(f){proj[f[0]]=document.getElementById('f-'+f[0]).value.trim();});
  if(!proj.name){err.textContent='Name is required.';return;}
  if(!proj.path){err.textContent='Path is required.';return;}
  if(!(bridge()&&window.pywebview.api.save_project)){
    err.textContent='Editing needs the desktop app.';return;}
  var btn=document.getElementById('editorsave');btn.disabled=true;btn.textContent='Saving…';
  window.pywebview.api.save_project(proj,EDIT_ORIG).then(function(r){
    if(r&&r.ok){location.reload();}
    else{btn.disabled=false;btn.textContent='Save';err.textContent=(r&&r.error)||'Save failed.';}
  }).catch(function(){btn.disabled=false;btn.textContent='Save';err.textContent='Save failed.';});
}
function removeProject(name){
  if(!confirm('Remove “'+name+'” from Orrery?\\nThis only edits baseline.json — it does not touch the repo.'))return;
  if(!(bridge()&&window.pywebview.api.delete_project))return;
  window.pywebview.api.delete_project(name).then(function(r){if(r&&r.ok)location.reload();});
}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeEditor();closeGitHub();}});

// --- GitHub connect (P3.1, pywebview only). Token → OS keychain via Python. ---
function ghAgo(ts){                                  // unix seconds → "3m ago"
  if(!ts)return '';
  var s=Math.max(0,Math.floor(Date.now()/1000-ts));
  if(s<60)return 'just now';
  if(s<3600)return Math.floor(s/60)+'m ago';
  if(s<86400)return Math.floor(s/3600)+'h ago';
  return Math.floor(s/86400)+'d ago';
}
function ghRefresh(){
  if(!(bridge()&&window.pywebview.api.github_status))return;
  window.pywebview.api.github_status().then(function(s){
    var box=document.getElementById('ghbox');if(!box)return;
    if(s&&s.connected){
      var sub = s.synced_at
        ? (s.repo_count||0)+' repos · '+ghAgo(s.synced_at)
        : 'not synced yet';
      box.innerHTML='<div class="ghstat">GitHub · <b>'+(s.login||'connected')+'</b>'+
        '<div class="ghsub">'+sub+'</div>'+
        '<a onclick="ghSync()">sync</a> · <a onclick="ghDisconnect()">disconnect</a></div>';
    } else {
      box.innerHTML='<button class="addbtn" onclick="openGitHub()">Connect GitHub</button>';
    }
  }).catch(function(){});
}
function ghClone(url){
  if(!(bridge()&&window.pywebview.api.github_clone))return;
  if(!confirm('Clone '+url+' into your first roots folder?'))return;
  window.pywebview.api.github_clone(url).then(function(r){
    if(r&&r.ok){location.reload();}
    else{alert((r&&r.error)||'Clone failed.');}
  }).catch(function(){alert('Clone failed.');});
}
function ghSync(){
  if(!(bridge()&&window.pywebview.api.github_sync))return;
  var box=document.getElementById('ghbox');
  box.innerHTML='<div class="ghstat">GitHub · syncing…</div>';
  window.pywebview.api.github_sync().then(function(r){
    if(r&&r.ok){location.reload();}                 // regenerated with GitHub cards
    else{ghRefresh();if(r&&r.error)alert('Sync failed: '+r.error);}
  }).catch(function(){ghRefresh();});
}
function openGitHub(){
  document.getElementById('gherr').textContent='';
  document.getElementById('ghtoken').value='';
  document.getElementById('ghmodal').classList.add('on');
  document.getElementById('ghtoken').focus();
}
function closeGitHub(){document.getElementById('ghmodal').classList.remove('on');}
function ghConnect(){
  var tok=document.getElementById('ghtoken').value.trim(),err=document.getElementById('gherr');
  if(!tok){err.textContent='Paste a token.';return;}
  if(!(bridge()&&window.pywebview.api.github_connect)){err.textContent='Needs the desktop app.';return;}
  var b=document.getElementById('ghsave');b.disabled=true;b.textContent='Connecting…';
  window.pywebview.api.github_connect(tok).then(function(r){
    b.disabled=false;b.textContent='Connect';
    if(r&&r.ok){closeGitHub();ghRefresh();}
    else{err.textContent=(r&&r.error)||'Connection failed.';}
  }).catch(function(){b.disabled=false;b.textContent='Connect';err.textContent='Connection failed.';});
}
function ghDisconnect(){
  if(!confirm('Disconnect GitHub? This removes the token from your keychain.'))return;
  if(!(bridge()&&window.pywebview.api.github_disconnect))return;
  window.pywebview.api.github_disconnect().then(ghRefresh);
}
</script>
</body></html>"""

    page = (tpl.replace("%%SECS%%", str(REFRESH_MIN * 60))
               .replace("%%GENTS%%", str(int(time.time())))
               .replace("%%COUNT%%", str(len(projects)))
               .replace("%%TOPSIDE%%", "".join(top_side))
               .replace("%%TOPVIEWS%%", "".join(top_views))
               .replace("%%TODAY%%", views.hero_line(worklog, totals))
               .replace("%%SIDE%%", "".join(side))
               .replace("%%CARDS%%", "".join(cards))
               .replace("%%DETAILS%%", "".join(details))
               .replace("%%STATS%%", stats)
               .replace("%%NOW%%", now)
               .replace("%%MIN%%", str(REFRESH_MIN))
               .replace("%%NAMES%%", json.dumps(flat_names))
               .replace("%%FIELDS%%", json.dumps(PROJECT_FIELDS))
               .replace("%%PROJECTS_RAW%%",
                        json.dumps([pr["p"] for pr in projects]).replace("</", "<\\/")))
    page = page.replace("⌘", MOD)   # platform shortcut labels (⌘ vs Ctrl+)
    out = INDEX
    open(out, "w", encoding="utf-8").write(page)
    print(f"wrote {out}  ({len(projects)} projects) at {now}")
    if "--open" in sys.argv:
        webbrowser.open(Path(out).as_uri())

if __name__ == "__main__":
    if "--watch" in sys.argv:
        while True:
            main()
            time.sleep(REFRESH_MIN * 60)
    else:
        main()
