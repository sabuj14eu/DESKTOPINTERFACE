#!/usr/bin/env bash
# DRY RUN OF THE BOX'S ACCEPTANCE — the whole scripts/verify_parity.py, here, before it meets the box.
# A stand-in engine (the test fixtures served at SignalMesh's own paths, with fresh signals of three senders) and the adapter
# in its REAL provider mode. Test data only. Why it exists: 2.14.0 changed a field the acceptance run reads by exact match;
# the unit tests passed, the box printed 14 FAIL. A check that never ran before the box proves nothing before the box.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
J=$(mktemp -d)
pkill -f "dryrun/fake_engine.py" 2>/dev/null || true; pkill -f "signalmesh_terminal.main:app --port 8202" 2>/dev/null || true
PORT=8201 $PY scripts/dryrun/fake_engine.py >"$J/engine.log" 2>&1 & E=$!
( cd adapter && SMT_PROVIDER=signalmesh SMT_SIGNALMESH_URL=http://127.0.0.1:8201 SMT_SIGNALMESH_API_KEY=bb_dryrun SMT_ENV=test SMT_AUTH=open SMT_WEB_DIST=/nonexistent \
  SMT_JOURNAL_PATH="$J/j.sqlite" $PY -m uvicorn signalmesh_terminal.main:app --port 8202 --log-level warning >"$J/term.log" 2>&1 & echo $! >"$J/term.pid" )
trap 'kill $E "$(cat "$J/term.pid")" 2>/dev/null || true' EXIT
sleep 6
SM_URL=http://127.0.0.1:8201 SM_KEY=bb_dryrun TERM_URL=http://127.0.0.1:8202 ALLOW_FIXTURE_SOURCE=1 $PY scripts/verify_parity.py GOLD SILVER BTC | grep -E "FAIL|GATE|checks, " || true
