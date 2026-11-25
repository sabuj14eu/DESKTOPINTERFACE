"""DATA STATES, SIMULATED — what the terminal shows when the feed is stale or SignalMesh cannot be reached.
These states cannot be produced on purpose on production without interrupting the MT5 feed, so they are
produced here: the test provider is made to answer as a stale or a dead upstream would. In neither state
may a READY decision, a fresh setup or a new journal forecast appear."""
import copy

import pytest

from signalmesh_terminal.providers.base import ProviderError


@pytest.fixture
def env(monkeypatch, tmp_path):
    for k, v in (("SMT_PROVIDER", "fixture"), ("SMT_ENV", "test"), ("SMT_AUTH", "open"), ("SMT_ACCESS_TOKEN", ""), ("SMT_WEB_DIST", "/nonexistent"),
                 ("SMT_JOURNAL_PATH", str(tmp_path / "j.sqlite"))):
        monkeypatch.setenv(k, v)
    from fastapi.testclient import TestClient
    from signalmesh_terminal import routes
    from signalmesh_terminal.main import create_app
    routes.reset_for_tests()
    c = TestClient(create_app())                  # no "with": the background recorder is not started
    yield c, routes
    routes.reset_for_tests()


def _ready(snap_fn):
    """The engine saying READY with a full BUY plan — the most dangerous thing to pair with bad data."""
    def fn(sym):
        o = copy.deepcopy(snap_fn(sym))
        o.setdefault("snapshot", {})["decision"] = {"status": "READY", "order_type": "BUY LIMIT", "entry": 100.0, "sl": 99.0, "tp1": 101.0, "tp2": 102.0, "reason": "simulated READY"}
        return o
    return fn


def _stale(candles_fn):
    def fn(sym, tf, n):
        o = copy.deepcopy(candles_fn(sym, tf, n))
        o["freshness"] = {**(o.get("freshness") or {}), "state": "STALE", "age_min": 900, "limit_min": 45, "note": "simulated: no new bar"}
        return o
    return fn


def test_live_and_ready_is_shown_ready_so_the_guard_is_not_always_on(env):
    c, routes = env
    p = routes.provider()
    p.snapshot = _ready(p.snapshot)
    row = next(r for r in c.get("/api/terminal/market-watch").json()["rows"] if r["symbol"] == "GOLD")
    assert row["feed_state"] == "LIVE" and row["summary"] == "READY" and row["direction"] == "BUY"


def test_feed_stale_every_instrument_silent_and_no_ready_decision(env):
    c, routes = env
    p = routes.provider()
    c.get("/api/terminal/instruments")                       # the instrument list was built while the feed was alive
    p.candles, p.snapshot = _stale(p.candles), _ready(p.snapshot)
    snap0 = p.snapshot

    def snap_stale(sym):                                     # the engine's own freshness word for its candles is STALE too
        o = snap0(sym)
        o["snapshot"]["freshness"] = {"candles": {"state": "STALE", "age_min": 900, "limit_min": 45, "note": "simulated"}}
        return o
    p.snapshot = snap_stale
    routes.cache()._store = {k: v for k, v in routes.cache()._store.items() if k == "discovery"}
    mw = c.get("/api/terminal/market-watch").json()
    assert mw["feed"] == "FEED STALE" and mw["rows"] and all(r["feed_state"] == "FEED STALE" for r in mw["rows"])
    # the engine says READY, the data is stale: nowhere is it shown as ready
    assert all(r["engine_status"] == "READY" and r["summary"] == "INVALIDATED" and r["direction"] is None for r in mw["rows"])
    d = c.get("/api/terminal/decision?symbol=GOLD").json()
    assert d["engine_status"] == "READY" and d["summary"] == "INVALIDATED"
    assert all(s["state"] == "INVALID" for s in (d["sides"].values() if isinstance(d["sides"], dict) else d["sides"]))
    assert any("TERMINAL GUARD" in x for x in d["invalidation"])
    # the studies say the data is stale, and the recorder makes nothing new from bars that are not new
    assert c.get("/api/terminal/studies?symbol=GOLD&tf=15m").json()["freshness"]["state"] == "STALE"
    first = routes.recorder().pass_once()
    again = routes.recorder().pass_once()
    assert again["recorded"] == 0 and again["refused"] == 0, (first, again)


