#!/usr/bin/env bash
# EXPORT GOLD AND SILVER HISTORY FOR THE TESTS — nothing to type.   scripts/export_history.sh
# Read-only: asks SignalMesh for closed candles (GET, the route the terminal already reads) from
# inside the terminal container and saves them to ./history-export/ as
#   GOLD_15m.json GOLD_1h.json GOLD_4h.json GOLD_1d.json  SILVER_15m.json …
# Kept: bar timestamp exactly as stored (broker server candle boundaries), open, high, low, close, tick volume.
# Removed: the account number in each candle's source. Never read: keys, balances, positions, orders.
# Nothing in SignalMesh, its database or the MT5 reporter is changed.
# Then it tries to send the files to GitHub on their own branch (data/gold-silver-history). If this
# box may not push, it says so and the files stay in ./history-export/ for you to upload by hand.
set -euo pipefail
cd "$(dirname "$0")/.."
SYMBOLS=(${EXPORT_SYMBOLS:-GOLD SILVER}); TFS=(${EXPORT_TFS:-15m 1h 4h 1d})
BRANCH=data/gold-silver-history
docker compose exec -T terminal true 2>/dev/null || { echo "✖ the terminal container is not running (scripts/setup.sh first)"; exit 1; }
rm -rf history-export && mkdir -p history-export
echo "▶ read-only export of closed candles (GET) — ${SYMBOLS[*]} × ${TFS[*]}"
for s in "${SYMBOLS[@]}"; do for tf in "${TFS[@]}"; do
  f="history-export/${s}_${tf}.json"
  if docker compose exec -T terminal python - "$s" "$tf" < scripts/export_history.py > "$f" 2> "$f.err"; then
    rm -f "$f.err"
    python3 - "$f" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(f"   ✔ {d['symbol']:7}{d['tf']:4} {d['count']:5} bars  {d['first_ts']} → {d['last_ts']}  source {','.join(d['source_kinds'])}")
PY
  else
    echo "   ! $s $tf not exported: $(head -c 200 "$f.err")"; rm -f "$f" "$f.err"
  fi
done; done
ls history-export/*.json >/dev/null 2>&1 || { echo "✖ nothing was exported"; exit 1; }
# privacy check before anything leaves the box: no long digit run (an account number) and no key
if grep -lE '"source"|bb_[A-Za-z0-9]|mt5:[0-9]' history-export/*.json; then echo "✖ an export still contains a source / key — NOT sent. Paste this line to me."; exit 1; fi
echo "   ✔ privacy check: no account number, no key in the files"
echo "▶ sending the files to GitHub on their own branch ($BRANCH)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ORIGIN=$(git remote get-url origin)
if git clone -q --depth 1 "$ORIGIN" "$TMP/r" 2>/dev/null \
   && mkdir -p "$TMP/r/adapter/tests/fixtures/history" && cp history-export/*.json "$TMP/r/adapter/tests/fixtures/history/" \
   && git -C "$TMP/r" checkout -q -b "$BRANCH" && git -C "$TMP/r" add adapter/tests/fixtures/history \
   && git -C "$TMP/r" -c user.name="signalmesh-terminal box" -c user.email="terminal-box@users.noreply.github.com" commit -q -m "Recorded Gold and Silver closed candles for the tests (read-only export, account numbers removed)" \
   && git -C "$TMP/r" push -q -f origin "$BRANCH" 2>/dev/null; then
  echo "   ✔ sent. Tell Claude: \"history is on branch $BRANCH\"."
else
  echo "   ! this box may not push to GitHub (it only pulls). The files are in: $PWD/history-export/"
  echo "     Upload them on github.com: repository → Add file → Upload files → choose the 8 files → 'Create a new branch' named $BRANCH."
fi
