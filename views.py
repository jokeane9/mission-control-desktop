#!/usr/bin/env python3
"""Orrery — top-level dashboard views beyond the project cards.
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
  Worktrees — every extra checkout across the repos, oldest first, each with a
             safe-to-remove verdict. Surfaces the ghost worktrees an interrupted
             Claude Code session leaves under .claude/worktrees/.
  Sessions — Claude Code sessions per repo: live/idle, plus a FOOTPRINT (files
             edited, dirs, branches, PRs opened) that gives each a readable
             identity, and whether one left a worktree behind. Metadata only,
             never prompt or response content.
  PM       — a local, always-there admin scratchpad: one free-text notes file
             the desktop app autosaves. Not synced; lives in the data dir.
"""
import datetime
import glob
import html
import json
import os
import re
import subprocess
import time
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


# A Claude Code worktree lives at <repo>/.claude/worktrees/<name>.
_WT_MARK = os.sep + ".claude" + os.sep + "worktrees" + os.sep


def _worktree_of(cwd):
    """The worktree root, if this path is inside one — else ''."""
    i = cwd.find(_WT_MARK)
    if i < 0:
        return ""
    tail = cwd[i + len(_WT_MARK):].split(os.sep)[0]
    return cwd[:i + len(_WT_MARK)] + tail if tail else ""


_FP_FILES = 12          # top files kept in a session's footprint
_FP_DIRS = 6            # top dirs
_EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")


def _parse_transcript(path):
    """One pass over a session transcript → {"days": …, "meta": …}.

    days: per-day usage totals. Deduped by message id — streaming updates repeat
    a message's usage on several lines; keep the last.
    meta: what the Sessions view needs to give a session an IDENTITY —
      cwd/branch/span/msgs, plus the FOOTPRINT (branches touched, files & dirs
      edited, PRs opened, tool-use profile). `04dc2441` means nothing; "worked
      marketing/ · edited index.html · PR #208" means everything.

    All of the footprint is action-metadata — file paths, branch names, PR URLs,
    tool names. Never prompt or response text; the privacy wall stands.

    One walk on purpose: the transcripts run to hundreds of MB, so a second pass
    would double every cold render. The `tool_use`/`pr-link` lines all carry a
    `timestamp`, so they already pass the fast-path filter — the footprint is
    free of the pass that was already happening.
    """
    import collections
    ids = {}
    meta = {"cwd": "", "branch": "", "start": "", "end": "", "msgs": 0, "wts": [],
            "branches": [], "prs": []}
    files, dirs, tools = collections.Counter(), collections.Counter(), collections.Counter()
    try:
        for line in open(path, encoding="utf-8", errors="ignore"):
            has_usage = '"usage"' in line
            # Fast path: skip lines that carry neither usage nor anything meta
            # needs. Substring checks are far cheaper than json.loads per line.
            if not has_usage and '"cwd"' not in line and '"timestamp"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = d.get("timestamp")
            if ts:
                meta["start"] = meta["start"] or ts     # first line wins
                meta["end"] = ts                        # last line wins
            cwd = d.get("cwd")
            if cwd:
                if not meta["cwd"]:
                    # First cwd — used only to attribute the session to a repo,
                    # which is prefix-matched, so drift can't change the answer.
                    meta["cwd"] = cwd
                # …but worktrees are collected from EVERY cwd, not just the first.
                # A session's cwd migrates: one real transcript starts in a
                # worktree at 05:47 and ends in the parent repo at 23:53. Reading
                # only the first cwd would make catching a worktree depend on line
                # ordering — it happened to work there, and would silently miss
                # any session that entered a worktree after its opening line.
                wt = _worktree_of(cwd)
                if wt and wt not in meta["wts"]:
                    meta["wts"].append(wt)
            gb = d.get("gitBranch")
            if gb:
                meta["branch"] = meta["branch"] or gb   # first, for attribution
                if gb not in meta["branches"]:
                    meta["branches"].append(gb)         # all, for the footprint
            typ = d.get("type")
            if typ in ("user", "assistant"):
                meta["msgs"] += 1
            m = d.get("message") or {}
            content = m.get("content")
            if isinstance(content, list):               # assistant tool calls
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                        continue
                    name = b.get("name") or "?"
                    tools[name] += 1
                    if name in _EDIT_TOOLS:
                        fp = (b.get("input") or {}).get("file_path")
                        if fp:
                            files[os.path.basename(fp)] += 1
                            parent = os.path.basename(os.path.dirname(fp))
                            if parent:
                                dirs[parent] += 1
            elif typ == "pr-link":                      # a PR this session opened
                num, url = d.get("prNumber"), d.get("prUrl")
                if num and not any(p.get("num") == str(num) for p in meta["prs"]):
                    meta["prs"].append({"num": str(num), "url": url or "",
                                        "repo": d.get("prRepository") or ""})
            if has_usage:
                u = m.get("usage")
                if isinstance(u, dict) and ts:
                    ids[m.get("id") or d.get("requestId") or ts] = (ts, u)
    except OSError:
        return {"days": {}, "meta": meta}
    # Trim the footprint before it hits the cache — a big session can edit
    # hundreds of files; the row needs the headline few, not the archive.
    meta["files"] = [f for f, _ in files.most_common(_FP_FILES)]
    meta["dirs"] = [d for d, _ in dirs.most_common(_FP_DIRS)]
    meta["tools"] = dict(tools)
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
    return {"days": days, "meta": meta}


