#!/usr/bin/env python3
"""Mission Control — native desktop window (Dock app).
Regenerates the dashboard, then renders index.html in a real app window
via pywebview. Distinct from menubar.py (the always-on menu-bar icon).

Run:  ./.venv/bin/python app.py
Packaged as "Mission Control.app" — see build_app.sh.
"""
import os, sys, threading, time, webview
import generate  # sibling: main(), INDEX, resource_path()

INDEX = generate.INDEX
ICON = generate.resource_path("icon.icns")


class Api:
    """JS bridge: the dashboard's 'Refresh git' button (and ⌘R) call this to
    rescan every repo's git and rewrite index.html; the page then reloads."""
    def refresh(self):
        try:
            generate.main()   # fresh git scan + rewrite index.html
            return True
        except Exception:
            return False


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
