#!/usr/bin/env python3
"""Mission Control — one dark shell, every project's live state + maps.
Usage: ./generate.py [--open] [--watch]   (stdlib only, no deps)
Git data live from each repo · human facts from baseline.json · maps via vizstack/agentviz.
Design language matches codebase-viz/vizstack (GitHub-dark, SF Mono).
"""
import json, subprocess, os, sys, html, datetime, time, shutil, webbrowser
from pathlib import Path

APP_NAME = "Mission Control"
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


def _data_dir():
    """Where config + generated output live. Running from source: next to the
    script (unchanged dev workflow). Installed app: per-user app-data dir,
    because the bundle itself is read-only once signed/installed."""
    if not FROZEN:
        return HERE
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME",
                              os.path.expanduser("~/.local/share"))
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


DATA = _data_dir()
BASELINE = os.path.join(DATA, "baseline.json")
INDEX = os.path.join(DATA, "index.html")


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
    unmerged = git(repo, "branch", "-r", "--no-merged", base) if base else ""
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

def build_viz(name, path, p, cfg_tools):
    """Optional architecture/pipeline maps. Tool paths come from the config's
    "tools" section; projects that don't set viz_* (or users without the tools
    installed) simply get no map tabs."""
    vizstack = os.path.expanduser(cfg_tools.get("vizstack", ""))
    agentviz = os.path.expanduser(cfg_tools.get("agentviz", ""))
    tools = {}
    if vizstack and os.path.isfile(vizstack):
        tools["app"] = (["node", vizstack], p.get("viz_app"))
    if agentviz and os.path.isfile(agentviz):
        py = shutil.which("python3") or shutil.which("python") or "python3"
        tools["pipeline"] = ([py, agentviz], p.get("viz_pipeline"))
    links = []
    os.makedirs(os.path.join(DATA, "viz"), exist_ok=True)
    for kind, (cmd, target) in tools.items():
        if not target:
            continue
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

def chips(g):
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

def rows_html(p, g, path):
    esc = html.escape
    def row(label, val):
        return (f'<div class="row"><span class="lbl">{label}</span>'
                f'<span class="val">{val}</span></div>') if val else ""
    if p["prod"]:
        site = f'<a href="{esc(p["prod"])}" target="_blank">{esc(p["prod"].replace("https://",""))}</a>'
        if p["prod_note"]:
            site += f' <span class="sub">· {esc(p["prod_note"])}</span>'
    else:
        site = f'<span class="sub">{esc(p["prod_note"] or "—")}</span>'
    arch = (f'<a href="{esc(Path(path, p["arch"]).as_uri())}">{esc(p["arch"])}</a>'
            if p["arch"] else "")
    outline = arch_outline(path, p.get("arch", ""))
    archval = f'{esc(outline)} <span class="sub">·</span> {arch}' if outline and arch else arch
    return (row("Site", site)
            + (row("Email", esc(p.get("email", ""))) if p.get("email") else "")
            + row("Dev", esc(p.get("dev", "")))
            + row("Prod", esc(p.get("prod_env", "")))
            + row("Stack", esc(p["stack"]))
            + row("Arch", archval)
            + row("Last", f'<span class="sub">{esc(g["last_msg"])}</span>')
            + (f'<div class="focus">{row("Focus", esc(p["focus"]))}</div>' if p["focus"] else ""))

