#!/usr/bin/env bash
# Upload Mournhold builds to itch.io via butler.
#
# Requires:
#   1. butler authenticated (run `butler login` once on this machine).
#   2. dist/ populated with the artifacts (run the build workflow first:
#      `gh workflow run build.yml --ref main` then download the artifacts).
#   3. The itch project (abidlebob/mournhold by default) exists on itch.io.
#
# Usage:
#   ./scripts/upload-to-itch.sh             # uses version 0.1.0
#   ./scripts/upload-to-itch.sh 0.2.0       # tags the uploads with 0.2.0
#
# To run against a fork or a different game name, override via env:
#   ITCH_USER=other-handle GAME=other-name ./scripts/upload-to-itch.sh

set -euo pipefail

# Always operate from the repo root so dist/ paths resolve.
cd "$(dirname "$0")/.."

ITCH_USER="${ITCH_USER:-abidlebob}"
GAME="${GAME:-mournhold}"
VERSION="${1:-0.1.0}"

# --- sanity checks ---------------------------------------------------------

if [ ! -d dist ]; then
    echo "error: no dist/ directory found. Run the build workflow first:" >&2
    echo "  gh workflow run build.yml --ref main" >&2
    echo "  gh run download \$(gh run list --workflow=build.yml --limit 1 --json databaseId --jq '.[0].databaseId') --dir dist/" >&2
    exit 1
fi

if [ ! -f "$HOME/.config/itch/butler_creds" ]; then
    echo "error: butler not authenticated. Run 'butler login' in this terminal first." >&2
    exit 1
fi

# --- push ------------------------------------------------------------------

push() {
    local file="$1"
    local channel="$2"
    if [ ! -f "dist/$file" ]; then
        echo "skip: dist/$file not found"
        return 0
    fi
    echo
    echo "==> pushing dist/$file -> $ITCH_USER/$GAME:$channel"
    butler push "dist/$file" "$ITCH_USER/$GAME:$channel" --userversion "$VERSION"
}

push mournhold-windows-x64.exe  windows-x64
push mournhold-macos-arm64      osx-arm64
push mournhold-linux-x64        linux-x64
push mournhold-source.zip       source

echo
echo "✓ All pushes complete."
echo "  Dashboard: https://itch.io/dashboard"
echo "  Project:   https://$ITCH_USER.itch.io/$GAME  (visible once you set Public)"
