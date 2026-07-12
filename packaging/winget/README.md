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

## Future updates

Once the package exists in winget-pkgs, each new release is a one-liner with
Microsoft's [wingetcreate](https://github.com/microsoft/winget-create):

```sh
wingetcreate update JohnOKeane.MissionControl \
  --version 1.2.0 \
  --urls "https://github.com/jokeane9/mission-control-desktop/releases/download/v1.2.0/MissionControl-1.2.0-setup.exe" \
  --submit --token <gh-token>
```

That can be wired into `release.yml` as a dormant job (gated on a token secret)
like SignPath is — worth doing after the first manual submission lands.
