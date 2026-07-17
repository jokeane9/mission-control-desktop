# Ship rules

Read before cutting a release or making a versioning call.

Orrery is a **desktop app**, not a live service — there's no prod to
blue/green or roll back. "Shipping" = tag → CI builds both platforms → GitHub
Release → Homebrew cask bump. Users are on whatever version they last installed;
the only rollback is "don't upgrade." So the bar is simply: **never publish a
broken release.** The killdate-kit deploy machinery (canary, N-1 bootable,
strangler) doesn't apply here — the *spirit* (one surgical change per version)
does.

---

## The invariant

**V(N+1) = V(N) + one coherent change.** If a release can't be described in one
line, it's probably two releases. Keep the changelog honest.

---

## Versioning (semver, one number for both platforms)

Never version Mac and Windows independently — one tag builds both.

- **MAJOR** (`2.0.0`) — breaking change to `baseline.json` schema or a dropped platform
- **MINOR** (`1.1.0`) — new feature (new card field, new tab, signing turned on)
- **PATCH** (`1.0.1`) — bug fix, packaging fix, doc-only-in-app change
- **No bump** — README/PM-doc changes that don't ship in the app

The tag strips its leading `v` for artifact names (`v1.1.0` →
`Orrery-1.1.0.dmg`). The cask URL depends on this — don't change it.

---

## Release checklist

1. `main` is green (once `ci.yml` exists, the PR check must pass).
2. Update `CHANGELOG.md` and `project-management/ROADMAP.md` (move the item to Completed).
3. Bump nothing by hand — the version comes from the tag.
4. `git tag vX.Y.Z && git push --tags`.
5. Watch `release.yml`: `macos` + `windows` + `release` + `bump-tap` all green.
6. Verify the three release assets exist and the DMG URL returns 200.
7. Verify the tap cask flipped: `brew info --cask jokeane9/tap/orrery`
   shows the new version.
8. If `bump-tap` fails on auth (HTTP 401), the `TAP_GITHUB_TOKEN` secret is stale
   — re-set it (interactive `gh secret set`, paste at the prompt) and re-run the
   failed job. No new tag needed.

---

## Before writing code for a feature

State the one-line change and its blast radius. If it touches packaging, note
which platform(s). If it introduces temporary/compat code, write its removal
criterion in the PR before the code. Keep the diff to the single change.
