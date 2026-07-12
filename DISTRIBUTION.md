# Distributing Mission Control (blog / GitHub releases, outside the app stores)

State of the rules as of July 2026, and exactly what this repo already does
about each one. Short version: **App Store review guidelines do not apply to
direct downloads — but Apple's notarization and Windows code-signing/SmartScreen
mechanics very much do**, and both have tightened since 2024.

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
already ship WebView2). A portable zip is produced as a fallback. Add your
signing step at the marked spot in the release workflow, signing
`MissionControl-*-setup.exe`.

**After signing, list it on winget** (PR a manifest to microsoft/winget-pkgs
pointing at the GitHub release URL) — free discoverability + `winget upgrade`
support. winget does not accept a low-reputation unsigned installer gracefully,
so do this after signing is in place. Also run each release through VirusTotal
and submit any Defender false positive via Microsoft's WDSI portal.

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

## Release flow (once secrets are in place)

```sh
git tag v1.0.0 && git push --tags   # CI builds mac dmg + win installer/zip
                                    # → draft GitHub release with artifacts
```

Local builds: `./packaging/build_macos.sh` (macOS) ·
`powershell -File packaging\build_windows.ps1` (Windows; needs Python 3.12+,
`pip install -r requirements.txt pyinstaller pillow`, and Inno Setup 6 for the
installer).
