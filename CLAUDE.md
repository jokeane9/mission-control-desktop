# Orrery — Claude Context

The one file to read first. What this is, how it's built, how it ships, and
where the rest of the truth lives.

---

## What it is

Orrery is a local, single-window dashboard that shows every one of
your git projects' live state — branch, uncommitted/unmerged/unpushed counts —
alongside the human facts no tool can derive (what the project is, where prod
lives, what you're pushing on). Git data is read live per repo; the human facts
live in one editable JSON file. Nothing leaves the machine — no server, no
telemetry, no accounts.

It ships as a free, open-source, donation-supported desktop app for **macOS and
Windows**.

## The one thing to get right: it's ONE app, two build targets

There is a single Python codebase. CI builds the macOS `.dmg` **and** the
Windows `.exe`/`.zip` from the *same commit*. "Mac vs Windows" exists only in
the packaging layer (`packaging/`). The dashboard logic, config, and version
number are shared.

**Consequences for how we work:** one repo, one roadmap, one version number,
one release. `v1.2.0` = both platforms from one tag. A platform-specific bug is
just an issue labeled `platform:mac` / `platform:windows` — never a second
project. Never version the two platforms independently.

## Layers (what calls what)

| File | Role | Notes |
|---|---|---|
| `generate.py` | Scans git + renders `index.html` from `baseline.json`. **stdlib only.** | The engine. `app.py`, `menubar.py` and `cli.py` all import it. Also runnable standalone: `./generate.py --open`. `workspace()` is the shared "what needs you" — GUI and CLI both call it, so they can't disagree. |
| `app.py` | The windowed desktop app (pywebview). This is the packaged entry point. | Regenerates on launch + on a background timer; `Refresh git` button bridges JS→Python. |
| `cli.py` | The terminal surface: `orrery status / worktrees / standup / skills`, `--json`. **stdlib only.** | A *formatter*, deliberately — every command is a thin renderer over a `collect_*()` that already backs the GUI. Logic added here is logic the GUI can't see: put it in `views.py`/`generate.py` instead. Reads the installed app's config, not the source tree's (see `cli.resolve_data_dir`). |
| `menubar.py` | macOS menu-bar companion (rumps). Optional, dev-only. | Not packaged. |
| `gen_icon.py` | Renders `icon_1024.png` (AppKit). macOS-only, run manually. | Source of both `icon.icns` (mac) and `packaging/icon.ico` (win). |
| `packaging/` | Everything platform-specific: PyInstaller spec, entitlements, build scripts, Inno Setup installer, Homebrew cask. | The only place the two platforms diverge. |

## Config model

- `baseline.json` — the user's real config (project paths, account notes).
  **Gitignored. Never commit it.**
- `baseline.sample.json` — shipped starter config. First launch of an installed
  build seeds the user's config from it.
- From source: config + `index.html` sit next to the scripts.
- Installed: they live in the per-user data dir
  (`~/Library/Application Support/Orrery` on macOS,
  `%APPDATA%\Orrery` on Windows) because the signed bundle is
  read-only. See `generate.py:_data_dir()`.

## Build & run

```sh
# run from source (no packaging)
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python app.py        # windowed app
./generate.py --open             # plain HTML in the browser (stdlib only)

# build the distributables locally
./packaging/build_macos.sh                        # -> dist/*.dmg
powershell -File packaging\build_windows.ps1      # -> dist/*.zip + *-setup.exe
```

## Release (fully automated)

```sh
git tag v1.2.0 && git push --tags
```

`.github/workflows/release.yml` then: builds macOS + Windows in parallel →
publishes a GitHub Release with all three artifacts → the `bump-tap` job
updates the Homebrew cask in `jokeane9/homebrew-tap` (via the Contents REST
API, using the `TAP_GITHUB_TOKEN` secret). `brew upgrade` picks it up.

Artifact naming strips the leading `v` (`v1.2.0` → `Orrery-1.2.0.dmg`)
so the cask URL resolves — don't reintroduce the `v`.

## Distribution status

**Currently unsigned** — the free launch path. macOS shows a one-time "Open
Anyway"; Windows shows SmartScreen "Run anyway". The full signing/notarization
story (Apple $99/yr, SignPath free for Windows OSS) is in
[`DISTRIBUTION.md`](DISTRIBUTION.md). CI already supports signing — it's just
adding secrets.

## Repos

- **`jokeane9/orrery`** (public) — this repo, the launch target
- **`jokeane9/homebrew-tap`** (public) — the Homebrew tap, auto-bumped on release
- **`jokeane9/orrery`** (private) — the original personal dev copy with
  real `baseline.json` + history. Not the source of truth for distribution.

## Design language

GitHub-dark palette, SF Mono, matches the vizstack/codebase-viz look. Tokens are
in the `<style>` block of the template string in `generate.py`. Sans-serif stack
falls back through `-apple-system` / `Segoe UI` so it reads right on Windows.

## Where the rest of the truth lives

- `project-management/` — the PM system (roadmap, known issues, ship rules,
  architecture, stack decisions, session log). Read `project-management/README.md`
  for which file to open when.
- `DISTRIBUTION.md` — signing, notarization, stores, the $0 launch path.
- `README.md` — the user-facing install + usage.