def test_one_instrument_quiet_while_the_feed_is_alive_reads_market_quiet(env):
    c, routes = env
    p = routes.provider()
    real = p.candles
    p.candles = lambda sym, tf, n: _stale(real)(sym, tf, n) if sym == "GOLD" else real(sym, tf, n)
    p.snapshot = _ready(p.snapshot)
    rows = {r["symbol"]: r for r in c.get("/api/terminal/market-watch").json()["rows"]}
    assert rows["GOLD"]["feed_state"] == "MARKET QUIET" and "INFERRED" in rows["GOLD"]["feed_note"] and "closed" in rows["GOLD"]["feed_note"]
    assert rows["GOLD"]["summary"] == "INVALIDATED" and rows["SILVER"]["feed_state"] == "LIVE" and rows["SILVER"]["summary"] == "READY"
    assert "MARKET CLOSED" not in str(rows)                   # the terminal has no calendar: it never says closed as a fact


def test_disconnected_one_instrument_cannot_be_read(env):
    c, routes = env
    p = routes.provider()
    c.get("/api/terminal/instruments")
    real_c, real_s = p.candles, _ready(p.snapshot)

    def cand(sym, tf, n):
        if sym == "GOLD":
            raise ProviderError("connection reset", state="DOWN")
        return real_c(sym, tf, n)

    def snap(sym):
        if sym == "GOLD":
            raise ProviderError("connection reset", state="DOWN")
        return real_s(sym)
    p.candles, p.snapshot = cand, snap
    routes.cache()._store = {k: v for k, v in routes.cache()._store.items() if k == "discovery"}
    rows = {r["symbol"]: r for r in c.get("/api/terminal/market-watch").json()["rows"]}
    g = rows["GOLD"]
    assert g["feed_state"] == "DISCONNECTED" and g["price"] is None and g["summary"] != "READY" and g["direction"] is None
    assert c.get("/api/terminal/decision?symbol=GOLD").status_code == 503       # no decision at all, not an old one
    assert c.get("/api/terminal/studies?symbol=GOLD&tf=15m").status_code == 503
    assert c.get("/api/terminal/candles?symbol=GOLD&tf=15m").status_code == 503


def test_disconnected_signalmesh_cannot_be_reached_at_all(env):
    c, routes = env
    p = routes.provider()

    def down(*a, **k):
        raise ProviderError("connection refused", state="DOWN")
    for name in ("candles", "snapshot", "signals", "news_state", "trades", "portfolio"):
        if hasattr(p, name):
            setattr(p, name, down)
    mw = c.get("/api/terminal/market-watch").json()
    assert mw["rows"] == [] and mw["feed"] == "DISCONNECTED" and "could not be read" in mw["feed_note"]
    inst = c.get("/api/terminal/instruments").json()
    assert inst["complete"] is False and inst["failed_reads"]
    for path in ("/api/terminal/decision?symbol=GOLD", "/api/terminal/studies?symbol=GOLD&tf=15m", "/api/terminal/candles?symbol=GOLD&tf=15m"):
        assert c.get(path).status_code == 503, path
    done = routes.recorder().pass_once()
    assert done["recorded"] == 0                              # nothing is forecast from a feed that is not there
    assert c.get("/api/terminal/execution/modes").json()["can_place"] is False


def test_journal_audit_counts_forecasts_not_marks(env):
    c, routes = env
    routes.recorder().pass_once()
    j = c.get("/api/terminal/journal?limit=1000").json()
    a = j["audit"]
    assert a["forecasts"] == j["store"]["forecasts"] == a["distinct_forecast_ids"] and a["outcome_marks"] == j["store"]["outcomes"]
    assert a["live"] + a["backfill"] == a["forecasts"] == a["finished_with_outcome"] + a["never_entered"] + a["open"]
    assert a["orphan_outcome_marks"] == 0 and a["duplicate_outcome_marks"] == 0 and a["forecasts_with_marks"] <= a["forecasts"]
    assert sum(g["recorded"] for g in a["by_method_timeframe"]) == a["forecasts"] == sum(g["recorded"] for g in j["stats"])
    assert sum(g["finished"] for g in j["stats"]) == a["finished_with_outcome"]
    # a second pass over the same bars adds marks at most, never a forecast, and never a second copy of a mark
    routes.recorder().pass_once()
    b = c.get("/api/terminal/journal").json()["audit"]
    assert b["forecasts"] == a["forecasts"] and b["duplicate_outcome_marks"] == 0 and b["outcome_marks"] == a["outcome_marks"]


def _stale_since(candles_fn, days):
    """A series whose newest bar is `days` old and which the engine calls STALE — what a series that stopped arriving looks like."""
    from datetime import datetime, timedelta

    def fn(sym, tf, n):
        o = _stale(candles_fn)(sym, tf, n)
        for b in o.get("candles") or []:
            b["ts"] = (datetime.fromisoformat(b["ts"]) - timedelta(days=days)).isoformat()
        return o
    return fn


