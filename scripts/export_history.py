"""Read-only export of CLOSED candles for the test suite. Runs INSIDE the terminal container
(scripts/export_history.sh pipes it in); prints one JSON document to stdout.

    python - SYMBOL TF < export_history.py

GET only — the same candle route the terminal already reads, with the read key the container
already holds. Nothing is written anywhere by this script, and nothing of SignalMesh changes.

What is kept, per candle: the bar's own timestamp EXACTLY as SignalMesh stores it (so the
broker's day and candle boundaries are preserved), open, high, low, close, and MT5 TICK volume.
What is dropped: everything else. In particular the per-candle `source` ("mt5:<account number>")
is reduced to the word before the colon, so no account number leaves the box. No key, account,
balance, position or order is read or written.
"""
import json
import os
import sys
from datetime import datetime, timezone

import httpx

symbol, tf = sys.argv[1].upper(), sys.argv[2]
url, key = os.environ["SMT_SIGNALMESH_URL"].rstrip("/"), os.environ["SMT_SIGNALMESH_API_KEY"]
raw, asked = None, None
for n in (5000, 2000, 1000, 500):                      # as much history as the route will give
    r = httpx.get(f"{url}/api/v1/market/candles", params={"symbol": symbol, "tf": tf, "n": n}, headers={"Authorization": f"Bearer {key}"}, timeout=60)
    if r.status_code == 200:
        raw, asked = r.json(), n
        break
if raw is None:
    sys.exit(f"{symbol} {tf}: SignalMesh answered HTTP {r.status_code}")


def epoch(ts):
    if isinstance(ts, (int, float)):
        return int(ts)
    return int(datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())


candles, kinds = [], set()
for k in raw.get("candles") or []:
    ts = k.get("ts", k.get("time"))
    kind = str(k.get("source") or "unstated").split(":")[0]          # "mt5:12345678" -> "mt5"
    kinds.add(kind)
    candles.append({"ts": ts, "t": epoch(ts), "open": k["open"], "high": k["high"], "low": k["low"], "close": k["close"],
                    "tick_volume": k.get("tick_volume", k.get("volume"))})
candles.sort(key=lambda c: c["t"])
steps = sorted({b["t"] - a["t"] for a, b in zip(candles, candles[1:])})
print(json.dumps({
    "what": "closed candles exported read-only from SignalMesh for the terminal's tests — genuine broker history, not synthetic",
    "symbol": symbol, "tf": tf, "count": len(candles), "asked_n": asked,
    "first_ts": candles[0]["ts"] if candles else None, "last_ts": candles[-1]["ts"] if candles else None,
    "timestamps": "each bar's `ts` is exactly what SignalMesh stores (bar open); `t` is the same instant in epoch seconds. Bar boundaries are the broker server's, unchanged.",
    "smallest_bar_spacing_s": steps[0] if steps else None,
    "volume": "MT5 TICK volume (number of price changes), not traded volume",
    "source_kinds": sorted(kinds), "account_numbers": "removed", "exported_at": datetime.now(timezone.utc).isoformat(),
    "candles": candles}, separators=(",", ":")))