_CACHE_V = 4        # v2 meta; v3 meta["wts"]; v4 footprint (branches/files/dirs/prs/tools)


def _transcripts(cache_path, claude_dir=CLAUDE_DIR):
    """{path: {size, mtime, days, meta}} for every session transcript, cached.

    The transcripts run to hundreds of MB, so results are cached per file keyed
    on (size, mtime) — a regen reparses only what changed. Shared by the Work Log
    (days) and Sessions (meta): one parse feeds both, and neither can drift from
    the other. Bumping _CACHE_V forces one full reparse; it's a cache, so that
    costs time, never data."""
    files = sorted(glob.glob(os.path.join(claude_dir, "projects", "*", "*.jsonl")))
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
        if cache.get("v") != _CACHE_V:
            raise ValueError
    except Exception:
        cache = {"v": _CACHE_V, "files": {}}
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
            parsed = _parse_transcript(f)
            entries[f] = {"size": st.st_size, "mtime": st.st_mtime,
                          "days": parsed["days"], "meta": parsed["meta"]}
            changed = True
    if changed or set(entries) != set(cache["files"]):
        try:
            tmp = cache_path + ".tmp"
            json.dump({"v": _CACHE_V, "files": entries}, open(tmp, "w"))
            os.replace(tmp, cache_path)
        except OSError:
            pass                       # cache is an optimization, never a failure
    return entries


def collect_tokens(cache_path, claude_dir=CLAUDE_DIR, days=WORKLOG_DAYS):
    """{'YYYY-MM-DD': [input, output, cache_write, cache_read], …} per local
    day, summed across every Claude Code session transcript."""
    entries = _transcripts(cache_path, claude_dir)
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


def hero_line(commits, totals):
    """The overview hero — attention-first. Answers "what needs me?" (repos with
    unsaved work) with today's commit count as the calm, secondary figure."""
    midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0,
                                               microsecond=0).timestamp()
    today = sum(1 for c in commits if c["t"] >= midnight)
    tc = f'{today} commit{"" if today == 1 else "s"} today'
    attn = totals.get("attn", 0)
    if attn:
        return (f'<span class="warn">⚠ {attn} project{"" if attn == 1 else "s"} '
                f'need attention</span> · {totals.get("dirty", 0)} uncommitted, '
                f'{totals.get("ahead", 0)} unpushed · <span class="sub">{tc}</span>')
    return f'<span class="ok">✓ All clear</span> · {tc}'


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
  // the most recent day BEFORE today that has commits — so Monday copies
  // Friday, not an empty "yesterday". Groups by repo, oldest-first per repo.
  var todayKey=wlDayKey(new Date()), byDay={};
  WORKLOG.forEach(function(c){var k=wlDayKey(new Date(c.t*1000));
    if(k<todayKey){(byDay[k]=byDay[k]||[]).push(c);}});
  var keys=Object.keys(byDay).sort(), day=keys.length?keys[keys.length-1]:null;
  var cs=day?byDay[day]:[];
  var lines=['Standup — '+(day?wlFmtDay(new Date(day+'T00:00:00')):'no recent commits')+':'];
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


