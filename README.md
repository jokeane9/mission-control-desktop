# Orrery

The observability layer for agent-assisted development: every repo's live
state, and what your agents left behind, in one local window.

Orrery scans your local git repos and renders a dark, keyboard-driven
dashboard — per-project cards with branch / uncommitted / unmerged / unpushed
chips, next to the human facts no tool can derive: what the project *is*, where
prod lives, and the one thing you're pushing on. On top of that it carries
whole-workspace views: a **Sessions** view of what your agents did and what
they left behind, a **Work Log** of commits and token usage over time, plus
Skills, Roadmap, and Worktrees.

Git data is read live from each repo on every render. The human facts live in
one editable JSON file. Nothing leaves your machine — no server, no telemetry,
no accounts.

## Install

Pick whichever fits. **Running from source is the lightest option** and needs
nothing but Python — no installer, no security prompts.

### Run from source (all platforms, zero setup friction)

```sh
git clone https://github.com/jokeane9/orrery
cd orrery
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python app.py        # desktop window
# or, no dependencies at all — just open the generated page in your browser:
./generate.py --open
```

### macOS (packaged app)

- **Homebrew** (recommended once a release is tagged):
  ```sh
  brew install --cask jokeane9/tap/orrery
  ```
- **Direct download:** grab the `.dmg` from
  [Releases](https://github.com/jokeane9/orrery/releases),
  drag the app to Applications.
- **First launch:** if the build isn't notarized yet, macOS will say it
  "cannot verify the developer." Open **System Settings → Privacy & Security**,
  scroll to the Security section, and click **Open Anyway** (one time). This is
  expected for unsigned open-source apps and is safe — the source is right here.

### Windows (packaged app)

Download the setup `.exe` (or the portable `.zip`) from
[Releases](https://github.com/jokeane9/orrery/releases) and
run it. If SmartScreen shows "Windows protected your PC," click **More info →
Run anyway**.

### First run

The app creates a starter config on first launch:

- macOS: `~/Library/Application Support/Orrery/baseline.json`
- Windows: `%APPDATA%\Orrery\baseline.json`
- From source: `baseline.json` next to the scripts

Add one entry per project — a `name`, a `path` to a local git repo, and
whatever facts you want on the card — then hit **Refresh git** (⌘R / Ctrl+R).

**Or let it find your repos.** Add folders to scan under `"roots"` and Mission
Control auto-discovers every git repo inside them, populating each card from the
repo itself — its `CLAUDE.md`/`AGENTS.md`, `README`, or `package.json`. Anything
you set in `baseline.json` still wins; auto-fill only fills the gaps. A repo can
describe its own card exactly with a `.orrery.json` (or a
`orrery:` block in `CLAUDE.md`) — see
[the schema](project-management/autopopulate-schema.md).

```jsonc
{ "roots": ["~/code", "~/work"], "projects": [ /* overrides */ ] }
```

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

## From the terminal

The window isn't always the right surface. The same data, as a command — no
bundle, no Gatekeeper, no notarization:

```sh
./cli.py status              # what needs you, across every repo
./cli.py status --all        # including the clean ones
./cli.py worktrees           # every extra checkout + a safe-to-remove verdict
./cli.py standup --since week
./cli.py skills auth         # search the Claude Code skills catalog
```

Add `--json` to any command to pipe it somewhere:

```sh
./cli.py status --json | jq '.projects[] | select(.attention) | .name'
```

`--strict` makes `status` exit non-zero when something needs you, so it works as
a gate:

```sh
./cli.py status --strict && ./deploy.sh     # won't deploy over unsaved work
```

It reads the **installed app's config**, so the CLI and the window always show
the same workspace. Override with `--data DIR` or `$ORRERY_DATA`.

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

MIT — see [LICENSE](LICENSE). If Orrery earns a place in your day,
donations are welcome (link on the blog / GitHub Sponsors).
