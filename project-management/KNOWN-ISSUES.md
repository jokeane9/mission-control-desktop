# Known issues

Open issues only. Fixed issues live in git history — remove them here when they
resolve, don't leave closed entries.

---

## ID prefixes

- `B-` — application logic
- `PKG-` — packaging / build (PyInstaller, installer, dmg)
- `SIG-` — signing / distribution (Gatekeeper, SmartScreen, notarization)
- `CI-` — CI/CD workflow
- `P-` — performance

---

## Entry format

**[ID] Short description**
- **Severity:** low / medium / high
- **Symptoms:** what you observe
- **Suspected cause:** if known, else "unknown"
- **Workaround:** if any, else "none"
- **Opened:** YYYY-MM-DD

---

**SIG-1 Unsigned builds trip Gatekeeper / SmartScreen**
- **Severity:** medium (expected, not a bug — tracked so it isn't mistaken for one)
- **Symptoms:** macOS "cannot verify the developer"; Windows "Windows protected your PC"
- **Suspected cause:** builds are intentionally unsigned (free launch path)
- **Workaround:** macOS → System Settings ▸ Privacy & Security ▸ Open Anyway;
  Windows → More info ▸ Run anyway. Documented in README. Resolved by the
  signing roadmap items.
- **Opened:** 2026-07-12

**PKG-1 Windows WebView2 assumed present on older Win10**
- **Severity:** low
- **Symptoms:** on the rare Win10 build without the Evergreen runtime, the window
  could fail to render
- **Suspected cause:** WebView2 not preinstalled on some older Win10
- **Workaround:** the Inno Setup installer already registry-checks and runs the
  Evergreen bootstrapper if missing. The portable **zip** does not — zip users on
  such machines must install WebView2 manually. Prefer the installer.
- **Opened:** 2026-07-12
