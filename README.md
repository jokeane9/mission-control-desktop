# Mission Control

One window, every project's live state. Mission Control scans your local git
repos and renders a dark, keyboard-driven dashboard: per-project cards with
branch / uncommitted / unmerged / unpushed chips, plus the human facts no tool
can derive — what the project *is*, where prod lives, which accounts it's tied
to, and the one thing you're pushing on right now.

Git data is read live from each repo. The human facts live in one editable
JSON file. Nothing leaves your machine — no server, no telemetry, no accounts.

## Install (packaged app)

Grab the latest release for macOS (.dmg) or Windows (setup .exe / portable
zip) and run it. First launch creates a starter config:

- macOS: `~/Library/Application Support/Mission Control/baseline.json`
- Windows: `%APPDATA%\Mission Control\baseline.json`

Add one entry per project — a `name`, a `path` to a local git repo, and
whatever facts you want on the card — then hit **Refresh git** (⌘R / Ctrl+R).

```jsonc
{
  "projects": [
    {
      "name": "my-app",
      "path": "~/code/my-app",
      "thesis": "What this project is, in one line",
      "prod": "https://example.com",
      "stack": "Remix + Postgres",
      "focus": "the single thing being pushed on right now",
      "tier": "major"
    }
  ]
}
```

Keyboard: `⌘0` overview · `⌘1–9` jump to a project · `⌘R` rescan git
(Ctrl on Windows). The page also self-refreshes every 15 minutes.

## Run from source

```sh
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python app.py        # desktop window
./generate.py --open             # or: plain HTML in your browser (stdlib only)
./.venv/bin/python menubar.py    # macOS menu-bar companion (optional)
```

From source, config and output live next to the scripts (`baseline.json`,
`index.html`). Optional: point `tools.vizstack` / `tools.agentviz` in the
config at [vizstack](https://github.com/jokeane9) / agentviz to get
architecture and pipeline map tabs per project.

## Build the apps

See [DISTRIBUTION.md](DISTRIBUTION.md) for the full signing/notarization
story. Locally:

```sh
./packaging/build_macos.sh                              # macOS .app + .dmg
powershell -File packaging\build_windows.ps1            # Windows zip + installer
```

Tagging `v*` runs [.github/workflows/release.yml](.github/workflows/release.yml),
which builds both platforms and drafts a GitHub release.

## License

MIT — see [LICENSE](LICENSE). If Mission Control earns a place in your day,
donations are welcome (link on the blog / GitHub Sponsors).
