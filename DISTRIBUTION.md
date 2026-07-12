# Distributing Mission Control (blog / GitHub releases, outside the app stores)

State of the rules as of July 2026, and exactly what this repo already does
about each one. Short version: **App Store review guidelines do not apply to
direct downloads — but Apple's notarization and Windows code-signing/SmartScreen
mechanics very much do**, and both have tightened since 2024.

## Launching at $0 (the free path)

You can ship this project for nothing. Here's the zero-cost route, and what
each choice costs the user in friction:

| Platform | Free option | User friction |
|---|---|---|
| All | **Run from source** (`pip install && python app.py`) | None — no Gatekeeper/SmartScreen at all. Best path for a dev audience. |
| macOS | **Unsigned DMG + Homebrew cask** | One-time "Open Anyway" in System Settings on first launch. |
| Windows | **SignPath Foundation** (free OSS code signing) | None — a properly signed installer, clears SmartScreen. |

- **Windows is fully solved for free.** SignPath Foundation signs open-source
  projects at no cost. Mission Control qualifies (OSI license, you own the
  repo, actively maintained). The publisher name shows as "SignPath
  Foundation" rather than you — the only trade-off. Apply at
  <https://signpath.org/terms> and add the signing step to the release
  workflow. No reason to pay Certum/Azure unless you want your own name as
  publisher.
- **macOS notarization has no free tier.** Free Apple IDs cannot create a
  Developer ID cert or use the notary service, and there is no OSS fee waiver
  for individual developers. So you either pay $99/yr or ship unsigned. For an
  open-source app aimed at developers, unsigned + "Open Anyway" (documented in
  the README) plus a Homebrew cask is a completely normal launch. Turn on
  notarization later if donations cover the $99 — the CI already supports it,
  it's just adding secrets.
- **Recommended sequence:** launch free (SignPath on Windows, unsigned +
  source + Homebrew on Mac) → if it gains traction and donations, add the
  Apple $99 and flip on macOS notarization. Nothing about the free launch has
  to be redone; you only add credentials.

## macOS

**What's required.** Any app you distribute outside the Mac App Store needs a
Developer ID signature + Apple notarization to open normally. macOS 15 Sequoia
removed the old right-click → Open bypass, and macOS 26 Tahoe tightened
Gatekeeper further: an unsigned app shows "Apple could not verify…" (or the
misleading "app is damaged, move to Trash"), and the only user escape hatch is
System Settings → Privacy & Security → "Open Anyway" + admin password. You
can't ask blog readers to do that.

- Apple Developer Program: **$99/year** (free accounts cannot notarize).
- Notarization is an automated malware scan, **not** App Review — no content
  or business-model judgment. Donation links are completely fine.
- Requirements notarization enforces: hardened runtime, secure timestamp,
  every nested binary signed. For a PyInstaller/CPython app the two
  entitlements in [packaging/entitlements.plist](packaging/entitlements.plist)
  (`allow-unsigned-executable-memory`, `disable-library-validation`) are
  standard and accepted.
- Ship a DMG; sign it, notarize it with `notarytool`, then `stapler staple` so
  it validates offline. [packaging/build_macos.sh](packaging/build_macos.sh)
  does all of this when `CODESIGN_IDENTITY` / `APPLE_ID` / `APPLE_TEAM_ID` /
  `APPLE_APP_PASSWORD` (an app-specific password) are set; unset, it produces
  an unsigned local-testing build.
- Tahoe cosmetic note: the classic `.icns` still works but renders inside a
  generic "glass" tile on macOS 26. Optional polish later: author a `.icon`
  file in Apple's Icon Composer and ship an `Assets.car` alongside the icns.

**Your setup checklist**
1. Join the Apple Developer Program ($99/yr).
2. Create a **Developer ID Application** certificate (Account Holder only),
   export as .p12.
3. Create an app-specific password at appleid.apple.com.
4. Locally: set the four env vars and run `./packaging/build_macos.sh`.
   In CI: add repo secrets `MACOS_CERT_P12` (base64), `MACOS_CERT_PASSWORD`,
   `CODESIGN_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` and
   push a `v*` tag — [.github/workflows/release.yml](.github/workflows/release.yml)
   builds, signs, notarizes, staples, and drafts the release.

## Windows

**What happens unsigned.** Downloads get Mark-of-the-Web; an unsigned
installer triggers the full-screen SmartScreen "Windows protected your PC"
block (More info → Run anyway). Reputation is per-file-hash and **resets to
zero on every release**, and Windows 11 machines with Smart App Control on
block unsigned binaries outright. PyInstaller apps additionally attract AV
false positives. Unsigned is survivable for a technical audience; signing is
the real fix.

**Signing options for an open-source project (2026):**
- **SignPath Foundation** — free for OSS (OSI license, no dual-licensing,
  you own the repo). Publisher name shows as "SignPath Foundation".
- **Certum Open Source cert** — ~€50–70 first year, publisher shows as *you*.
  Cloud "SimplySign" variant avoids the physical smart-card reader.