def main():
    cfg = load_config()
    projects, totals = [], {"dirty": 0, "unmerged": 0, "ahead": 0, "attn": 0}
    for p in cfg["projects"]:
        path = os.path.expanduser(p["path"])
        if not os.path.isdir(os.path.join(path, ".git")):
            continue
        g = collect(path)
        maps = build_viz(p["name"], path, p, cfg.get("tools", {}))
        attn = g["dirty"] or g["unmerged"] or g["stashes"] or g["ahead"] != "0"
        totals["dirty"] += g["dirty"]; totals["unmerged"] += g["unmerged"]
        totals["ahead"] += int(g["ahead"]) if g["ahead"].isdigit() else 0
        totals["attn"] += 1 if attn else 0
        projects.append({"p": p, "g": g, "maps": maps, "path": path, "attn": attn})

    esc = html.escape
    side, cards, details = [], [], []
    for i, pr in enumerate(projects):
        p, g, maps = pr["p"], pr["g"], pr["maps"]
        n = esc(p["name"])
        dot = f'<span class="dot amber"></span>' if pr["attn"] else '<span class="dot green"></span>'
        badge = f'<span class="scount">{g["dirty"]}</span>' if g["dirty"] else ""
        side.append(f'<div class="sitem" id="s-{n}" onclick="nav(\'{n}\')">'
                    f'{dot}<span class="sname">{n}</span>{badge}'
                    f'<span class="skey">⌘{i+1}</span></div>' if i < 9 else
                    f'<div class="sitem" id="s-{n}" onclick="nav(\'{n}\')">{dot}<span class="sname">{n}</span>{badge}</div>')
        accent = ' accent' if pr["attn"] else ""
        cards.append(f'''<div class="card{accent}" onclick="nav('{n}')">
  <div class="ctop"><span class="cname">{n}</span><span class="age">{esc(g["last_rel"] or "")}</span></div>
  <div class="thesis">{esc(p["thesis"])}</div>
  <div class="chips">{chips(g)}</div>
</div>''')
        tabs = ['<span class="tab on" onclick="tab(this,null)">overview</span>']
        panes = [f'<div class="pane on"><div class="dcard">'
                 f'<div class="chips" style="margin-bottom:10px">{chips(g)}</div>'
                 f'{rows_html(p, g, pr["path"])}</div></div>']
        for label, url in maps:
            tabs.append(f'<span class="tab" onclick="tab(this,\'{esc(url)}\')">{esc(label)} map</span>')
            panes.append('<div class="pane"><iframe data-src="' + esc(url) + '"></iframe></div>')
        details.append(f'''<div class="view" id="v-{n}">
  <div class="dhead"><span class="dname">{n}</span><span class="dthesis">{esc(p["thesis"])}</span></div>
  <div class="tabs">{"".join(tabs)}</div>
  {"".join(panes)}
</div>''')

    if not projects:
        cards.append(
            '<div class="card" style="cursor:default"><div class="ctop">'
            '<span class="cname">No projects yet</span></div>'
            '<div class="thesis">Add your repos to the config file, then hit '
            'Refresh git:<br><code style="font-size:11px">'
            f'{esc(BASELINE)}</code><br>Each entry needs a "name", a "path" '
            'to a local git repo, and whatever facts you want on the card.'
            '</div></div>')

    now_dt = datetime.datetime.now()
    now = now_dt.strftime("%a %b %d · %H:%M")
    stats = (f'Projects <b>{len(projects)}</b> · Needs attention <b>{totals["attn"]}</b> · '
             f'Uncommitted <b>{totals["dirty"]}</b> · Unmerged branches <b>{totals["unmerged"]}</b> · '
             f'Unpushed <b>{totals["ahead"]}</b>')

    tpl = """<!doctype html><html><head><meta charset="utf-8">
<title>Mission Control</title>
<meta http-equiv="refresh" content="%%SECS%%">
<style>
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2129;--border:#21262d;--border2:#30363d;
  --ink:#c9d1d9;--muted:#8b949e;--faint:#6e7681;--blue:#58a6ff;--green:#3fb950;--amber:#d29922;
  --mono:'SF Mono','Fira Code','Cascadia Code',Consolas,ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
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
.dot.green{background:var(--green)}.dot.amber{background:var(--amber)}
.scount{font-size:10px;color:var(--amber);border:1px solid #4d3800;background:#2a2100;
  border-radius:8px;padding:0 6px}
.skey{font-size:9px;color:var(--faint)}
.main{flex:1;display:flex;flex-direction:column;min-width:0}
.view{display:none;flex:1;min-height:0;flex-direction:column;overflow-y:auto;padding:20px 24px}
.view.on{display:flex}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;align-content:start}
.card{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:14px 16px;cursor:pointer}
.card:hover{border-color:var(--border2);background:var(--panel2)}
.card.accent{box-shadow:inset 3px 0 0 var(--amber)}
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
.sub{color:var(--muted)}
.focus{margin-top:10px;border-top:1px solid var(--border);padding-top:4px}
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
</style>
<body>
<div class="app">
  <div class="side">
    <div class="brand">mission-control</div>
    <div class="sitem on" id="s-overview" onclick="nav('overview')"><span class="dot green"></span><span class="sname">overview</span><span class="skey">⌘0</span></div>
    <div class="shead">Projects (%%COUNT%%)</div>
    %%SIDE%%
  </div>
  <div class="main">
    <div class="view on" id="v-overview"><div class="grid">%%CARDS%%</div></div>
    %%DETAILS%%
  </div>
</div>
<div class="statusbar"><span>%%STATS%%</span><span class="sbright"><span id="freshness" data-gen="%%GENTS%%" data-min="%%MIN%%">updated %%NOW%% · reload %%MIN%%m · ⌘0 overview · ⌘1–9 projects</span><button id="refreshgit" onclick="refreshGit(this)" title="Rescan all repos now (⌘R)"><span class="spin">⟳</span> Refresh git</button></span></div>
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
var NAMES=%%NAMES%%;
function nav(n){
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
(function(){var h=location.hash.replace('#','');if(h.indexOf('p/')===0)nav(h.slice(2));})();
</script>
</body></html>"""

    page = (tpl.replace("%%SECS%%", str(REFRESH_MIN * 60))
               .replace("%%GENTS%%", str(int(time.time())))
               .replace("%%COUNT%%", str(len(projects)))
               .replace("%%SIDE%%", "".join(side))
               .replace("%%CARDS%%", "".join(cards))
               .replace("%%DETAILS%%", "".join(details))
               .replace("%%STATS%%", stats)
               .replace("%%NOW%%", now)
               .replace("%%MIN%%", str(REFRESH_MIN))
               .replace("%%NAMES%%", json.dumps([pr["p"]["name"] for pr in projects])))
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