# --------------------------------------------------------------------------- #
# Worktrees — every extra checkout across the dashboard's repos.
#
# A worktree is a second folder holding a checkout of the same repo: one object
# store, many working directories. They go invisible easily — Claude Code makes
# them under .claude/worktrees/ and only auto-removes them on a clean session
# exit, so an interrupted session leaves a ghost folder that no `git status`
# anywhere will ever mention. This view is the workspace-level answer to "what
# checkouts exist that I've forgotten about, and can I delete them?"
#
# The verdict is the point, and it is deliberately pessimistic: "safe" requires
# BOTH a clean tree AND a HEAD reachable from some branch. Removing a worktree
# deletes the folder, not the branch — so a HEAD that lives on a branch survives
# removal, while a detached HEAD's commits become unreachable and die with it.
# Anything we cannot prove safe says NO and why. Never green-light real work.
# --------------------------------------------------------------------------- #
WT_SAFE = "safe to remove"


def _wt_age_days(path):
    """Days since the worktree folder was last touched — the ghost signal. Uses
    os.path.getmtime, not `stat -f %m`: this ships on Windows too. -1 if the
    folder is gone (a prunable registration whose directory was deleted)."""
    try:
        return max(0, int((time.time() - os.path.getmtime(path)) / 86400))
    except OSError:
        return -1


def _wt_parse(porcelain):
    """`git worktree list --porcelain` → [{path, head, branch, detached,
    locked, prunable}, …]. Records are blank-line separated; the main worktree
    is the first record. Unknown attribute lines are ignored."""
    out, cur = [], None
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur = {"path": val, "head": "", "branch": "", "detached": False,
                   "locked": False, "prunable": False}
            out.append(cur)
        elif cur is None:
            continue
        elif key == "HEAD":
            cur["head"] = val
        elif key == "branch":
            cur["branch"] = val.rsplit("/", 1)[-1]      # refs/heads/x → x
        elif key in ("detached", "locked", "prunable"):
            cur[key] = True
    return out


def _wt_verdict(wt):
    """(safe: bool, why: str) for one collected worktree. Every NO carries the
    reason, so the row explains itself without a second click."""
    if wt["prunable"]:
        # The folder is already gone; only the registration is left behind.
        return True, "folder already gone · git worktree prune"
    if wt["dirty"]:
        n = wt["dirty"]
        return False, f"NO — {n} uncommitted file{'s' if n != 1 else ''}"
    if not wt["contained"]:
        return False, "NO — commit is not on any branch"
    if wt["locked"]:
        return False, "NO — worktree is locked"
    return True, WT_SAFE


def _wt_base(repo):
    """The repo's default branch ref for the unmerged count — origin/HEAD when
    the remote publishes one, else a local main/master. '' when neither exists
    (a repo with no remote and no conventional trunk), which zeroes the count
    rather than inventing a baseline."""
    ref = _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    if ref:
        return ref.split("refs/remotes/", 1)[-1]        # → origin/main
    for b in ("main", "master"):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{b}"):
            return b
    return ""


