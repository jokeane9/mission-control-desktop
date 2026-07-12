# winget manifest

Prepped manifests for listing Mission Control in the Windows Package Manager
(`winget install mission-control`). **Do this after Windows code signing is
live** ([#7](https://github.com/jokeane9/mission-control-desktop/issues/7)) —
winget's validation pipeline rejects low-reputation unsigned installers.

## Files

- `JohnOKeane.MissionControl.installer.yaml` — installer type (inno), URL, SHA256
- `JohnOKeane.MissionControl.locale.en-US.yaml` — name, publisher, description, tags
- `JohnOKeane.MissionControl.yaml` — version/root manifest

These are **templates** with `__VERSION__` / `__INSTALLER_URL__` / `__SHA256__`
placeholders. `PackageIdentifier` is `JohnOKeane.MissionControl` — provisional
until the name decision
([#12](https://github.com/jokeane9/mission-control-desktop/issues/12)); if the
app is renamed, rename these files and the identifier to match.

## Submit a version

1. **Stamp** the templates against the signed release:
   ```sh
   ./packaging/winget/stamp.sh 1.1.0
   # writes out/manifests/j/JohnOKeane/MissionControl/1.1.0/
   ```
2. **Validate + test** on a Windows machine (Windows Sandbox recommended):
   ```sh
   winget validate --manifest packaging\winget\out\manifests\j\JohnOKeane\MissionControl\1.1.0
   winget install  --manifest packaging\winget\out\manifests\j\JohnOKeane\MissionControl\1.1.0
   ```
3. **Open the PR** to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs):
   copy the stamped folder to `manifests/j/JohnOKeane/MissionControl/<version>/`
   in a fork and PR it. The `wingetcreate` tool automates this:
   ```sh
   wingetcreate submit --token <gh-token> packaging\winget\out\manifests\j\JohnOKeane\MissionControl\1.1.0
   ```

## Future updates (already automated)

Once the package exists in winget-pkgs, later releases update it **automatically**
— the `winget` job in [release.yml](../../.github/workflows/release.yml) runs
Microsoft's [wingetcreate](https://github.com/microsoft/winget-create) to submit
the update PR. It's dormant until you enable it:

1. Do the **first submission manually** (steps above) — `wingetcreate update`
   only works on a package that already exists in winget-pkgs.
2. Create a PAT that can fork winget-pkgs and open PRs (classic token with
   `public_repo`, or fine-grained with fork + PR access to your fork), then:
   ```sh
   gh secret set WINGET_TOKEN --repo jokeane9/mission-control-desktop
   ```
3. From then on, every `v*` tag opens a winget update PR on its own. To run it
   by hand instead:
   ```sh
   wingetcreate update JohnOKeane.MissionControl \
     --version 1.2.0 \
     --urls "https://github.com/jokeane9/mission-control-desktop/releases/download/v1.2.0/MissionControl-1.2.0-setup.exe" \
     --submit --token <gh-token>
   ```
