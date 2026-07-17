# winget manifest

Prepped manifests for listing Orrery in the Windows Package Manager
(`winget install orrery`). **Do this after Windows code signing is
live** ([#7](https://github.com/jokeane9/orrery/issues/7)) —
winget's validation pipeline rejects low-reputation unsigned installers.

## Files

- `JohnOKeane.Orrery.installer.yaml` — installer type (inno), URL, SHA256
- `JohnOKeane.Orrery.locale.en-US.yaml` — name, publisher, description, tags
- `JohnOKeane.Orrery.yaml` — version/root manifest

These are **templates** with `__VERSION__` / `__INSTALLER_URL__` / `__SHA256__`
placeholders (each carries a `# yaml-language-server: $schema=…` line for editor
validation; `stamp.sh` fills the placeholders and drops the `# Template:` note).
`PackageIdentifier` is `JohnOKeane.Orrery` — the name is retained for now
(the launch-rename question [#12] was closed as *not planned*, parked in
[`PRODUCT.md`](../../PRODUCT.md) → Open product questions). If the app is ever
renamed, rename these files and the identifier to match.

## Submit a version

1. **Stamp** the templates against the signed release:
   ```sh
   ./packaging/winget/stamp.sh 1.4.0
   # writes out/manifests/j/JohnOKeane/Orrery/1.4.0/
   ```
2. **Validate + test** on a Windows machine (Windows Sandbox recommended):
   ```sh
   winget validate --manifest packaging\winget\out\manifests\j\JohnOKeane\Orrery\1.4.0
   winget install  --manifest packaging\winget\out\manifests\j\JohnOKeane\Orrery\1.4.0
   ```
3. **Open the PR** to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs):
   copy the stamped folder to `manifests/j/JohnOKeane/Orrery/<version>/`
   in a fork and PR it. The `wingetcreate` tool automates this:
   ```sh
   wingetcreate submit --token <gh-token> packaging\winget\out\manifests\j\JohnOKeane\Orrery\1.4.0
   ```

> **Tip:** `stamp.sh` works against any existing release, so you can dry-run the
> tooling today (`./packaging/winget/stamp.sh 1.4.0` stamps the current build and
> proves URL/SHA/layout). Only **submit** a manifest for a *signed* installer —
> winget rejects low-reputation unsigned ones (see the note above).

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
   gh secret set WINGET_TOKEN --repo jokeane9/orrery
   ```
3. From then on, every `v*` tag opens a winget update PR on its own. To run it
   by hand instead:
   ```sh
   wingetcreate update JohnOKeane.Orrery \
     --version 1.4.0 \
     --urls "https://github.com/jokeane9/orrery/releases/download/v1.4.0/Orrery-1.4.0-setup.exe" \
     --submit --token <gh-token>
   ```