def collect_worktrees(project_dirs):
    """[{repo, repo_path, path, name, branch, detached, age_days, dirty,
    unmerged, safe, why, locked, prunable}, …] — every worktree of every
    dashboard repo except each repo's own main checkout. Sorted oldest-first:
    the ghosts you've forgotten about float to the top."""
    out = []
    for name, pdir in sorted(project_dirs):
        repo = os.path.expanduser(pdir)
        trees = _wt_parse(_git(repo, "worktree", "list", "--porcelain"))
        if len(trees) <= 1:             # the common case: one repo, one checkout
            continue
        base = _wt_base(repo)
        for wt in trees[1:]:            # [0] is the repo's own main checkout
            path = wt["path"]
            live = os.path.isdir(path) and not wt["prunable"]
            # Dirty/unmerged are read from the worktree itself; containment is
            # asked of the parent, whose refs cover every branch in the repo.
            status = _git(path, "status", "--porcelain") if live else ""
            dirty = len([l for l in status.splitlines() if l.strip()])
            head = wt["head"]
            contained = bool(_git(repo, "branch", "-a", "--contains", head)) if head else False
            unmerged = 0
            if head and base:
                n = _git(repo, "rev-list", "--count", f"{base}..{head}")
                unmerged = int(n) if n.isdigit() else 0
            rec = {"repo": name, "repo_path": repo, "path": path,
                   "name": os.path.basename(path.rstrip("/\\")) or path,
                   "branch": wt["branch"], "detached": wt["detached"],
                   "age_days": _wt_age_days(path), "dirty": dirty,
                   "unmerged": unmerged, "locked": wt["locked"],
                   "prunable": wt["prunable"] or not os.path.isdir(path),
                   "contained": contained}
            rec["safe"], rec["why"] = _wt_verdict(rec)
            out.append(rec)
    out.sort(key=lambda w: -w["age_days"])
    return out


def worktrees_html(worktrees):
    """The Worktrees view body: one row per worktree, oldest first, each with
    its safe-to-remove verdict and the exact removal command."""
    esc = html.escape
    risky = [w for w in worktrees if not w["safe"]]
    repos = len({w["repo"] for w in worktrees})
    sub = (f'{len(worktrees)} extra checkout{"s" if len(worktrees) != 1 else ""} '
           f'across {repos} repo{"s" if repos != 1 else ""}'
           + (f' · {len(risky)} hold unsaved work' if risky else ' · all safe to remove'))
    out = [f'''<div class="dhead"><span class="dname">Worktrees</span>
    <span class="dthesis">{esc(sub) if worktrees else "no extra checkouts"}</span></div>''']
    if not worktrees:
        out.append(
            '<div class="vempty">Every repo has just its one checkout — nothing '
            'stray to clean up.<br><span class="wtdim">A worktree is a second '
            'folder checked out from the same repo. Claude Code makes them under '
            '<code>.claude/worktrees/</code> and only removes them on a clean '
            'session exit, so interrupted sessions leave ghosts here.</span></div>')
        return "".join(out)

    by_repo = {}
    for w in worktrees:
        by_repo.setdefault(w["repo"], []).append(w)

    for repo, trees in by_repo.items():
        rows = []
        for w in trees:
            branch = ("(detached)" if w["detached"] or not w["branch"]
                      else w["branch"])
            bcls = "wtbranch det" if w["detached"] or not w["branch"] else "wtbranch"
            age = "—" if w["age_days"] < 0 else f'{w["age_days"]}d'
            chips = []
            if w["dirty"]:
                chips.append(f'<span class="wtchip amber">{w["dirty"]} uncommitted</span>')
            if w["unmerged"]:
                chips.append(f'<span class="wtchip">{w["unmerged"]} unmerged</span>')
            if w["locked"]:
                chips.append('<span class="wtchip">locked</span>')
            vcls = "wtverdict ok" if w["safe"] else "wtverdict no"
            rows.append(f'''<div class="wtrow">
  <div class="wtmain"><span class="wtname">{esc(w["name"])}</span>
    <span class="{bcls}">{esc(branch)}</span>
    <span class="wtage" title="last touched">{age}</span>
    <span class="{vcls}">{esc(w["why"])}</span></div>
  <div class="wtpath" title="{esc(w["path"], quote=True)}">{esc(w["path"])}</div>
  <div class="wtchips">{"".join(chips)}</div>
</div>''')
        cmd = esc(f'git -C {trees[0]["repo_path"]} worktree remove <path>')
        out.append(f'''<div class="sgroup">
  <div class="sgtitle">{esc(repo)}<span class="wtcount">{len(trees)}</span></div>
  {"".join(rows)}
  <div class="wthint">Remove a safe one: <code>{cmd}</code></div>
</div>''')
    return "".join(out)


