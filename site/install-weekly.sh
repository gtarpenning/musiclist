#!/bin/bash
# Install or update the LaunchAgent that rebuilds and redeploys the site
# every Sunday at 9:00. Safe to re-run; it replaces the previous install.
#
#   site/install-weekly.sh                 # track main
#   MUSICLIST_BRANCH=x site/install-weekly.sh
#   site/install-weekly.sh --uninstall
#
# Logs: ~/.musiclist-site/weekly.log
# Run now: launchctl kickstart gui/$(id -u)/local.musiclist-site
set -euo pipefail

LABEL="local.musiclist-site"
SITE_HOME="$HOME/.musiclist-site"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
BRANCH="${MUSICLIST_BRANCH:-main}"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$PLIST" "$SITE_HOME/bin/weekly.sh"
  echo "removed $LABEL (data in $SITE_HOME left in place)"
  exit 0
fi

mkdir -p "$SITE_HOME/bin" "$HOME/Library/LaunchAgents"
install -m 755 "$(dirname "$0")/weekly.sh" "$SITE_HOME/bin/weekly.sh"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$SITE_HOME/bin/weekly.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MUSICLIST_BRANCH</key>
    <string>$BRANCH</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>0</integer>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$SITE_HOME/weekly.log</string>
  <key>StandardErrorPath</key>
  <string>$SITE_HOME/weekly.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
PLIST

plutil -lint "$PLIST" >/dev/null
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "installed $LABEL: Sundays 9:00, branch $BRANCH"
echo "  log:     $SITE_HOME/weekly.log"
echo "  run now: launchctl kickstart $DOMAIN/$LABEL"