- **Azure Artifact Signing** (ex "Trusted Signing") — $9.99/mo, GA since
  April 2026 and open to self-employed individuals in US/CA/EU/UK (photo-ID
  validation). Integrates cleanly with GitHub Actions. Re-verify the
  individual-eligibility details at signup — they changed twice in two years.
- EV certificates no longer get instant SmartScreen reputation — per
  Microsoft's own docs there's no reason to pay the EV premium anymore.

**What this repo does.** PyInstaller **onedir** build (single-file exes are
the #1 AV-heuristic trigger) wrapped in an Inno Setup installer
([packaging/windows/installer.iss](packaging/windows/installer.iss)) that
checks the registry for the WebView2 Evergreen runtime and silently runs the
~2 MB Microsoft bootstrapper only if it's missing (Win11 and current Win10
already ship WebView2). A portable zip is produced as a fallback.

### Turning on SignPath signing (the step is already wired)

The `windows` job in [release.yml](.github/workflows/release.yml) already has
the SignPath signing step. It's dormant until the secrets exist, so releases
ship unsigned until you finish enrollment — then it activates automatically.

1. **Apply to SignPath Foundation** (free OSS signing) at
   <https://signpath.org/terms>. Once approved, in the SignPath console create a
   **project** and a **signing policy**.
2. **Match the slugs.** The workflow uses `project-slug: mission-control-desktop`
   and `signing-policy-slug: release-signing`. Either name your SignPath project
   and policy those exact slugs, or edit the two lines in the `Sign installer
   with SignPath` step to match what you created.
3. **Add two secrets** to `jokeane9/mission-control-desktop`:
   ```sh
   gh secret set SIGNPATH_API_TOKEN --repo jokeane9/mission-control-desktop   # from SignPath console
   gh secret set SIGNPATH_ORG_ID    --repo jokeane9/mission-control-desktop   # your SignPath organization id (GUID)
   ```
4. **Tag a release.** The job uploads the unsigned installer, submits it to
   SignPath, and overwrites `dist/*-setup.exe` in place with the signed file
   before the release is published. The **installer** is signed; the portable
   zip's inner `.exe` is not — point users at the installer, or extend the step
   to also sign the exe before it's packaged if you need a signed zip.

**After signing, list it on winget** — free discoverability + `winget upgrade`
support. winget does not accept a low-reputation unsigned installer gracefully,
so do this after signing is in place. The manifests are prepped in
[packaging/winget/](packaging/winget/): run `stamp.sh <version>` and PR the
result (README there has the steps). After that first PR lands, the `winget` job
in the release workflow auto-submits every later version — just add a
`WINGET_TOKEN` secret (a PAT that can fork winget-pkgs and open PRs). Also run
each release through VirusTotal and submit any Defender false positive via
Microsoft's WDSI portal.

## Donations

- **Outside the stores (your blog + GitHub releases): no rules at all.** Link
  GitHub Sponsors / Ko-fi / PayPal from the app, the site, the README — fine.
- **Mac App Store, if ever submitted:** guideline 3.2.2(iv) — donation
  collection *inside* the app is restricted; the tolerated pattern is a link
  that opens the browser. (Also MAS would force App Sandbox onto the app —
  real work for a PyInstaller build.)
- **Microsoft Store, if ever submitted:** policy 10.8.2 governs in-app
  donation flows; a browser link-out is the common OSS pattern. Win32
  submissions also require signed installers (10.2.9) and a privacy policy
  (10.5.1).

## Data hygiene

`baseline.json` is your personal config (project paths, account notes) and is
gitignored — never commit it. The repo ships `baseline.sample.json` only.

## Release flow

```sh
git tag v1.2.0 && git push --tags   # CI builds mac dmg + win installer/zip,
                                    # publishes a GitHub release, and bumps the
                                    # Homebrew cask in jokeane9/homebrew-tap
```

The `bump-tap` job in the workflow downloads the freshly-released DMG, computes
its `sha256`, and pushes the new `version` + checksum into the tap's cask — so
`brew upgrade` picks up every release with no manual step.

### Homebrew tap auto-bump: the one required secret

`bump-tap` pushes to a **different** repo (`jokeane9/homebrew-tap`), which the
default `GITHUB_TOKEN` can't write to. Give it a token once:

1. Create a **fine-grained personal access token** at
   <https://github.com/settings/tokens?type=beta> → Repository access = *only*
   `jokeane9/homebrew-tap` → Permissions → Contents: **Read and write**.
2. Add it to this repo as a secret named `TAP_GITHUB_TOKEN`:
   ```sh
   gh secret set TAP_GITHUB_TOKEN --repo jokeane9/mission-control-desktop
   # (paste the token when prompted — it never touches the repo)
   ```

Without the secret the job simply logs "skipping" and the release still
succeeds; you'd then bump the cask by hand.

Local builds: `./packaging/build_macos.sh` (macOS) ·
`powershell -File packaging\build_windows.ps1` (Windows; needs Python 3.12+,
`pip install -r requirements.txt pyinstaller pillow`, and Inno Setup 6 for the
installer).
