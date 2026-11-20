"""OUTLOOK VIEWS — Market Outlook, the system's own calls, the Turning Point record. RESHAPE ONLY.

Platform 5.210 opened three read routes so the terminal can show what three of its pages show:

    GET /api/v1/market/outlook?symbol=   three questions from closed DAILY candles (rule market-scenarios-v1)
    GET /api/v1/ledger/system            the system's own daily-trend calls and their scoreboard (system-daily-call-v1)
    GET /api/v1/turning-points           the score of an old skill test (turning-point-record-v1)

Rules of this file (the same as normalize.py):

  * every word, level, state, count, rate and verdict is the platform's. Nothing here is calculated: no level, no
    state, no hit rate, no verdict, no distance. A value the platform did not send is absent — never defaulted;
  * the keys the terminal shows are named below and copied with their values untouched; nested dicts the platform
    builds (a level, a scoreboard, a word-cell) are carried whole;
  * the ONLY thing added is `decimals` — how many digits a price is printed with, from the terminal's mirror of the
    platform's own precision table (normalize.decimals_for), exactly as every other price on the terminal;
  * a route the platform does not have (404) is the named state NOT_BUILT, never an empty panel and never an error
    dressed as "no data";
  * UNKNOWN, NO CLEAR TREND and a SERIES FAULT are the platform's answers and pass through as they are. UNKNOWN is
    not a direction.

WHAT THESE ARE NOT. A description of what price HAS done, a count of calls that were written down before their
outcome, and an old exam's score. None is a forecast, a probability or a signal; nothing here reaches the decision
panel, a ticket, an alert or the forecast journal.
"""
from __future__ import annotations

OUTLOOK_RULE = ("outlook-views-v1: reshape of GET /api/v1/market/outlook, /api/v1/ledger/system and /api/v1/turning-points only — "
                "every word, level, state, count, rate and verdict is the platform's (market-scenarios-v1, system-daily-call-v1, "
                "analyst-ledger-v1, turning-point-record-v1); the terminal calculates none of it and adds only `decimals` for printing "
                "a price; a route the platform does not have is NOT BUILT; UNKNOWN is not a direction; not a forecast, not a signal")

ROUTES = {"outlook": "/api/v1/market/outlook", "ledger": "/api/v1/ledger/system", "turning_points": "/api/v1/turning-points"}

_READ_KEYS = ("rule", "symbol", "tf", "as_of", "state", "reason", "structure", "structure_rule", "bars", "bar_ts", "bar_day", "bar_age_days",
              "close", "atr", "above", "below", "heading", "interesting", "wrong", "series_fault", "swing_highs", "swing_lows")
_OVERVIEW_KEYS = ("symbol", "state", "structure", "close", "bar_ts", "bar_day", "reason", "above", "below", "wrong")
_TRACK_KEYS = ("rule", "analyst", "board", "here", "open", "atr_mult", "days", "fault")
_LEDGER_KEYS = ("rule", "scoring_rule", "analyst", "as_of", "definition", "board", "authority", "plain")
_LEDGER_ROW_KEYS = ("id", "symbol", "direction", "ref_price", "target", "invalidation", "recorded_at", "expires_at", "daily_bar_close", "why",
                    "outcome", "outcome_at", "r", "stored")
_TP_KEYS = ("rule", "as_of", "authority", "plain", "question", "config_hash", "total_rows", "real_rows", "fake_rows", "skill_rows",
            "shadow_rows", "overall", "gate", "words")
_TP_CELL_KEYS = ("symbol", "tf", "model_repo", "model_revision", "config_hash", "readable", "rows", "word", "candidate_words", "held_words",
                 "holdout_word", "holdout_state", "computed_from", "computed_to")
_TP_SEGMENT_KEYS = ("points", "independent", "base", "words", "brier_down", "brier_up", "brier_ref_down", "brier_ref_up", "first_as_of",
                    "last_as_of", "example", "rows_hidden")       # the stored rows themselves are never asked for (rows=0)


def _only(d, keys) -> dict | None:
    """The named keys of a platform dict, values untouched; None when the platform sent no dict."""
    return {k: d[k] for k in keys if k in d} if isinstance(d, dict) else None


def not_built(which: str) -> dict:
    """The platform answered 404 for the route: it has not shipped it. A named state, never an empty panel."""
    return {"state": "NOT_BUILT", "terminal_rule": OUTLOOK_RULE, "route": ROUTES[which],
            "note": (f"NOT BUILT — this SignalMesh build has no GET {ROUTES[which]} route (it arrived in platform 5.210). "
                     "Nothing is shown in its place.")}


def market_outlook(payload: dict | None, symbol: str, decimals_for) -> dict:
    """market-scenarios-v1 for one symbol, the one-line table for the core assets, and the system's counted record."""
    p = payload if isinstance(payload, dict) else {}
    read = _only(p.get("read"), _READ_KEYS)
    sym = str(p.get("symbol") or symbol)
    rows = []
    for x in p.get("overview") or []:
        if isinstance(x, dict):
            rows.append({**_only(x, _OVERVIEW_KEYS), "decimals": decimals_for(str(x.get("symbol") or ""), x.get("close"))})
    return {"state": "OK", "rule": str(p.get("rule") or ""), "terminal_rule": OUTLOOK_RULE, "symbol": sym, "as_of": p.get("as_of"),
            "plain": str(p.get("plain") or ""), "authority": str(p.get("authority") or ""),
            "decimals": decimals_for(sym, (read or {}).get("close")),
            "read": read, "overview": rows, "track": _only(p.get("track"), _TRACK_KEYS)}


def system_ledger(payload: dict | None, decimals_for) -> dict:
    """system-daily-call-v1: the system's own calls, newest first as the platform orders them, and their scoreboard."""
    p = payload if isinstance(payload, dict) else {}
    rows = []
    for x in p.get("rows") or []:
        if isinstance(x, dict):
            rows.append({**_only(x, _LEDGER_ROW_KEYS), "decimals": decimals_for(str(x.get("symbol") or ""), x.get("ref_price"))})
    return {"state": "OK", "terminal_rule": OUTLOOK_RULE, **(_only(p, _LEDGER_KEYS) or {}), "rows": rows}


def turning_points(payload: dict | None, decimals_for) -> dict:
    """turning-point-record-v1: the overall word, why there is no forecast card, one box per cell."""
    p = payload if isinstance(payload, dict) else {}
    cells = []
    for c in p.get("cells") or []:
        if not isinstance(c, dict):
            continue
        cell = _only(c, _TP_CELL_KEYS) or {}
        price = None
        for seg in ("search", "holdout"):
            cell[seg] = _only(c.get(seg), _TP_SEGMENT_KEYS)
            ex = (cell[seg] or {}).get("example")
            if price is None and isinstance(ex, dict):
                price = ex.get("price")
        cell["decimals"] = decimals_for(str(c.get("symbol") or ""), price)
        cells.append(cell)
    return {"state": "OK", "terminal_rule": OUTLOOK_RULE, **(_only(p, _TP_KEYS) or {}), "cells": cells}
