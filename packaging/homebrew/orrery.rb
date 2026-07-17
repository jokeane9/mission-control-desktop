# typed: strict
# frozen_string_literal: true

# Homebrew Cask for Orrery (reference copy).
#
# The LIVE cask users install is in the tap repo jokeane9/homebrew-tap
# (Casks/orrery.rb); keep this copy in sync with it.
#
#     brew install --cask jokeane9/tap/orrery
#
# On each release, bump `version` and refresh `sha256`:
#     shasum -a 256 dist/Orrery-<version>.dmg
#
# Renamed from `mission-control-desktop` in v2.0.0. The tap carries a
# cask_renames.json mapping the old token onto this one, so `brew upgrade`
# follows the rename instead of silently stranding every pre-2.0 install.
# Homebrew uninstalls the old artifacts (including "Mission Control.app") from
# the recorded receipt before installing this one, so no second app is left in
# /Applications.
#
# The DMG installs whether or not the app is notarized; unsigned builds show a
# one-time "Open Anyway" prompt (see the README).
cask "orrery" do
  version "1.0.0"
  sha256 "2974a833bd17f80fd907a5820f7589c5c895ad60ef0900f90fdd46b8b73a1035"

  url "https://github.com/jokeane9/orrery/releases/download/v#{version}/Orrery-#{version}.dmg"
  name "Orrery"
  desc "One window, every project's live git state"
  homepage "https://github.com/jokeane9/orrery"

  app "Orrery.app"

  # Both paths: pre-2.0 config lived under the old app name, and an upgraded
  # install has a copy at each (the app migrates rather than moves, so the old
  # one survives on purpose). Zap means "remove every trace" — leaving the
  # legacy dir behind would betray that.
  zap trash: [
    "~/Library/Application Support/Orrery",
    "~/Library/Application Support/Mission Control",
  ]

  caveats <<~EOS
    Orrery isn't notarized yet, so macOS blocks it on first launch with
    "Apple could not verify that 'Orrery' is free of malware."

    To open it (one time):
      System Settings → Privacy & Security → scroll to Security → "Open Anyway"

    Every launch after that opens normally. It's an ad-hoc-signed open-source
    app — the source is at the homepage above.
  EOS
end
