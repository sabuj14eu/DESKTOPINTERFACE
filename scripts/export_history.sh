#!/usr/bin/env bash
# EXPORT GOLD AND SILVER HISTORY, AND CHECK THE SCORER ON IT — nothing to type.   scripts/export_history.sh
# Read-only: asks SignalMesh for closed candles (GET, the route the terminal already reads) from
# inside the terminal container and saves them to ./history-export/ as
#   GOLD_15m.json GOLD_1h.json GOLD_4h.json GOLD_1d.json  SILVER_15m.json …
# Kept: bar timestamp exactly as stored (broker server candle boundaries), open, high, low, close, tick volume.
# Removed: the account number in each candle's source. Never read: keys, balances, positions, orders.
# Nothing in SignalMesh, its database or the MT5 reporter is changed.
# Then it runs the scorer's no-lookahead check on those real bars, inside the container, and prints a summary.
# THE FILES NEVER LEAVE THIS BOX: the folder is ignored by the repository, nothing is committed or sent, and
# no password, token or key is ever asked for. (The repository is public — production data does not go in it.)
set -euo pipefail
cd "$(dirname "$0")/.."
SYMBOLS=(${EXPORT_SYMBOLS:-GOLD SILVER}); TFS=(${EXPORT_TFS:-15m 1h 4h 1d})
docker compose exec -T terminal true 2>/dev/null || { echo "✖ the terminal container is not running (scripts/setup.sh first)"; exit 1; }
rm -rf history-export && mkdir -p history-export
echo "▶ read-only export of closed candles (GET) — ${SYMBOLS[*]} × ${TFS[*]}"
for s in "${SYMBOLS[@]}"; do for tf in "${TFS[@]}"; do
  f="history-export/${s}_${tf}.json"
  if docker compose exec -T terminal python - "$s" "$tf" < scripts/export_history.py > "$f" 2> "$f.err"; then
    rm -f "$f.err"
    python3 - "$f" <<'PY'
import json, sys
from datetime import datetime, timezone
d = json.load(open(sys.argv[1]))
c = d["candles"]
opens = sorted({datetime.fromtimestamp(k["t"], timezone.utc).strftime("%H:%M") for k in c[-40:]}) if d["tf"] in ("4h", "1d") else []
vol = sum(1 for k in c if k.get("tick_volume") not in (None, 0))
print(f"   ✔ {d['symbol']:7}{d['tf']:4} {d['count']:5} bars  {d['first_ts']} → {d['last_ts']}  spacing {d['smallest_bar_spacing_s']}s  tick-volume on {vol}/{len(c)}  source {','.join(d['source_kinds'])}"
      + (f"  bar opens (UTC) {' '.join(opens)}" if opens else ""))
PY
  else
    echo "   ! $s $tf not exported: $(head -c 200 "$f.err")"; rm -f "$f" "$f.err"
  fi
done; done
ls history-export/*.json >/dev/null 2>&1 || { echo "✖ nothing was exported"; exit 1; }
# privacy check of the files themselves: no per-candle source, no account number, no key
if grep -lE '"source"|bb_[A-Za-z0-9]|mt5:[0-9]' history-export/*.json; then echo "✖ an export still contains a source or a key — delete ./history-export/ and paste this line to Claude."; exit 1; fi
echo "   ✔ privacy check: no account number, no key in the files"
echo "▶ scorer no-lookahead check on these recorded bars (inside the container; nothing is written)"
BAD=0
for f in history-export/*.json; do
  docker compose exec -T terminal python /srv/terminal/scripts/history_check.py < "$f" | sed 's/^/   /' || BAD=1
done
echo "▶ forecasting studies: no-lookahead / no-repaint check on these recorded bars"
for s in "${SYMBOLS[@]}"; do
  if [[ -f "history-export/${s}_15m.json" && -f "history-export/${s}_1d.json" ]]; then
    python3 -c 'import json,sys; print(json.dumps({"intraday": json.load(open(sys.argv[1])), "daily": json.load(open(sys.argv[2]))}))' "history-export/${s}_15m.json" "history-export/${s}_1d.json" \
      | docker compose exec -T terminal python /srv/terminal/scripts/history_check.py | sed 's/^/   /' || BAD=1
  fi
done
echo
echo "== SUMMARY — paste everything from the first ▶ line down to here back to Claude =="
echo "   files: $(ls -1 history-export/*.json | wc -l) in $PWD/history-export/ — they stay on this box; nothing was sent anywhere"
echo "   history check: $([[ $BAD -eq 0 ]] && echo 'all OK' || echo 'FAIL — see the lines above')"
[[ $BAD -eq 0 ]]
