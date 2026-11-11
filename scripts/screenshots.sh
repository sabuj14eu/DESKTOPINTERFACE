#!/usr/bin/env bash
# SCREENSHOTS OF THE DEPLOYED TERMINAL — nothing to type.   scripts/screenshots.sh
# Opens the terminal that is running on this box (127.0.0.1:8090 — the same process the public
# address serves) in a headless browser and saves the standard set to ./screenshots/<version>-<commit>-…/
# Read-only: page loads and tab clicks only. The browser runs in a throw-away container
# (Microsoft's Playwright image); nothing is installed on the box and nothing touches SignalMesh.
# The pictures contain your (masked) account and balances — they stay on this box, and the
# folder is ignored by git. Copy them out yourself:  scp -r <box>:/srv/signalmesh-terminal/screenshots .
set -euo pipefail
cd "$(dirname "$0")/.."
PW_VERSION=$(sed -n 's/.*"node_modules\/playwright": *{//;T;n;s/.*"version": *"\([^"]*\)".*/\1/p' web/package-lock.json | head -1)
[[ -n "$PW_VERSION" ]] || PW_VERSION=1.49.1
KEY=$(docker compose exec -T terminal printenv SMT_SIGNALMESH_API_KEY | tr -d '\r\n')
[[ -n "$KEY" ]] || { echo "the terminal container is not running (scripts/setup.sh first)"; exit 1; }
mkdir -p screenshots
echo "▶ screenshots of the running terminal (Playwright $PW_VERSION, throw-away container)"
docker run --rm --network host --ipc=host -e TERM_URL=http://127.0.0.1:8090 -e TERM_KEY="$KEY" -e OUT=/out \
  -v "$PWD/web/e2e:/e2e:ro" -v "$PWD/screenshots:/out" "mcr.microsoft.com/playwright:v${PW_VERSION}-noble" \
  sh -c "cd /tmp && npm i --silent --no-audit --no-fund playwright@${PW_VERSION} >/dev/null 2>&1 && PLAYWRIGHT_MODULE=/tmp/node_modules/playwright/index.mjs node /e2e/screenshots.mjs"
echo "▶ done — newest set:"; ls -1dt screenshots/*/ | head -1; cat "$(ls -1dt screenshots/*/ | head -1)manifest.txt"
