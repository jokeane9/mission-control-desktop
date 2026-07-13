#!/usr/bin/env python3
"""Mission Control — native desktop window (Dock app).
Regenerates the dashboard, then renders index.html in a real app window
via pywebview. Distinct from menubar.py (the always-on menu-bar icon).

Run:  ./.venv/bin/python app.py
Packaged as "Mission Control.app" — see build_app.sh.
"""
import os, sys, threading, time, subprocess, webbrowser, webview
import webview.menu as wm
import generate            # sibling: main(), INDEX, resource_path()
import resolve             # sibling: load_github_cache() for sync status
import github_auth         # sibling: GitHub token (keychain) — P3.1
import github_sync as ghsync  # sibling: list repos → github_cache.json — P3.2

INDEX = generate.INDEX
ICON = generate.resource_path("icon.icns")
REPO = "https://github.com/jokeane9/mission-control-desktop"
WINDOW = None            # set in main(); menu handlers drive the page through it


class Api:
    """JS bridge for the dashboard. Refresh git rescans every repo; the config
    editor adds/edits/removes projects in baseline.json. Every method rewrites
    index.html so the page can just reload to show the result."""

    def refresh(self):
        try:
            generate.main()   # fresh git scan + rewrite index.html
            return True
        except Exception:
            return False

    def save_project(self, project, original=None):
        """Add or update one project, then regenerate. Returns
        {ok, error} so the editor can show a message instead of failing silently."""
        try:
            ok, err = generate.upsert_project(project, original)
            if ok:
                generate.main()
            return {"ok": ok, "error": err}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_project(self, name):
        try:
            generate.delete_project(name)
            generate.main()
            return {"ok": True, "error": ""}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --- GitHub (P3.1): token lives in the OS keychain, never in config ---
    def github_status(self):
        try:
            s = github_auth.status()
            if s.get("connected"):     # attach sync info from the cache (P3.3)
                cache = resolve.load_github_cache(ghsync.cache_path())
                s["synced_at"] = cache.get("synced_at")
                s["repo_count"] = len(cache.get("repos", []))
            return s
        except Exception as e:
            return {"connected": False, "login": None, "error": str(e)}

    def github_clone(self, url):
        """Clone an uncloned GitHub repo into the first configured `roots` folder,
        then regenerate so it shows up as a local card (P3.3)."""
        try:
            roots = generate.load_config().get("roots", [])
            if not roots:
                return {"ok": False, "error": "Add a folder to \"roots\" first to clone into."}
            dest = os.path.expanduser(roots[0])
            os.makedirs(dest, exist_ok=True)
            r = subprocess.run(["git", "clone", url], cwd=dest,
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return {"ok": False, "error": (r.stderr or "git clone failed").strip()[:200]}
            generate.main()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def github_connect(self, token):
        try:
            return github_auth.connect(token)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def github_sync(self):
        """Fetch repos → cache, then regenerate so the cards appear."""
        try:
            r = ghsync.sync()
            if r.get("ok"):
                generate.main()
            return r
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def github_disconnect(self):
        try:
            github_auth.disconnect()
            ghsync.clear_cache()       # wipe synced data too
            generate.main()            # GitHub cards vanish
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def _brand_dock():
    """Launcher execs Homebrew python, so macOS labels the app 'Python' with a
    generic icon. Override the Dock icon + name at runtime via AppKit.
    Only needed for the source-tree launcher: a frozen (PyInstaller) build is a
    real bundle with its own Info.plist, and other platforms brand via the exe."""
    if sys.platform != "darwin" or generate.FROZEN:
        return
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle
        # rename: patch the (python framework) main bundle's info dict in place
        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = "Mission Control"
        app = NSApplication.sharedApplication()
        if os.path.isfile(ICON):
            app.setApplicationIconImage_(
                NSImage.alloc().initByReferencingFile_(ICON))
    except Exception:
        pass


def _regen_loop():
    """Keep index.html fresh so the page's 15-min meta-refresh reloads real
    data. In the dev setup menubar.py does this; the packaged app must do it
    itself or the dashboard flags itself STALE after two cycles."""
    while True:
        time.sleep(generate.REFRESH_MIN * 60)
        try:
            generate.main()
        except Exception:
            pass


def _js(code):
    """Run JS in the page from a native menu handler (reuses the existing UI
    actions instead of duplicating them)."""
    if WINDOW is not None:
        try:
            WINDOW.evaluate_js(code)
        except Exception:
            pass


def _open(target):
    """Open a file/folder in the OS default handler."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", target])
        elif os.name == "nt":
            os.startfile(target)            # Windows only
        else:
            subprocess.run(["xdg-open", target])
    except Exception:
        pass


def _menu():
    """The app's main menu. Every action just surfaces something the dashboard
    already does — no new behaviour, so nothing here can get out of sync."""
    return [
        wm.Menu("File", [
            wm.MenuAction("New Project…", lambda: _js("openEditor()")),
            wm.MenuAction("Refresh Git", lambda: _js(
                "refreshGit(document.getElementById('refreshgit'))")),
            wm.MenuSeparator(),
            wm.MenuAction("Open Config File", lambda: _open(generate.BASELINE)),
            wm.MenuAction("Reveal Data Folder", lambda: _open(generate.DATA)),
        ]),
        wm.Menu("GitHub", [
            wm.MenuAction("Connect…", lambda: _js("openGitHub()")),
            wm.MenuAction("Sync Repos", lambda: _js("ghSync()")),
            wm.MenuAction("Disconnect", lambda: _js("ghDisconnect()")),
        ]),
        wm.Menu("Help", [
            wm.MenuAction("Mission Control on GitHub", lambda: webbrowser.open(REPO)),
            wm.MenuAction("Report an Issue", lambda: webbrowser.open(REPO + "/issues")),
        ]),
    ]


def main():
    global WINDOW
    try:
        generate.main()          # fresh git scan + rewrite index.html on launch
    except Exception:
        pass                     # never block the window on a scan hiccup
    _brand_dock()
    threading.Thread(target=_regen_loop, daemon=True).start()
    WINDOW = webview.create_window(
        "Mission Control",
        url=f"file://{INDEX}",
        width=1240, height=900,
        min_size=(760, 560),
        js_api=Api(),
    )
    webview.start(menu=_menu())  # blocks; owns the Dock icon, window + menu bar


if __name__ == "__main__":
    main()