# --------------------------------------------------------------------------- #
# Sessions — what your agents are doing, and what they left behind.
#
# Worktrees answers "what did my agent leave on disk". This answers "what was it
# doing, and where" — and joins the two: an abandoned worktree and the session
# that stranded it are one story told from both ends. Claude Code only removes a
# worktree on a clean exit, so an interrupted session leaves a folder no
# `git status` mentions and a transcript nobody reads. Here they meet.
#
# PRIVACY, non-negotiable: metadata only — never prompts, never responses, never
# titles. Timings, counts, paths, token totals. The transcripts are the most
# sensitive thing on the machine; this view reads them and must never surface
# their content, even locally.
# --------------------------------------------------------------------------- #
SESSIONS_DAYS = 30              # history window for the view
SESSION_ACTIVE_MIN = 30         # last activity within this → still live


def _iso_local(ts):
    """Transcript timestamp (UTC ISO, 'Z') → local datetime. None if unparseable."""
    try:
        return (datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                .astimezone().replace(tzinfo=None))
    except (ValueError, AttributeError):
        return None


def _match_repo(cwd, project_dirs):
    """Which dashboard project a session's launch dir belongs to — longest path
    prefix wins.

    Prefix-matching rather than un-mangling `~/.claude/projects/<dir>`, because
    that mangling is LOSSY: both `/` and `.` collapse to `-`, so
    `killdate.dev` and `killdate/dev` produce the same directory name. Prefix
    matching also gets worktrees right for free — a session inside
    `killdate.dev/.claude/worktrees/x` still belongs to killdate.dev.
    """
    best_name, best_len = "", -1
    for name, p in project_dirs:
        root = os.path.realpath(os.path.expanduser(p))
        if (cwd == root or cwd.startswith(root + os.sep)) and len(root) > best_len:
            best_name, best_len = name, len(root)
    return best_name


def collect_sessions(project_dirs, cache_path, claude_dir=CLAUDE_DIR,
                     days=SESSIONS_DAYS):
    """[{id, repo, cwd, branch, started, ended, age_min, msgs, tokens,
    worktree, worktree_live, active}, …] — Claude Code sessions in the
    dashboard's repos, newest first.

    Scoped to `project_dirs` like Worktrees: a session in a repo the dashboard
    doesn't know about isn't part of this workspace's story.
    """
    entries = _transcripts(cache_path, claude_dir)
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=days)
    out = []
    for path, e in entries.items():
        meta = e.get("meta") or {}
        cwd = meta.get("cwd") or ""
        if not cwd:
            continue
        cwd = os.path.realpath(cwd)
        repo = _match_repo(cwd, project_dirs)
        if not repo:                        # not a dashboard repo — out of scope
            continue
        end = _iso_local(meta.get("end"))
        start = _iso_local(meta.get("start"))
        if not end or end < cutoff:
            continue
        # Every worktree this session touched, not just the one it opened in.
        # A live one wins: that's the ghost still on disk, and the only one
        # that's actionable.
        wts = [os.path.realpath(w) for w in (meta.get("wts") or [])]
        live = [w for w in wts if os.path.isdir(w)]
        wt = (live or wts or [""])[0]
        tokens = [0, 0, 0, 0]
        for v in (e.get("days") or {}).values():
            for i in range(4):
                tokens[i] += v[i]
        age_min = max(0, int((now - end).total_seconds() / 60))
        # Footprint — what the session DID, so a row reads as work, not a hex id.
        # .get with defaults: a cache written before v4 lacks these until reparse.
        branches = [b for b in (meta.get("branches") or []) if b]
        out.append({
            "id": os.path.basename(path)[:8],
            "repo": repo,
            "cwd": cwd,
            "branch": meta.get("branch") or "",
            "branches": branches,
            "files": meta.get("files") or [],
            "dirs": meta.get("dirs") or [],
            "prs": meta.get("prs") or [],
            "tools": meta.get("tools") or {},
            "started": start.isoformat(timespec="minutes") if start else "",
            "ended": end.isoformat(timespec="minutes"),
            "age_min": age_min,
            "mins": (int((end - start).total_seconds() / 60)
                     if start and end >= start else 0),
            "msgs": meta.get("msgs") or 0,
            "tokens": sum(tokens),
            "worktree": wt,
            # A worktree still on disk after its session ended is the ghost the
            # Worktrees view hunts — this is the other end of that story.
            "worktree_live": bool(live),
            "active": age_min <= SESSION_ACTIVE_MIN,
        })
    out.sort(key=lambda s: s["age_min"])
    return out


