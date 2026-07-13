#!/usr/bin/env python3
"""Mission Control — native desktop window (Dock app).
Regenerates the dashboard, then renders index.html in a real app window
via pywebview. Distinct from menubar.py (the always-on menu-bar icon).

Run:  ./.venv/bin/python app.py
Packaged as "Mission Control.app" — see build_app.sh.
"""
import os, sys, threading, time, webview
import generate            # sibling: main(), INDEX, resource_path()
import github_auth         # sibling: GitHub token (keychain) — P3.1
import github_sync as ghsync  # sibling: list repos → github_cache.json — P3.2

INDEX = generate.INDEX
ICON = generate.resource_path("icon.icns")


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
            return github_auth.status()
        except Exception as e:
            return {"connected": False, "login": None, "error": str(e)}

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


def main():
    try:
        generate.main()          # fresh git scan + rewrite index.html on launch
    except Exception:
        pass                     # never block the window on a scan hiccup
    _brand_dock()
    threading.Thread(target=_regen_loop, daemon=True).start()
    webview.create_window(
        "Mission Control",
        url=f"file://{INDEX}",
        width=1240, height=900,
        min_size=(760, 560),
        js_api=Api(),
    )
    webview.start()              # blocks; owns the Dock icon + window


if __name__ == "__main__":
    main()
