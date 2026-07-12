# Mission Control

One window, every project's live state. Mission Control scans your local git
repos and renders a dark, keyboard-driven dashboard: per-project cards with
branch / uncommitted / unmerged / unpushed chips, plus the human facts no tool
can derive — what the project *is*, where prod lives, which accounts it's tied
to, and the one thing you're pushing on right now.

Git data is read live from each repo. The human facts live in one editable
JSON file. Nothing leaves your machine — no server, no telemetry, no accounts.

## Install

Pick whichever fits. **Running from source is the lightest option** and needs
nothing but Python — no installer, no security prompts.

### Run from source (all platforms, zero setup friction)

```sh
git clone https://github.com/jokeane9/mission-control-desktop
cd mission-control-desktop
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python app.py        # desktop window
# or, no dependencies at all — just open the generated page in your browser:
./generate.py --open
```

### macOS (packaged app)

- **Homebrew** (recommended once a release is tagged):
  ```sh
  brew install --cask jokeane9/tap/mission-control-desktop
  ```
- **Direct download:** grab the `.dmg` from
  [Releases](https://github.com/jokeane9/mission-control-desktop/releases),
  drag the app to Applications.
- **First launch:** if the build isn't notarized yet, macOS will say it
  "cannot verify the developer." Open **System Settings → Privacy & Security**,
  scroll to the Security section, and click **Open Anyway** (one time). This is
  expected for unsigned open-source apps and is safe — the source is right here.

### Windows (packaged app)

Download the setup `.exe` (or the portable `.zip`) from
[Releases](https://github.com/jokeane9/mission-control-desktop/releases) and
run it. If SmartScreen shows "Windows protected your PC," click **More info →
Run anyway**.

### First run

The app creates a starter config on first launch:

- macOS: `~/Library/Application Support/Mission Control/baseline.json`
- Windows: `%APPDATA%\Mission Control\baseline.json`
- From source: `baseline.json` next to the scripts

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

Optional: on macOS, `./.venv/bin/python menubar.py` adds a menu-bar companion.
Point `tools.vizstack` / `tools.agentviz` in the config at
[vizstack](https://github.com/jokeane9) / agentviz to get architecture and
pipeline map tabs per project.

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
