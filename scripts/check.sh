#!/usr/bin/env bash
# AUTO CHECK — one command, everything verified, no back-and-forth.
#   scripts/check.sh            unit tests + typecheck + build + read-only audit
#   scripts/check.sh --parity   additionally run the engine parity check (needs SM_URL, SM_KEY, TERM_URL)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}

echo "▶ adapter: read-only audit + unit tests"
( cd adapter && $PY -m pytest -q )

echo "▶ web: typecheck + production build"
( cd web && npm ci --no-audit --no-fund --silent && npx tsc -b --noEmit && npm run build --silent )

echo "▶ grep audit: no write verbs toward SignalMesh anywhere in the adapter"
if grep -rnE "\.(post|put|patch|delete)\(" adapter/signalmesh_terminal/providers/signalmesh.py; then
  echo "FAIL: write verb found"; exit 1; fi
echo "   ok"

if [[ "${1:-}" == "--parity" ]]; then
  echo "▶ Phase 3 parity: terminal vs engine, field by field"
  $PY scripts/verify_parity.py ${SYMBOLS:-}
fi
echo "✔ ALL CHECKS PASSED"