def test_a_series_silent_for_months_reads_no_new_bars_never_market_quiet(env):
    """Seen on production (Shyam, 2026-11-25): US10Y read STALE · MARKET QUIET every day. SignalMesh retired it on 27 August —
    nothing pushes it. A market break lasts hours or a holiday weekend; a series silent for longer has stopped arriving."""
    c, routes = env
    p = routes.provider()
    real = p.candles
    p.candles = lambda sym, tf, n: _stale_since(real, 90)(sym, tf, n) if sym == "GOLD" else real(sym, tf, n)
    p.snapshot = _ready(p.snapshot)
    mw = c.get("/api/terminal/market-watch").json()
    rows = {r["symbol"]: r for r in mw["rows"]}
    g = rows["GOLD"]
    assert g["feed_state"] == "NO NEW BARS" and "90 days" in g["feed_note"] and "not a market break" in g["feed_note"] and "not live" in g["feed_note"]
    assert "terminal's own rule" in g["feed_note"] and "MARKET QUIET" not in str(g) and "most likely the market is closed" not in g["feed_note"]
    assert g["summary"] != "READY" and g["direction"] is None                 # an old price is never a setup
    assert rows["SILVER"]["feed_state"] == "LIVE" and "NO NEW BARS" in mw["feed_rule"]


@pytest.mark.parametrize("days,word", [(2, "MARKET QUIET"), (6, "MARKET QUIET"), (8, "NO NEW BARS")])
def test_the_no_new_bars_rule_starts_after_seven_days(env, days, word):
    c, routes = env
    p = routes.provider()
    real = p.candles
    p.candles = lambda sym, tf, n: _stale_since(real, days)(sym, tf, n) if sym == "GOLD" else real(sym, tf, n)
    rows = {r["symbol"]: r for r in c.get("/api/terminal/market-watch").json()["rows"]}
    assert rows["GOLD"]["feed_state"] == word


def test_a_dead_series_on_a_closed_market_is_not_promised_a_reopening(env):
    """On a weekend SignalMesh's clock says closed for every 24/5 name — including one that will not come back on Sunday."""
    c, routes = env
    p = routes.provider()
    real = p.candles

    def closed(sym, tf, n):
        o = _stale_since(real, 90)(sym, tf, n) if sym == "GOLD" else copy.deepcopy(real(sym, tf, n))
        if sym in ("GOLD", "SILVER"):
            o["market_status"] = {"open": False, "kind": "24/5", "why": "weekend", "reopens_in": "22h 03m", "reopens_in_min": 1323, "next_open_utc": "2026-11-29T22:00:00+00:00"}
        return o
    p.candles = closed
    rows = {r["symbol"]: r for r in c.get("/api/terminal/market-watch").json()["rows"]}
    assert rows["GOLD"]["feed_state"] == "NO NEW BARS" and "reopens" not in rows["GOLD"]["feed_note"]
    assert rows["SILVER"]["feed_state"] == "MARKET CLOSED"


def test_a_retired_instrument_reads_retired_in_signalmeshs_own_words(env):
    """Platform 5.232 sends `retired` on every market answer. Its word and its date are printed as sent; the terminal infers none."""
    c, routes = env
    p = routes.provider()
    real = p.candles

    def candles(sym, tf, n):
        o = _stale_since(real, 90)(sym, tf, n) if sym == "GOLD" else copy.deepcopy(real(sym, tf, n))
        o["retired"] = {"since": "2026-08-27 20:58 UTC", "reason": "broker contract roll with NO SUCCESSOR"} if sym == "GOLD" else None
        return o
    p.candles = candles
    rows = {r["symbol"]: r for r in c.get("/api/terminal/market-watch").json()["rows"]}
    g = rows["GOLD"]
    assert g["feed_state"] == "RETIRED" and g["retired"]["since"] == "2026-08-27 20:58 UTC"
    assert "2026-08-27 20:58 UTC" in g["feed_note"] and "NO SUCCESSOR" in g["feed_note"] and "not live" in g["feed_note"]
    assert g["summary"] != "READY" and rows["SILVER"]["feed_state"] == "LIVE" and rows["SILVER"]["retired"] is None


def test_a_null_or_absent_retired_key_retires_nothing(env):
    c, routes = env
    p = routes.provider()
    real = p.candles
    p.candles = lambda sym, tf, n: {**_stale_since(real, 90)(sym, tf, n), "retired": None} if sym == "GOLD" else real(sym, tf, n)
    rows = {r["symbol"]: r for r in c.get("/api/terminal/market-watch").json()["rows"]}
    assert rows["GOLD"]["feed_state"] == "NO NEW BARS" and rows["GOLD"]["retired"] is None       # the terminal's own fallback, never RETIRED by inference
