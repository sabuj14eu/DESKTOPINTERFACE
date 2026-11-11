#!/usr/bin/env bash
# AUTO CHECK — one command, everything verified, no back-and-forth.
#   scripts/check.sh            unit tests + typecheck + build + read-only audit
#   scripts/check.sh --parity   additionally run the engine parity check (needs SM_URL, SM_KEY, TERM_URL)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}

echo "▶ adapter: read-only audit + unit tests"
( cd adapter && $PY -m pytest -q )

echo "▶ web: typecheck + unit tests (poller race) + production build"
( cd web && npm ci --no-audit --no-fund --silent && npx tsc -b --noEmit && npx vitest run --reporter=dot && npm run build --silent )

echo "▶ e2e: symbol switching + V2 workspace acceptance (full screen, hide/restore, resize, persistence, signal origin, account switch, forecast journal, phone) — fixture adapter"
[[ -z "${PLAYWRIGHT_MODULE:-}" && -f /opt/node-tools/node_modules/playwright/index.mjs ]] && export PLAYWRIGHT_MODULE=/opt/node-tools/node_modules/playwright/index.mjs
if [[ -n "${PLAYWRIGHT_MODULE:-}" ]] || ( cd web && node -e "require.resolve('playwright')" >/dev/null 2>&1 ); then
  pkill -f "signalmesh_terminal.main:app --port 8097" 2>/dev/null || true   # a test adapter left by an earlier run would answer instead of this build
  JDIR=$(mktemp -d)   # a fresh, throw-away forecast journal for the test adapter (its fixture-only demo module fills it)
  ( cd adapter && SMT_JOURNAL_PATH="$JDIR/journal.sqlite" SMT_JOURNAL_INTERVAL_S=5 SMT_PROVIDER=fixture SMT_ENV=test SMT_AUTH=open SMT_WEB_DIST=../web/dist $PY -m uvicorn signalmesh_terminal.main:app --port 8097 >/tmp/smt-e2e.log 2>&1 & echo $! > /tmp/smt-e2e.pid )
  trap 'kill "$(cat /tmp/smt-e2e.pid 2>/dev/null)" 2>/dev/null || true; pkill -f "signalmesh_terminal.main:app --port 8097" 2>/dev/null || true' EXIT   # never leave a stale test adapter on :8097
  sleep 3
  ( cd web && TERM_URL=http://127.0.0.1:8097 node e2e/switch.mjs && TERM_URL=http://127.0.0.1:8097 node e2e/workspace.mjs ); rc=$?
  kill "$(cat /tmp/smt-e2e.pid)" 2>/dev/null || true
  [[ $rc -eq 0 ]] || { echo "FAIL: e2e"; exit 1; }
else
  echo "   skipped (playwright not installed: cd web && npm i -D playwright && npx playwright install chromium)"
fi

echo "▶ grep audit: no write verbs toward SignalMesh anywhere in the adapter"
if grep -rnE "\.(post|put|patch|delete)\(" adapter/signalmesh_terminal/providers/signalmesh.py; then
  echo "FAIL: write verb found"; exit 1; fi
echo "   ok"

if [[ "${1:-}" == "--parity" ]]; then
  echo "▶ Phase 3 parity: terminal vs engine, field by field"
  $PY scripts/verify_parity.py ${SYMBOLS:-}
fi
echo "✔ ALL CHECKS PASSED"
