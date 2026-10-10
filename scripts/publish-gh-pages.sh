#!/usr/bin/env bash
# Publishes apps/mobile/dist to the gh-pages branch as a new commit (no force push, so every
# earlier deploy stays in the branch history and can be restored with git revert).
# Build first: cd apps/mobile && EXPO_BASE_URL=/Faceapp EXPO_PUBLIC_STYLE_API_URL=... npm run build:web
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
dist="$root/apps/mobile/dist"
test -f "$dist/index.html" || { echo "Build the web app first (apps/mobile/dist is missing)"; exit 1; }
node "$root/apps/mobile/scripts/check-bundle-secrets.mjs" "$dist"
source_rev="$(git -C "$root" rev-parse --short HEAD)"
work="$(mktemp -d)"
trap 'git -C "$root" worktree remove --force "$work" >/dev/null 2>&1 || true' EXIT
git -C "$root" fetch origin gh-pages
git -C "$root" worktree add --detach "$work" origin/gh-pages
find "$work" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$dist"/. "$work"/
cp "$work/index.html" "$work/404.html"
touch "$work/.nojekyll"
git -C "$work" add -A
if git -C "$work" diff --cached --quiet; then echo "gh-pages already up to date"; exit 0; fi
git -C "$work" commit -m "Deploy web app from $source_rev"
git -C "$work" push origin HEAD:gh-pages
