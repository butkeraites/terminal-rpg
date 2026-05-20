#!/usr/bin/env bash
# Download the binary artifacts from a specific tag's build run into dist/.
#
# Tag-triggered GitHub Actions builds run on the tag's own ref, NOT on main —
# so `gh run list --branch=main` will silently return an older build. This
# helper looks up the run by the tag's displayTitle and downloads correctly.
#
# Usage:
#   ./scripts/download-build.sh v0.17.0
#   ./scripts/download-build.sh           # uses the latest tag-triggered run

set -euo pipefail

cd "$(dirname "$0")/.."

if [ $# -ge 1 ]; then
    tag="$1"
    # Match by headBranch — tag pushes set headBranch to the tag name.
    run_id=$(gh run list --workflow=build.yml --limit 50 \
        --json databaseId,headBranch,conclusion \
        --jq ".[] | select(.headBranch == \"$tag\" and .conclusion == \"success\") | .databaseId" \
        | head -n 1)
else
    # Latest successful run (tag or main — most recent wins).
    run_id=$(gh run list --workflow=build.yml --limit 1 \
        --json databaseId,conclusion \
        --jq '.[] | select(.conclusion == "success") | .databaseId')
fi

if [ -z "$run_id" ]; then
    echo "error: no successful build found${tag:+ for tag $tag}" >&2
    exit 1
fi

echo "==> downloading run $run_id into dist/"
rm -rf dist
mkdir -p dist
gh run download "$run_id" -D dist

# Each artifact lands in its own subdirectory of the same name. Flatten.
cd dist
for d in mournhold-windows-x64.exe mournhold-macos-arm64 mournhold-linux-x64; do
    if [ -d "$d" ]; then
        mv "$d"/* "$d.tmp" 2>/dev/null || true
        rmdir "$d" 2>/dev/null || true
        mv "$d.tmp" "$d"
    fi
done

echo
echo "✓ dist/ ready:"
ls -la
