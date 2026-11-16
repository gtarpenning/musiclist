#!/bin/bash
# Weekly refresh for the SF Music Calendar site: update a dedicated clone of
# the repo, scrape every venue, and deploy to Cloudflare Pages.
#
# Run by the local.musiclist-site LaunchAgent (see install-weekly.sh). Everything
# lives in ~/.musiclist-site, outside ~/Desktop, so macOS privacy prompts never
# block it. That clone is managed by this script: it is reset to origin each run.
#
#   MUSICLIST_BRANCH=some-branch ~/.musiclist-site/bin/weekly.sh   # try a branch
set -euo pipefail

SITE_HOME="${MUSICLIST_SITE_HOME:-$HOME/.musiclist-site}"
REPO_URL="https://github.com/gtarpenning/musiclist.git"
REPO="$SITE_HOME/repo"
VENV="$SITE_HOME/venv"
BRANCH="${MUSICLIST_BRANCH:-main}"
# Python 3.12+ with OpenSSL 3: Cloudflare-fronted venues reject OpenSSL 1.1 handshakes
PYTHON="${MUSICLIST_PYTHON:-$HOME/.pyenv/versions/3.13.2/bin/python3}"
LOG="$SITE_HOME/weekly.log"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export MUSICLIST_HOME="$SITE_HOME"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

notify_failure() {
  log "FAILED (exit $1), the live site keeps its previous build"
  /usr/bin/osascript -e "display notification \"Weekly refresh failed. Log: $LOG\" with title \"SF Music Calendar\"" || true
}
trap 'notify_failure $?' ERR

mkdir -p "$SITE_HOME"
cd "$SITE_HOME"  # launchd starts jobs in "/", where tools can't write their caches

started=$(date +%s)
log "weekly refresh starting: branch $BRANCH, data in $SITE_HOME"

log "[1/4] updating repo"
if [ ! -d "$REPO/.git" ]; then
  git clone --quiet "$REPO_URL" "$REPO"
fi
git -C "$REPO" fetch --quiet origin "$BRANCH"
git -C "$REPO" checkout --quiet --force -B "$BRANCH" "origin/$BRANCH"
log "      at $(git -C "$REPO" log -1 --format='%h %s')"

log "[2/4] python env"
if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --disable-pip-version-check -r "$REPO/requirements.txt"

log "[3/4] scrape + build, [4/4] deploy"
"$VENV/bin/python" "$REPO/site/build.py" --deploy

log "done in $(( $(date +%s) - started ))s"
