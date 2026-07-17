# Orrery — Architecture

One Python codebase, two build targets. Read before touching how the layers
connect.

---

## Stack

- **Language:** Python 3.12+ (dev on 3.14), standard library where possible
- **UI:** `pywebview` (WKWebView on macOS, Edge WebView2 on Windows) rendering a
  self-contained `index.html`
- **Data:** live `git` CLI per repo + a local `baseline.json`. No database, no
  network, no server.
- **Packaging:** PyInstaller (onedir) → `.app`/`.dmg` on macOS, `.exe` dir +
  Inno Setup installer + zip on Windows
- **CI/CD:** GitHub Actions (`release.yml`) — build both platforms, publish a
  Release, bump the Homebrew tap
- **Distribution:** GitHub Releases + Homebrew cask (`jokeane9/homebrew-tap`).
  Currently unsigned; see `DISTRIBUTION.md`.

---

## How the layers connect

```
baseline.json ─┐
               ├─> generate.py ──> index.html ──> pywebview window (app.py)
git (per repo)─┘        ▲                              │  Refresh git (JS→Py)
                        └──────────────────────────────┘
                     menubar.py (mac, optional) also drives generate.py
```

`generate.py` is the engine and is stdlib-only, so it runs anywhere with no
deps. `app.py` wraps it in a desktop window and is the packaged entry point.
`menubar.py` is a macOS-only dev convenience. The `packaging/` layer is the only
place platform differences live.

---

## Key modules

- `generate.py`
  - `collect(repo)` — per-repo git state (branch, dirty, ahead/behind, unmerged, stashes)
  - `_data_dir()` — source-tree dir when run raw, per-user app-data dir when frozen
  - `load_config()` — reads `baseline.json`, seeds it from the sample on first run
  - `build_viz()` — optional architecture/pipeline map tabs (only if the user
    points `tools.vizstack` / `tools.agentviz` at those tools)
  - `main()` — scans all projects, renders `index.html`
- `app.py` — `webview` window; background regen thread; `Api.refresh()` JS bridge
- `packaging/orrery.spec` — PyInstaller build for both platforms
  (BUNDLE on macOS, COLLECT dir on Windows); strips leading `v` from version

---

## The build/release seam

Source commit → (per platform) PyInstaller → installer/dmg → GitHub Release →
Homebrew cask bump. A tag drives the whole thing; nothing platform-specific
leaks above the `packaging/` layer. See `SHIP-RULES.md` for the sequence and
`CLAUDE.md` for the commands.