def _ago(mins):
    if mins < 60:
        return f"{mins}m ago"
    if mins < 60 * 24:
        return f"{mins // 60}h ago"
    return f"{mins // (60 * 24)}d ago"


def _knum(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def sessions_html(sessions):
    """The Sessions view body: one row per session, newest first, grouped by repo.
    Metadata only — no prompt or response content ever reaches this page."""
    esc = html.escape
    live = [s for s in sessions if s["active"]]
    ghosts = [s for s in sessions if s["worktree_live"] and not s["active"]]
    sub = (f'{len(sessions)} session{"s" if len(sessions) != 1 else ""} · '
           f'last {SESSIONS_DAYS} days'
           + (f' · {len(live)} live' if live else "")
           + (f' · {len(ghosts)} left a worktree behind' if ghosts else ""))
    out = [f'''<div class="dhead"><span class="dname">Sessions</span>
    <span class="dthesis">{esc(sub) if sessions else "no recent sessions"}</span></div>''']
    if not sessions:
        out.append(
            '<div class="vempty">No Claude Code sessions in the last '
            f'{SESSIONS_DAYS} days for these repos.<br><span class="wtdim">'
            'Sessions are read from your local <code>~/.claude</code> transcripts '
            '— timings and counts only, never prompts.</span></div>')
        return "".join(out)

    by_repo = {}
    for s in sessions:
        by_repo.setdefault(s["repo"], []).append(s)

    for repo, rows in by_repo.items():
        body = []
        for s in rows:
            dot = ('<span class="dot green"></span>' if s["active"]
                   else '<span class="dot dim"></span>')
            # Footprint fields via .get(): a hand-built row or a pre-v4 cache
            # entry may not carry them, and the renderer shouldn't crash on that.
            branches = s.get("branches") or []
            files, sdirs, prs = (s.get("files") or [], s.get("dirs") or [],
                                 s.get("prs") or [])
            # Branch: one shows inline; several collapse to a hover-listing count,
            # since a heavy session can span ten branches.
            if len(branches) > 1:
                branch = (f'<span class="wtbranch" title="'
                          + esc("  ".join(branches), quote=True) + '">'
                          + f'{len(branches)} branches</span>')
            elif s["branch"]:
                branch = f'<span class="wtbranch">{esc(s["branch"])}</span>'
            else:
                branch = ""

            # The footprint line — what the session DID, so the row has identity.
            fp = []
            if files:
                shown = ", ".join(esc(f) for f in files[:3])
                extra = len(files) - 3
                fp.append(f'<span class="sffiles">{shown}'
                          + (f' +{extra}' if extra > 0 else "") + '</span>')
            if sdirs:
                fp.append('<span class="sfdirs">'
                          + " ".join(esc(d) + "/" for d in sdirs[:4]) + '</span>')
            # No edits → a read/plan session; show where it ran instead of blank.
            footline = " · ".join(fp) if fp else f'<span class="sfnone">{esc(s["cwd"])}</span>'

            chips = []
            if s["msgs"]:
                chips.append(f'<span class="wtchip">{s["msgs"]} msgs</span>')
            if s["tokens"]:
                chips.append(f'<span class="wtchip">{_knum(s["tokens"])} tokens</span>')
            if s["mins"]:
                chips.append(f'<span class="wtchip">{_ago(s["mins"]).replace(" ago", "")}</span>')
            for p in prs[:5]:                    # click straight through to the PR
                url = esc(p.get("url") or "", quote=True)
                label = "PR #" + esc(p.get("num", "?"))
                chips.append(f'<a class="wtchip pr" href="{url}" target="_blank">{label}</a>'
                             if url else f'<span class="wtchip">{label}</span>')
            # The join that makes this view worth building.
            if s["worktree_live"]:
                chips.append('<span class="wtchip amber" title="' +
                             esc(s["worktree"], quote=True) +
                             '">left a worktree</span>')
            state = ('<span class="wtverdict ok">live</span>' if s["active"]
                     else f'<span class="wtage">{esc(_ago(s["age_min"]))}</span>')
            body.append(f'''<div class="wtrow">
  <div class="wtmain">{dot}<span class="wtname">{esc(s["id"])}</span>{branch}{state}</div>
  <div class="wtpath" title="{esc(s["cwd"], quote=True)}">{footline}</div>
  <div class="wtchips">{"".join(chips)}</div>
</div>''')
        out.append(f'''<div class="sgroup">
  <div class="sgtitle">{esc(repo)}<span class="wtcount">{len(rows)}</span></div>
  {"".join(body)}
</div>''')
    if ghosts:
        out.append('<div class="wthint">Sessions marked <b>left a worktree</b> ended '
                   'without cleaning up — the folder is still on disk. See the '
                   '<b>worktrees</b> tab for whether it is safe to remove.</div>')
    return "".join(out)


# --------------------------------------------------------------------------- #
# PM — a local admin scratchpad. One free-text file the desktop app autosaves
# through the JS→Python bridge; read here at render time and embedded in a
# textarea. Not synced, not in git — it lives in the per-user data dir.
# --------------------------------------------------------------------------- #
NOTES_PLACEHOLDER = ("Your always-there PM scratchpad.\n\n"
                     "Jot anything — priorities, follow-ups, decisions, links. "
                     "It autosaves locally in the desktop app; nothing leaves "
                     "your machine.")


def load_notes(path):
    """The scratchpad text, or '' if there's nothing saved yet."""
    try:
        return open(path, encoding="utf-8").read()
    except OSError:
        return ""


def save_notes(path, text):
    """Persist the scratchpad (atomic-ish via temp file + replace). Returns
    (ok, error)."""
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text if isinstance(text, str) else "")
        os.replace(tmp, path)
        return True, ""
    except OSError as e:
        return False, str(e)


