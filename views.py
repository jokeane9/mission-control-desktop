#!/usr/bin/env python3
"""Mission Control — top-level dashboard views beyond the project cards.
Stdlib only, like generate.py. Each view is a collect_*() (pure data, testable)
plus a *_html() renderer that generate.py drops into the page template.

Views:
  Skills   — a searchable catalog of Claude Code skills (plugins, project-local,
             user-level), parsed from SKILL.md frontmatter.
  Work Log — the user's own commits across every dashboard repo, as a
             per-day chart + day-grouped list with a Today/Week/Month/3-months
             filter and a "Copy as standup" button.
  Roadmap  — every project's ROADMAP.md in one place: the Now/Next sections
             (or the top items when a roadmap has neither), linked to the file.
"""
import datetime
import glob
import html
import json
import os
import re
import subprocess
from pathlib import Path

CLAUDE_DIR = os.path.expanduser("~/.claude")
DESC_MAX = 160          # one-line description budget per skill row
WORKLOG_DAYS = 92       # history window ≥ the widest filter (3 months)


# --------------------------------------------------------------------------- #
# SKILL.md frontmatter — flat `key: value` pairs plus folded/indented
# continuation lines (`description: >` style). Best-effort; never raises.
# --------------------------------------------------------------------------- #
def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line[:1] in (" ", "\t"):          # continuation of the previous key
            if key is not None and line.strip():
                data[key] = (data[key] + " " + line.strip()).strip()
            continue
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if val in (">", "|", ">-", "|-"):    # block scalar: body follows indented
            val = ""
        if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
            val = val[1:-1]
        data[key] = val
    return data


def _read_skill(path):
    try:
        return parse_frontmatter(open(path, encoding="utf-8", errors="ignore").read())
    except Exception:
        return {}


def _one_line(desc):
    desc = " ".join((desc or "").split())
    return desc[:DESC_MAX - 1] + "…" if len(desc) > DESC_MAX else desc


def _skill(fm, fallback_name, qualifier=""):
    """One catalog entry from parsed frontmatter. `qualifier` prefixes the
    invoke hint for plugin skills (/plugin:name)."""
    name = str(fm.get("name") or fallback_name)
    invocable = str(fm.get("user-invocable", "")).lower() != "false"
    invoke = f"/{qualifier}{name}" if invocable else "auto"
    return {"name": name,
            "desc": _one_line(str(fm.get("description", ""))),
            "invoke": invoke}


