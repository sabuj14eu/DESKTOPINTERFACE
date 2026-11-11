"""THE FORMING BAR — display only, never a decision input.

Everything else in this terminal is CLOSED bars: what SignalMesh stores and what its engine
decides on. A closed-bar chart moves once per bar, which is why it looks slow beside MT5.
This module adds the bar that is still forming, from one of two sources, each labelled:

  1. LIVE BRIDGE — SignalMesh's own live chart feed (`/chart/candles.json`, the bot box's
     candle feed with its forming bar and bid/ask, proxied by the platform; the route its own
     /chart page draws from). It is a signed-in dashboard route, so the terminal reads it with
     the SAME SignalMesh session cookie the user's browser already sent. GET only.
  2. BUILT FROM CLOSED 1m BARS — when the bridge is not available: the forming bar of the
     chart's timeframe is the stored 1m bars since that bar opened (open = first open,
     high = max, low = min, close = newest close). It moves once a minute. A display
     aggregate of stored bars; no price in it is invented.

Laws kept here:
  * a forming bar NEVER enters `/candles`, the decision, the levels, an indicator's history
    or the acceptance parity — those stay closed bars only;
  * the bridge's own flags (`forming`, state LIVE / STALE / DOWN / …) pass through verbatim;
    a stale or dead bridge is a named state, never a quiet fallback that looks live;
  * bid / ask are shown only when the bridge sent them, labelled as the bridge's.
"""
from __future__ import annotations

from datetime import datetime, timezone

TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
BRIDGE_TF = {k: str(v) for k, v in TF_MIN.items()}          # the bridge names a timeframe by its minutes
RULE = ("forming-bar-v1: display only. Source 1 = SignalMesh live bridge (forming bar + bid/ask, verbatim). "
        "Source 2 = aggregate of stored closed 1m bars. Never part of /candles, the decision or acceptance.")


def _epoch(v) -> int | None:
    if v in (None, "", 0):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return int((dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp())


def _num(row: dict, *keys):
    for k in keys:
        v = row.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _empty(symbol: str, tf: str, state: str, source: str, error: str = "") -> dict:
    return {"symbol": symbol, "tf": tf, "state": state, "source": source, "bars": [], "bid": None, "ask": None,
            "spread": None, "age_s": None, "error": error, "rule": RULE,
            "as_of": datetime.now(timezone.utc).isoformat()}


def from_bridge(symbol: str, tf: str, payload: dict, last_closed: int | None) -> dict:
    """The platform's bridge reply -> the bars NEWER than the newest stored closed bar.
    Usable only when the reply really is the live feed (not the platform's stored fallback)."""
    out = _empty(symbol, tf, str(payload.get("state") or "UNKNOWN"), "bridge", str(payload.get("error") or ""))
    out["upstream_source"] = str(payload.get("source") or "")
    if payload.get("feed") != "live" or "live_state" in payload:
        out["state"] = str(payload.get("live_state") or out["state"])
        out["error"] = str(payload.get("live_error") or out["error"] or "the platform answered with stored bars, not the live feed")
        return out
    if out["state"] != "LIVE":
        return out
    step = TF_MIN[tf] * 60
    rows = [r for r in (payload.get("candles") or []) if isinstance(r, dict)]
    bars = []
    for i, r in enumerate(rows):
        t = _epoch(r.get("ts", r.get("time")))
        o, h, low, c = _num(r, "open", "o"), _num(r, "high", "h"), _num(r, "low", "l"), _num(r, "close", "c")
        if t is None or None in (o, h, low, c) or t % step:
            continue                                    # not on this timeframe's grid: not drawn
        if last_closed is not None and t <= last_closed:
            continue                                    # the stored closed series already has it
        forming = bool(r.get("forming")) or (i == len(rows) - 1 and bool(payload.get("forming_last")))
        bars.append({"time": t, "open": o, "high": h, "low": low, "close": c, "forming": forming})
    out["bars"] = bars[-3:]
    out["bid"], out["ask"], out["spread"] = payload.get("bid"), payload.get("ask"), payload.get("spread")
    out["age_s"] = payload.get("age_s")
    if not out["bars"]:
        out["state"], out["error"] = "NO_NEWER_BAR", "the live feed has no bar newer than the stored closed series"
    return out


def from_1m(symbol: str, tf: str, candles_1m: dict | None, last_closed: int | None, why: str) -> dict:
    """The forming bar of `tf`, aggregated from stored CLOSED 1m bars."""
    out = _empty(symbol, tf, "CLOSED_ONLY", "closed_1m", why)
    if tf == "1m" or tf == "1d" or last_closed is None:
        out["error"] = why + (" · a 1m chart has no smaller stored bar to build from" if tf == "1m"
                              else " · a daily forming bar needs more 1m bars than one read returns" if tf == "1d" else "")
        return out
    step = TF_MIN[tf] * 60
    start = last_closed + step                          # the open of the bar that is forming now
    rows = []
    for k in (candles_1m or {}).get("candles") or []:
        t = _epoch(k.get("ts"))
        if t is not None and start <= t < start + step:
            rows.append((t, k))
    if not rows:
        out["error"] = why + " · no stored 1m bar inside the forming bar yet"
        return out
    rows.sort(key=lambda x: x[0])
    ks = [k for _, k in rows]
    fr = (candles_1m or {}).get("freshness") or {}
    if str(fr.get("state") or "").upper() != "LIVE":
        out["state"], out["error"] = "STALE", why + f" · stored 1m bars are {fr.get('state', 'UNKNOWN')}"
        return out
    out["state"] = "FROM_1M"
    out["bars"] = [{"time": start, "open": float(ks[0]["open"]), "high": max(float(k["high"]) for k in ks),
                    "low": min(float(k["low"]) for k in ks), "close": float(ks[-1]["close"]), "forming": True}]
    out["built_from"] = {"bars_1m": len(ks), "newest_1m_open": rows[-1][0]}
    return out
