# Stack decisions

Permanent decisions that survive any single session. Reopen only with new
evidence, not preference. Most choices belong in the log or a PR description —
only record here what constrains future builds.

---

## Entry format

**[Decision]** — one-line summary
- **Decided:** YYYY-MM-DD
- **Rationale:** why
- **Alternatives ruled out:** what and why

---

**One codebase, two build targets** — never split Mac and Windows into separate projects/versions
- **Decided:** 2026-07-12
- **Rationale:** The app is shared Python; only packaging differs. One repo/tag/version keeps the platforms from drifting and halves the PM overhead.
- **Alternatives ruled out:** Two repos or two version streams — guarantees the cask/installer/version metadata diverge and doubles every issue.

**PyInstaller onedir, not onefile** — directory build wrapped in an installer
- **Decided:** 2026-07-12
- **Rationale:** onefile self-extraction to temp is the #1 antivirus-heuristic trigger and slows startup; onedir + Inno Setup also means the app exe never carries Mark-of-the-Web after install.
- **Alternatives ruled out:** onefile exe (AV flags); MSIX (must always be signed — non-starter while unsigned).

**GitHub-native PM, not an external tool** — Issues/Projects/Milestones + in-repo docs
- **Decided:** 2026-07-12
- **Rationale:** Solo/OSS project — external PM tools split context away from the code and add a login. GitHub-native lives with the repo and links straight to CI/CD.
- **Alternatives ruled out:** Linear/Notion/Asana — overhead without payoff at this scale.

**Homebrew tap auto-bump via the Contents REST API** — not `git push`
- **Decided:** 2026-07-12
- **Rationale:** Fine-grained PATs authenticate to the REST API as bearer tokens (their native path). Git-over-HTTPS basic auth with `x-access-token` was rejected (HTTP 401) for these tokens.
- **Alternatives ruled out:** `git clone`/`push` with the token in the URL — flaky/rejected for fine-grained PATs.

**Launch unsigned (free), add signing later** — SignPath for Windows, Apple $99/yr for macOS notarization
- **Decided:** 2026-07-12
- **Rationale:** macOS notarization has no free tier; Windows OSS signing (SignPath) is free but needs enrollment. Ship now unsigned + documented "Open Anyway"/"Run anyway"; flip signing on via CI secrets once donations justify it. See `DISTRIBUTION.md`.
- **Alternatives ruled out:** Blocking launch on paid signing — unnecessary for a dev-facing OSS tool.
