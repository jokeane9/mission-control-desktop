<!-- Keep the diff to one coherent change (see project-management/SHIP-RULES.md). -->

## What & why

<!-- One line: the single change this PR makes, and the reason. -->

## Platform impact

- [ ] Shared (both platforms)
- [ ] macOS packaging
- [ ] Windows packaging

## Checklist

- [ ] `CHANGELOG.md` updated (under Unreleased) if this ships in the app
- [ ] `ruff check --select=E9,F63,F7,F82 .` passes
- [ ] `python generate.py` still renders
- [ ] If it touches packaging, built locally on the affected platform(s)
- [ ] Any temporary/compat code has a removal criterion noted above
