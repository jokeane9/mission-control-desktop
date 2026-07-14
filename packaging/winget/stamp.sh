#!/bin/bash
# Stamp the winget manifest templates for a real release.
#
#   ./packaging/winget/stamp.sh 1.1.0
#
# Downloads that version's signed installer from GitHub Releases, computes its
# SHA256, and writes ready-to-submit manifests under out/manifests/... in the
# exact path winget-pkgs expects. Run this only against a SIGNED release —
# winget rejects low-reputation unsigned installers (see README.md).
set -euo pipefail
VERSION="${1:?usage: stamp.sh <version, e.g. 1.1.0>}"
VERSION="${VERSION#v}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="jokeane9/mission-control-desktop"
URL="https://github.com/${REPO}/releases/download/v${VERSION}/MissionControl-${VERSION}-setup.exe"

TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
echo "downloading ${URL}"
curl -fsSL -o "$TMP" "$URL"
SHA="$(shasum -a 256 "$TMP" | awk '{print toupper($1)}')"   # winget expects uppercase hex
echo "sha256: ${SHA}"

OUT="${HERE}/out/manifests/j/JohnOKeane/MissionControl/${VERSION}"
rm -rf "${HERE}/out"; mkdir -p "$OUT"
for f in JohnOKeane.MissionControl.installer.yaml \
         JohnOKeane.MissionControl.locale.en-US.yaml \
         JohnOKeane.MissionControl.yaml; do
  # Drop the "# Template:" note (source-only) but keep the schema comment and
  # the explanatory inline comments; then fill the placeholders.
  grep -v '^# Template:' "${HERE}/${f}" \
    | sed -e "s|__VERSION__|${VERSION}|g" \
          -e "s|__INSTALLER_URL__|${URL}|g" \
          -e "s|__SHA256__|${SHA}|g" \
    > "${OUT}/${f}"
done
echo "stamped -> ${OUT}"
echo
echo "Validate + test locally on Windows, then submit (see packaging/winget/README.md):"
echo "  winget validate --manifest \"${OUT}\""
echo "  winget install  --manifest \"${OUT}\"    # sandbox recommended"
