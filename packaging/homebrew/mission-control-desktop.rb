# typed: strict
# frozen_string_literal: true

# Homebrew Cask for Mission Control (reference copy).
#
# The LIVE cask users install is in the tap repo jokeane9/homebrew-tap
# (Casks/mission-control-desktop.rb); keep this copy in sync with it.
#
#     brew install --cask jokeane9/tap/mission-control-desktop
#
# On each release, bump `version` and refresh `sha256`:
#     shasum -a 256 dist/MissionControl-<version>.dmg
#
# The DMG installs whether or not the app is notarized; unsigned builds show a
# one-time "Open Anyway" prompt (see the README).
cask "mission-control-desktop" do
  version "1.0.0"
  sha256 "2974a833bd17f80fd907a5820f7589c5c895ad60ef0900f90fdd46b8b73a1035"

  url "https://github.com/jokeane9/mission-control-desktop/releases/download/v#{version}/MissionControl-#{version}.dmg"
  name "Mission Control"
  desc "One window, every project's live git state"
  homepage "https://github.com/jokeane9/mission-control-desktop"

  app "Mission Control.app"

  zap trash: "~/Library/Application Support/Mission Control"

  caveats <<~EOS
    Mission Control isn't notarized yet, so macOS blocks it on first launch with
    "Apple could not verify that 'Mission Control' is free of malware."

    To open it (one time):
      System Settings → Privacy & Security → scroll to Security → "Open Anyway"

    Every launch after that opens normally. It's an ad-hoc-signed open-source
    app — the source is at the homepage above.
  EOS
end