def _walk_skill_files(root):
    """Every SKILL.md under root, sorted for stable output."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") or d == ".claude"]
        if "SKILL.md" in filenames:
            found.append(os.path.join(dirpath, "SKILL.md"))
    return sorted(found)


def collect_skills(project_dirs, claude_dir=CLAUDE_DIR):
    """Grouped skill catalog: [(group_label, [entry, …]), …].
    Sources, in display order:
      1. installed plugins   — <claude_dir>/plugins/marketplaces/<mkt>/…/<plugin>/skills/**
      2. project-local       — <project>/.claude/skills/**   (from the dashboard's repos)
      3. user-level          — <claude_dir>/skills/**
    """
    groups = {}

    def add(label, entry):
        groups.setdefault(label, []).append(entry)

    # 1. plugin skills — group by "<marketplace> · <plugin>" so /plugin:name reads off the row
    plug_root = os.path.join(claude_dir, "plugins", "marketplaces")
    if os.path.isdir(plug_root):
        for f in _walk_skill_files(plug_root):
            rel = os.path.relpath(f, plug_root).split(os.sep)
            # <marketplace>/(plugins|external_plugins)/<plugin>/skills/<skill>/SKILL.md
            if len(rel) >= 5 and rel[1] in ("plugins", "external_plugins"):
                mkt, plugin = rel[0], rel[2]
            else:                              # unexpected layout — still list it
                mkt, plugin = rel[0], "?"
            fm = _read_skill(f)
            add(f"plugin · {plugin}  ({mkt})",
                _skill(fm, os.path.basename(os.path.dirname(f)), f"{plugin}:"))

    plugin_labels = sorted(groups)

    # 2. project-local skills
    project_labels = []
    for name, pdir in sorted(project_dirs):
        root = os.path.join(os.path.expanduser(pdir), ".claude", "skills")
        if not os.path.isdir(root):
            continue
        label = f"project · {name}"
        for f in _walk_skill_files(root):
            fm = _read_skill(f)
            add(label, _skill(fm, os.path.basename(os.path.dirname(f))))
        if label in groups:
            project_labels.append(label)

    # 3. user-level skills
    user_root = os.path.join(claude_dir, "skills")
    if os.path.isdir(user_root):
        for f in _walk_skill_files(user_root):
            fm = _read_skill(f)
            add("user · ~/.claude/skills", _skill(fm, os.path.basename(os.path.dirname(f))))
    user_labels = ["user · ~/.claude/skills"] if "user · ~/.claude/skills" in groups else []

    return [(label, groups[label])
            for label in plugin_labels + project_labels + user_labels]


# --------------------------------------------------------------------------- #
# Work Log — the user's commits across every repo the dashboard knows about.
# Fork-safe: filtered to the user's own author identity (per-repo user.email,
# plus the global one), so pulled upstream history doesn't count as "shipped".
# --------------------------------------------------------------------------- #
def _git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo] + list(args),
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _author_emails(repo):
    """The emails identifying "me" in this repo: the repo-effective user.email
    and the global one (they differ when a repo overrides it). Matched with
    --fixed-strings — regex-escaping breaks here because git's default basic
    regex reads the `\\+` in noreply addresses as a repetition operator."""
    emails = {_git(repo, "config", "user.email"),
              _git(repo, "config", "--global", "user.email")}
    return sorted(e for e in emails if e)


def collect_worklog(project_dirs, days=WORKLOG_DAYS):
    """[{r: repo, t: unix_ts, s: subject}, …] newest first — the user's own
    commits across all local branches of every dashboard repo."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    commits = []
    for name, pdir in project_dirs:
        repo = os.path.expanduser(pdir)
        args = ["log", "--branches", f"--since={since}", "--format=%ct%x09%s"]
        authors = _author_emails(repo)
        if authors:                                     # ORed; none configured → all
            args += ["--fixed-strings"] + [f"--author={a}" for a in authors]
        for line in _git(repo, *args).splitlines():
            ct, _, subj = line.partition("\t")
            if ct.isdigit():
                commits.append({"r": name, "t": int(ct), "s": subj[:120]})
    commits.sort(key=lambda c: -c["t"])
    return commits


def _parse_transcript(path):
    """Per-day usage totals from one Claude Code session transcript.
    Cheap pre-filter (most lines carry no usage), then dedupe by message id —
    streaming updates repeat a message's usage on several lines; keep the last."""
    ids = {}
    try:
        for line in open(path, encoding="utf-8", errors="ignore"):
            if '"usage"' not in line:      # cheap pre-filter; most lines skip here
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            m = d.get("message") or {}
            u = m.get("usage")
            ts = d.get("timestamp")
            if isinstance(u, dict) and ts:
                ids[m.get("id") or d.get("requestId") or ts] = (ts, u)
    except OSError:
        return {}
    days = {}
    for ts, u in ids.values():
        try:
            day = (datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                   .astimezone().date().isoformat())
        except ValueError:
            continue
        t = days.setdefault(day, [0, 0, 0, 0])
        for i, k in enumerate(("input_tokens", "output_tokens",
                               "cache_creation_input_tokens", "cache_read_input_tokens")):
            try:
                t[i] += int(u.get(k) or 0)
            except (TypeError, ValueError):
                pass
    return days


def collect_tokens(cache_path, claude_dir=CLAUDE_DIR, days=WORKLOG_DAYS):
    """{'YYYY-MM-DD': [input, output, cache_write, cache_read], …} per local
    day, summed across every Claude Code session transcript. The transcripts
    are hundreds of MB, so results are cached per file keyed on (size, mtime)
    — a regen reparses only transcripts that changed since the last one."""
    files = sorted(glob.glob(os.path.join(claude_dir, "projects", "*", "*.jsonl")))
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
        if cache.get("v") != 1:
            raise ValueError
    except Exception:
        cache = {"v": 1, "files": {}}
    entries, changed = {}, False
    for f in files:
        try:
            st = os.stat(f)
        except OSError:
            continue
        c = cache["files"].get(f)
        if c and c.get("size") == st.st_size and c.get("mtime") == st.st_mtime:
            entries[f] = c
        else:
            entries[f] = {"size": st.st_size, "mtime": st.st_mtime,
                          "days": _parse_transcript(f)}
            changed = True
    if changed or set(entries) != set(cache["files"]):
        try:
            tmp = cache_path + ".tmp"
            json.dump({"v": 1, "files": entries}, open(tmp, "w"))
            os.replace(tmp, cache_path)
        except OSError:
            pass                       # cache is an optimization, never a failure
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    total = {}
    for e in entries.values():
        for day, v in e["days"].items():
            if day >= cutoff:
                t = total.setdefault(day, [0, 0, 0, 0])
                for i in range(4):
                    t[i] += v[i]
    return total


def today_line(commits):
    """The overview's one-liner: 'N commits across M repos today'."""
    midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0,
                                               microsecond=0).timestamp()
    today = [c for c in commits if c["t"] >= midnight]
    if not today:
        return "Today · no commits yet"
    repos = len({c["r"] for c in today})
    n = len(today)
    return (f'Today · <b>{n} commit{"s" if n != 1 else ""}</b> across '
            f'<b>{repos} repo{"s" if repos != 1 else ""}</b>')


def worklog_html(commits, tokens=None):
    """The Work Log view body. Data is embedded once; the range filter, charts,
    and day-grouped list all re-render client-side (no regen round-trip).
    `tokens` is collect_tokens() output; the day's chart series is the tokens
    actually processed (input + output + cache writes) — cache reads are ~50×
    larger and would flatten everything else. Two measures of different scale
    (commits, tokens) = two charts sharing the time axis, never a dual axis."""
    data = json.dumps(commits).replace("</", "<\\/")
    tok = {d: v[0] + v[1] + v[2] for d, v in (tokens or {}).items()}
    tokchart = ""
    if tok:
        tokchart = """
  <div class="wlcap">Claude tokens / day <span class="wlcapsub">in + out + cache writes · cache reads excluded</span></div>
  <div class="wlchart" id="wltokchart"><div class="wltip" id="wltoktip"></div></div>"""
    return """<div class="dhead"><span class="dname">Work Log</span>
    <span class="dthesis" id="wlsum"></span></div>
  <div class="wlbar">
    <span class="fbtn" onclick="wlSet('today',this)">Today</span>
    <span class="fbtn on" onclick="wlSet('week',this)">Week</span>
    <span class="fbtn" onclick="wlSet('month',this)">Month</span>
    <span class="fbtn" onclick="wlSet('quarter',this)">3 months</span>
    <button class="standup" id="standupbtn" onclick="copyStandup(this)">Copy as standup</button>
  </div>
  <div class="wlcap">commits / day</div>
  <div class="wlchart" id="wlchart"><div class="wltip" id="wltip"></div></div>""" + tokchart + """
  <div id="wllist"></div>
<script>
var WORKLOG=""" + data + """;
var WLTOKENS=""" + json.dumps(tok) + """;
var WL_RANGE='week';
var WL_DAYS={today:1,week:7,month:31,quarter:92};
function wlDayKey(d){return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2);}
function wlFmtDay(d){return d.toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'});}
function wlSet(range,btn){
  WL_RANGE=range;
  document.querySelectorAll('#v-worklog .fbtn').forEach(function(b){b.classList.remove('on')});
  btn.classList.add('on');
  wlRender();
}
function wlWindow(){
  var end=new Date();end.setHours(0,0,0,0);
  var start=new Date(end);start.setDate(end.getDate()-(WL_DAYS[WL_RANGE]-1));
  return [start,end];
}
function wlFmtNum(n){
  if(n>=1e6)return (n/1e6>=10?Math.round(n/1e6):(n/1e6).toFixed(1))+'M';
  if(n>=1e3)return Math.round(n/1e3)+'k';
  return String(n);
}
function wlRender(){
  var se=wlWindow(),start=se[0],end=se[1];
  var order=[];
  for(var d=new Date(start);d<=end;d.setDate(d.getDate()+1))order.push(wlDayKey(d));
  var cs=WORKLOG.filter(function(c){return c.t*1000>=start.getTime();});
  var repos={};cs.forEach(function(c){repos[c.r]=1;});
  document.getElementById('wlsum').textContent=
    cs.length+' commits · '+Object.keys(repos).length+' repos in range';
  var counts={};order.forEach(function(k){counts[k]=0;});
  cs.forEach(function(c){var k=wlDayKey(new Date(c.t*1000));
    if(k in counts)counts[k]++;});
  wlBarChart('wlchart','wltip',order,counts,'wlmark',
    function(v){return v+' commit'+(v!==1?'s':'');},String);
  if(document.getElementById('wltokchart')){
    var tv={};order.forEach(function(k){tv[k]=WLTOKENS[k]||0;});
    wlBarChart('wltokchart','wltoktip',order,tv,'wlmark2',
      function(v){return wlFmtNum(v)+' tokens';},wlFmtNum);
  }
  wlList(cs);
}
function wlBarChart(holderId,tipId,order,vals,markCls,fmtTip,fmtAxis){
  var max=1;order.forEach(function(k){if(vals[k]>max)max=vals[k];});
  var W=920,H=120,L=40,B=18,T=8,pw=(W-L-6)/order.length;
  var svgNS='http://www.w3.org/2000/svg';
  var svg=document.createElementNS(svgNS,'svg');
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  svg.setAttribute('class','wlsvg');
  function line(x1,y1,x2,y2){var l=document.createElementNS(svgNS,'line');
    l.setAttribute('x1',x1);l.setAttribute('y1',y1);l.setAttribute('x2',x2);
    l.setAttribute('y2',y2);l.setAttribute('class','wlgrid');svg.appendChild(l);}
  function text(x,y,s,anchor){var t=document.createElementNS(svgNS,'text');
    t.setAttribute('x',x);t.setAttribute('y',y);t.setAttribute('class','wllbl');
    if(anchor)t.setAttribute('text-anchor',anchor);
    t.textContent=s;svg.appendChild(t);}
  // one y axis: baseline + max (+ a midpoint when it labels cleanly)
  var y0=H-B,y1=T,plotH=y0-y1;
  line(L,y0,W,y0);text(L-5,y0+3,'0','end');
  line(L,y1,W,y1);text(L-5,y1+3,fmtAxis(max),'end');
  if(max>=4&&(max%2===0||max>=1000)){
    var ym=y0-plotH/2;line(L,ym,W,ym);text(L-5,ym+3,fmtAxis(max/2),'end');}
  var step=order.length<=7?1:(order.length<=31?7:14);
  var holder=document.getElementById(holderId);
  var tip=document.getElementById(tipId);
  order.forEach(function(k,i){
    var x=L+i*pw,c=vals[k];
    var day=new Date(k+'T00:00:00');
    if(i%step===0)text(x+pw/2,H-4,day.toLocaleDateString(undefined,{month:'short',day:'numeric'}),'middle');
    var bw=Math.max(2,Math.min(24,pw*0.7));
    if(c>0){
      var r=document.createElementNS(svgNS,'rect');
      var bh=Math.max(2,plotH*c/max);
      r.setAttribute('x',x+(pw-bw)/2);r.setAttribute('y',y0-bh);
      r.setAttribute('width',bw);r.setAttribute('height',bh);
      r.setAttribute('rx',2);r.setAttribute('class',markCls);
      svg.appendChild(r);
    }
    // full-height invisible hit target: hover works on empty days too
    var hit=document.createElementNS(svgNS,'rect');
    hit.setAttribute('x',x);hit.setAttribute('y',y1);
    hit.setAttribute('width',pw);hit.setAttribute('height',plotH);
    hit.setAttribute('fill','transparent');
    hit.addEventListener('mousemove',function(ev){
      tip.textContent=wlFmtDay(day)+' · '+fmtTip(c);
      tip.style.display='block';
      var box=holder.getBoundingClientRect();
      tip.style.left=Math.min(ev.clientX-box.left+12,box.width-tip.offsetWidth-4)+'px';
      tip.style.top=(ev.clientY-box.top-26)+'px';
    });
    hit.addEventListener('mouseleave',function(){tip.style.display='none';});
    svg.appendChild(hit);
  });
  var old=holder.querySelector('svg');if(old)old.remove();
  holder.appendChild(svg);
}
function wlList(cs){
  var box=document.getElementById('wllist');box.textContent='';
  if(!cs.length){var e=document.createElement('div');e.className='vempty';
    e.textContent='No commits in this range.';box.appendChild(e);return;}
  var byDay={},order=[];
  cs.forEach(function(c){var k=wlDayKey(new Date(c.t*1000));
    if(!byDay[k]){byDay[k]=[];order.push(k);}byDay[k].push(c);});
  order.forEach(function(k){
    var g=document.createElement('div');g.className='sgroup';
    var h=document.createElement('div');h.className='sgtitle';
    h.textContent=wlFmtDay(new Date(k+'T00:00:00'));
    var n=document.createElement('span');n.className='sgcount';
    n.textContent=byDay[k].length;h.appendChild(n);g.appendChild(h);
    byDay[k].forEach(function(c){
      var row=document.createElement('div');row.className='wlrow';
      var r=document.createElement('span');r.className='wlrepo';r.textContent=c.r;
      var s=document.createElement('span');s.className='wlmsg';s.textContent=c.s;
      var t=document.createElement('span');t.className='wltime';
      t.textContent=new Date(c.t*1000).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'});
      row.appendChild(r);row.appendChild(s);row.appendChild(t);g.appendChild(row);
    });
    box.appendChild(g);
  });
}
function copyStandup(btn){
  var end=new Date();end.setHours(0,0,0,0);          // today 00:00
  var start=new Date(end);start.setDate(end.getDate()-1);
  var cs=WORKLOG.filter(function(c){var ms=c.t*1000;
    return ms>=start.getTime()&&ms<end.getTime();});
  var lines=['Standup — '+wlFmtDay(start)+':'];
  if(!cs.length)lines.push('- no commits');
  var byRepo={},order=[];
  cs.forEach(function(c){if(!byRepo[c.r]){byRepo[c.r]=[];order.push(c.r);}byRepo[c.r].push(c.s);});
  order.forEach(function(r){byRepo[r].reverse().forEach(function(s){lines.push('- '+r+': '+s);});});
  var txt=lines.join('\\n');
  function done(){var old=btn.textContent;btn.textContent='Copied ✓';
    setTimeout(function(){btn.textContent=old;},1500);}
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(txt).then(done,function(){wlFallbackCopy(txt);done();});
  }else{wlFallbackCopy(txt);done();}
}
function wlFallbackCopy(txt){
  var ta=document.createElement('textarea');ta.value=txt;
  ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);
  ta.select();try{document.execCommand('copy');}catch(e){}ta.remove();
}
wlRender();
</script>"""


# --------------------------------------------------------------------------- #
# Roadmap — the Now/Next of every project that keeps a ROADMAP.md.
# --------------------------------------------------------------------------- #
ROADMAP_LOCATIONS = ("project-management/ROADMAP.md", "docs/ROADMAP.md", "ROADMAP.md")
ROADMAP_ITEMS_MAX = 8           # per section; the full file is one click away
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_ITEM = re.compile(r"^\s{0,3}(?:[-*+]|\d+\.)\s+(.*)")


def _clean_item(text):
    """One roadmap bullet → plain one-liner (checkbox/link/emphasis stripped)."""
    text = re.sub(r"^\[[ xX]\]\s*", "", text.strip())
    text = _MD_LINK.sub(r"\1", text)
    text = text.replace("**", "").replace("`", "")
    text = " ".join(text.split())
    return text[:199] + "…" if len(text) > 200 else text


def parse_roadmap(text):
    """{'now': […], 'next': […], 'top': […]} — unchecked bullets under the Now
    and Next headings; `top` is the file's first bullets, the fallback when a
    roadmap uses neither heading."""
    sections = {"now": [], "next": [], "top": []}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].strip().lower()
            current = ("now" if head.startswith("now")
                       else "next" if head.startswith("next") else None)
            continue
        m = _ITEM.match(line)
        if not m or m.group(1).lstrip().startswith("[x]") or m.group(1).lstrip().startswith("[X]"):
            continue
        item = _clean_item(m.group(1))
        if not item:
            continue
        if current:
            sections[current].append(item)
        if len(sections["top"]) < ROADMAP_ITEMS_MAX:
            sections["top"].append(item)
    return sections


def collect_roadmaps(project_dirs):
    """[{name, file, rel, now, next, top}, …] for every project that has a
    roadmap in one of the conventional spots (first hit wins)."""
    out = []
    for name, pdir in sorted(project_dirs):
        root = os.path.expanduser(pdir)
        for rel in ROADMAP_LOCATIONS:
            f = os.path.join(root, rel)
            if not os.path.isfile(f):
                continue
            try:
                sec = parse_roadmap(open(f, encoding="utf-8", errors="ignore").read())
            except Exception:
                break
            out.append({"name": name, "file": f, "rel": rel, **sec})
            break
    return out


def roadmaps_html(roadmaps):
    """The Roadmap view body: one card per project, Now/Next (or top items),
    each titled with a link to the full file."""
    esc = html.escape
    out = [f'''<div class="dhead"><span class="dname">Roadmap</span>
    <span class="dthesis">{len(roadmaps)} projects with a ROADMAP.md</span></div>''']
    if not roadmaps:
        out.append('<div class="vempty">No ROADMAP.md found. Looked for '
                   + ", ".join(ROADMAP_LOCATIONS) + " in each project.</div>")

    def items(label, arr):
        rows = [f'<div class="rmsec">{label}</div>']
        for it in arr[:ROADMAP_ITEMS_MAX]:
            rows.append(f'<div class="rmitem">{esc(it)}</div>')
        if len(arr) > ROADMAP_ITEMS_MAX:
            rows.append(f'<div class="rmmore">+{len(arr) - ROADMAP_ITEMS_MAX} more</div>')
        return "".join(rows)

    for r in roadmaps:
        body = ""
        if r["now"]:
            body += items("Now", r["now"])
        if r["next"]:
            body += items("Next", r["next"])
        if not body:
            body = (items("Top items", r["top"]) if r["top"]
                    else '<div class="rmmore">roadmap is empty</div>')
        uri = esc(Path(r["file"]).as_uri())
        out.append(f'''<div class="sgroup">
  <div class="sgtitle">{esc(r["name"])}<a class="rmlink" href="{uri}">{esc(r["rel"])}</a></div>
  {body}
</div>''')
    return "".join(out)


def skills_html(grouped):
    """The Skills view body: live search box + grouped rows with count badges."""
    esc = html.escape
    total = sum(len(entries) for _, entries in grouped)
    out = [f'''<div class="dhead"><span class="dname">Skills</span>
    <span class="dthesis">{total} Claude Code skills · plugins, projects, user</span></div>
  <input class="vsearch" id="skillq" type="text" placeholder="Search skills…"
    spellcheck="false" oninput="skillFilter(this.value)">''']
    if not grouped:
        out.append('<div class="vempty">No SKILL.md files found under ~/.claude '
                   'or your projects’ .claude/skills folders.</div>')
    for label, entries in grouped:
        rows = []
        for s in entries:
            q = esc(f'{s["name"]} {s["desc"]}'.lower(), quote=True)
            hint_cls = "skhint auto" if s["invoke"] == "auto" else "skhint"
            rows.append(
                f'<div class="skrow" data-q="{q}">'
                f'<span class="skname">{esc(s["name"])}</span>'
                f'<span class="skdesc">{esc(s["desc"]) or "—"}</span>'
                f'<span class="{hint_cls}">{esc(s["invoke"])}</span></div>')
        out.append(f'''<div class="sgroup">
  <div class="sgtitle">{esc(label)}<span class="sgcount">{len(entries)}</span></div>
  {"".join(rows)}
</div>''')
    return "".join(out)