def notes_html(text):
    """The PM view body: a full-height textarea with an autosave status line.
    Editing needs the bridge (packaged app); in a plain browser the pad is
    read-only, matching the config editor's behaviour."""
    esc = html.escape
    head = (f'''<div class="dhead"><span class="dname">PM</span>
    <span class="dthesis">Admin scratchpad · autosaves locally · not synced</span>
    <span class="pmstatus" id="pmstatus"></span></div>
  <textarea class="pmpad" id="pmpad" spellcheck="false" readonly
    placeholder="{esc(NOTES_PLACEHOLDER)}"
    oninput="pmDirty()">{esc(text)}</textarea>
  <div class="pmhint editonly">Autosaves as you type. Also saved when you switch views.</div>
  <div class="pmhint nobridgeonly">Read-only here — open the desktop app to edit and save.</div>''')
    return head + """
<script>
var PM_TIMER=null, PM_SAVED=true;
function pmBridge(){return window.pywebview&&window.pywebview.api&&window.pywebview.api.save_notes;}
function pmStatus(msg,cls){var el=document.getElementById('pmstatus');
  if(el){el.textContent=msg;el.className='pmstatus'+(cls?' '+cls:'');}}
function pmDirty(){
  if(!pmBridge())return;
  PM_SAVED=false;pmStatus('unsaved…','');
  if(PM_TIMER)clearTimeout(PM_TIMER);
  PM_TIMER=setTimeout(pmSave,800);              // debounce: save 0.8s after typing stops
}
function pmSave(){
  if(!pmBridge()||PM_SAVED)return;
  var txt=document.getElementById('pmpad').value;
  pmStatus('saving…','');
  window.pywebview.api.save_notes(txt).then(function(r){
    if(r&&r.ok){PM_SAVED=true;pmStatus('saved ✓','ok');}
    else{pmStatus((r&&r.error)||'save failed','err');}
  }).catch(function(){pmStatus('save failed','err');});
}
// Flush a pending save when the tab/window goes away, so nothing is lost to
// the 15-min meta-refresh or a close.
window.addEventListener('visibilitychange',function(){if(document.hidden)pmSave();});
window.addEventListener('beforeunload',pmSave);
</script>"""
