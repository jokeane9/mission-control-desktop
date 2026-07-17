#!/usr/bin/env python3
"""Orrery — macOS menu-bar app.
Glanceable per-project git status; opens the full dashboard.
Reuses generate.py for git scanning + HTML regeneration.

Run:  ./.venv/bin/python menubar.py   (needs rumps: pip install rumps)
"""
import os, subprocess, rumps
import generate  # sibling module: git(), collect(), main(), HERE, REFRESH_MIN

INDEX = generate.INDEX


def scan():
    """Return [(name, path, git_state)] for every project with a .git dir."""
    cfg = generate.load_config()
    rows = []
    for p in cfg["projects"]:
        path = os.path.expanduser(p["path"])
        if not os.path.isdir(os.path.join(path, ".git")):
            continue
        rows.append((p["name"], path, generate.collect(path)))
    return rows


def status_label(name, g):
    """One glanceable line: attention items win over 'clean'."""
    if g["dirty"]:
        mark, tail = "•", f'{g["dirty"]} uncommitted'
    elif g["unmerged"]:
        mark, tail = "•", f'{g["unmerged"]} unmerged'
    elif g["ahead"] not in ("0", "–"):
        mark, tail = "•", f'{g["ahead"]} unpushed'
    else:
        mark, tail = "✓", "clean"
    return f'{mark}  {name:<15} {tail}'


class Orrery(rumps.App):
    def __init__(self):
        super().__init__("◉", quit_button="Quit")
        self.timer = rumps.Timer(self.refresh, generate.REFRESH_MIN * 60)
        self.timer.start()
        self.refresh(None)

    def refresh(self, _):
        rows = scan()
        attention = sum(1 for _, _, g in rows
                        if g["dirty"] or g["unmerged"]
                        or g["ahead"] not in ("0", "–"))
        # title shows a count when something needs attention, else a calm dot
        self.title = f"◉ {attention}" if attention else "◉"

        self.menu.clear()
        items = []
        for name, path, g in rows:
            it = rumps.MenuItem(status_label(name, g),
                                callback=self._open_repo(path))
            items.append(it)
        items.append(rumps.separator)
        items.append(rumps.MenuItem("Open dashboard", callback=self.open_dashboard))
        items.append(rumps.MenuItem("Refresh now", callback=self.refresh_now))
        self.menu = items
        # keep the dashboard file in lockstep with the menu, so an open
        # dashboard window (which meta-reloads the static file) never goes stale
        try:
            generate.main()
        except Exception:
            pass

    def _open_repo(self, path):
        return lambda _: subprocess.run(["open", path])

    def open_dashboard(self, _):
        generate.main()   # always rescan git + rewrite before opening (never serve stale)
        subprocess.run(["open", INDEX])

    def refresh_now(self, _):
        self.refresh(None)   # refresh() now rescans git + rewrites index.html


if __name__ == "__main__":
    Orrery().run()
