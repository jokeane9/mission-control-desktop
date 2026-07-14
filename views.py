#!/usr/bin/env python3
"""Mission Control — top-level dashboard views beyond the project cards.
Stdlib only, like generate.py. Each view is a collect_*() (pure data, testable)
plus a *_html() renderer that generate.py drops into the page template.

Views:
  Skills — a searchable catalog of Claude Code skills (plugins, project-local,
           user-level), parsed from SKILL.md frontmatter.
"""
import html
import os

CLAUDE_DIR = os.path.expanduser("~/.claude")
DESC_MAX = 160          # one-line description budget per skill row


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
