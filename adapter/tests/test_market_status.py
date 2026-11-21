"""market-status-v1 (platform 5.214) — SignalMesh's own market clock. On Saturday 2026-11-21 the terminal showed US100, US30,
VIX and DXY as LIVE: the engine's freshness word for their newest bar was LIVE and no read route said the market was closed.
Now every /api/v1/market/* answer carries `market_status`, and the terminal never prints LIVE when it says open=false.
Also here: the lane history counted by PLANS (lane-history-v3), carried untouched beside the bar count."""
import copy

from signalmesh_terminal import normalize, routes
from signalmesh_terminal.providers.fixture import FixtureProvider

CLOSED = {"open": False, "kind": "24/5", "why": "weekend — closed Fri 22:00 UTC to Sun 22:00 UTC (approximate; exact minutes are broker-dependent)",
          "next_open_utc": "2026-11-22T22:00:00+00:00", "reopens_in_min": 1860, "reopens_in": "31h 00m"}
OPEN = {"open": True, "kind": "24/5", "why": "inside the trading week (closes Fri 22:00 UTC)"}
CRYPTO = {"open": True, "kind": "24/7", "why": "crypto — trades through the weekend"}


def _candles(sym="US100", tf="1m", ms=None, state="LIVE"):
    c = FixtureProvider().candles("GOLD", tf, 3)
    c["symbol"] = sym
    c["freshness"] = {**c["freshness"], "state": state}
    if ms is not None:
        c["market_status"] = ms
    return c


def test_live_on_a_closed_market_is_never_printed_as_live():
    f = normalize._fresh({"state": "LIVE", "age_min": 3, "limit_min": 45, "note": "bar-clock"}, CLOSED)
    assert f.state == "CLOSED" and f.detail.startswith("MARKET CLOSED — weekend") and "reopens in 31h 00m" in f.detail and "was LIVE" in f.detail
    assert (f.age_min, f.limit_min) == (3, 45)                      # the engine's numbers stay
    assert normalize.shown_state(_candles(ms=CLOSED)) == "CLOSED"
    assert normalize.bar_ref("US100", "1m", _candles(ms=CLOSED)).freshness.state == "CLOSED"
    s = normalize.candle_series("fixture", "US100", "15m", _candles(tf="15m", ms=CLOSED))
    assert s.freshness.state == "CLOSED" and s.market_status == CLOSED


def test_the_clock_only_downgrades_and_an_open_market_makes_nothing_live():
    assert normalize._fresh({"state": "STALE"}, CLOSED).state == "STALE"        # the engine's own word stays
    assert normalize._fresh({"state": "UNKNOWN"}, CLOSED).state == "UNKNOWN"
    assert normalize._fresh({"state": "STALE"}, OPEN).state == "STALE"          # open does not make an old bar live
    assert normalize._fresh({"state": "LIVE"}, OPEN).state == "LIVE" and normalize._fresh({"state": "LIVE"}, CRYPTO).state == "LIVE"


def test_without_the_clock_nothing_changes_and_nothing_is_guessed():
    """A platform before 5.214, or a malformed clock: the terminal closes nothing by itself."""
    assert normalize.market_status_of(_candles()) is None and normalize.shown_state(_candles()) == "LIVE"
    for bad in (None, {}, {"open": None}, {"open": "false"}, {"open": 0}, "closed"):
        assert normalize.market_closed(bad) is False
        assert normalize._fresh({"state": "LIVE"}, bad if isinstance(bad, dict) else None).state == "LIVE"
    assert normalize.market_status_of({"market_status": {"open": False, "why": "w", "extra": 1}}) == {"open": False, "why": "w"}


def test_market_watch_row_says_market_closed_in_the_platforms_words(client, monkeypatch):
    p = routes.provider()
    real_c, real_s = p.candles, p.snapshot
    monkeypatch.setattr(p, "candles", lambda sym, tf, n: {**real_c(sym, tf, n), "market_status": CLOSED if sym == "GOLD" else CRYPTO})
    monkeypatch.setattr(p, "snapshot", lambda sym: {**real_s(sym), "market_status": CLOSED if sym == "GOLD" else CRYPTO})
    routes.cache().clear()
    rows = {r["symbol"]: r for r in client.get("/api/terminal/market-watch").json()["rows"]}
    g = rows["GOLD"]
    assert g["freshness"]["state"] == "CLOSED" and g["feed_state"] == "MARKET CLOSED" and g["market_status"] == CLOSED
    assert "weekend" in g["feed_note"] and "reopens in 31h 00m" in g["feed_note"] and "not live" in g["feed_note"]
    assert g["summary"] != "READY"                                              # a plan on a closed market cannot fill
    assert rows["BTC"]["freshness"]["state"] == "LIVE" and rows["BTC"]["feed_state"] == "LIVE"
    # the chart's own series, the coverage table and the decision's bar freshness say the same
    assert client.get("/api/terminal/candles?symbol=GOLD&tf=15m&n=50").json()["freshness"]["state"] == "CLOSED"
    assert all(r["state"] != "LIVE" for r in client.get("/api/terminal/coverage?symbol=GOLD").json()["timeframes"])
    d = client.get("/api/terminal/decision?symbol=GOLD").json()
    assert d["freshness"]["candles"]["state"] == "CLOSED" and d["summary"] != "READY"
    assert all(f["state"] != "CLOSED" for k, f in d["freshness"].items() if k != "candles")   # the clock touches the BAR freshness only
    routes.cache().clear()


def test_no_forming_bar_is_built_on_a_closed_market(client, monkeypatch):
    p = routes.provider()
    real_c = p.candles
    monkeypatch.setattr(p, "candles", lambda sym, tf, n: {**real_c(sym, tf, n), "market_status": CLOSED})
    routes.cache().clear()
    lv = client.get("/api/terminal/live?symbol=GOLD&tf=15m").json()
    assert lv["state"] == "MARKET_CLOSED" and lv["bars"] == [] and "weekend" in lv["error"]
    routes.cache().clear()


# ---------------------------------------------------------------- lane history counted by plans (platform 5.214)
def _desk_with_plans():
    d = copy.deepcopy(FixtureProvider().desk("GOLD"))
    v = {"rule": "evidence-verdict-v2", "verdict": "UNKNOWN", "icon": "?", "tone": "unknown", "ok": None, "n": 31, "floor": 20, "held_by": "days floor",
         "why": "31 plans, but born on only 9 day(s) — under the floor of 20 days: results from one stretch of market are not independent observations",
         "lo_r": -0.2, "hi_r": 0.4}
    cell = {"rule": "lane-history-v3", "cells_rule": "lane-cells-v2", "unit": "plans", "key": "HH/HL-BUY", "engine": "session-v1", "symbol": "GOLD", "days_floor": 20,
            "state": "FRESH", "cells_age_s": 120, "level": "session-v1 × GOLD × HH/HL-BUY", "backed_off": False, "symbol_n": 31, "n": 31, "bars_n": 412, "days": 9,
            "expectancy_r": 0.101, "sd": 1.01, "wins": 15, "losses": 16, "lo_r": -0.2, "hi_r": 0.4, "verdict": v, "population": "one result per plan", "authority": "PAPER"}
    line = "by plans (lane-cells-v2): UNKNOWN ? — 31 plan(s) on 9 day(s), standing for 412 bar(s), mean +0.101R (31 plans, but born on only 9 day(s))"
    for lane in d["desk"]["lanes"]:
        if lane.get("own_history"):
            lane["own_history_plans"], lane["own_history_plans_line"] = cell, line
            m = next(k for k in lane["validity"]["checks"] if k.get("label") == "Measured history")
            m["verdict_plans"], m["plans_line"] = v, line
    for r in d["verdict_board"]["rows"]:
        r["plans"], r["plans_line"], r["plans_class"] = cell, line, "text-slate-400"
    d["verdict_board"]["plans"] = {"rule": "lane-history-v3", "cells_rule": "lane-cells-v2", "days_floor": 20, "positive": 0, "negative": 0, "cannot_separate": 0,
                                   "unknown": 8, "note": "n, the interval and the V1 / V2 columns count every resolved BAR … Read that column."}
    return d, cell, line, v


def test_the_plan_count_is_carried_untouched_beside_the_bar_count():
    d, cell, line, v = _desk_with_plans()
    card = next(c for c in normalize.lane_cards(d) if c.own_history)
    assert card.own_history_plans == cell and card.own_history_plans_line == line and card.verdict_plans == v and card.plans_line == line
    assert card.own_history_plans["verdict"]["held_by"] == "days floor" and card.own_history_plans["verdict"]["verdict"] == "UNKNOWN"
    assert card.own_history["n"] == 47 and card.verdict_v2 is not None          # the bar count is unchanged beside it
    vb = normalize.verdict_board(d, "GOLD")
    assert all(r.plans == cell and r.plans_line == line for r in vb.rows) and vb.plans == d["verdict_board"]["plans"]
    assert "plans_class" not in vb.model_dump_json()                            # the platform page's CSS name is not data


def test_a_platform_before_5214_sends_no_plan_count_and_none_is_invented():
    d = FixtureProvider().desk("GOLD")
    card = next(c for c in normalize.lane_cards(d) if c.own_history)
    assert (card.own_history_plans, card.own_history_plans_line, card.verdict_plans, card.plans_line) == (None, "", None, "")
    vb = normalize.verdict_board(d, "GOLD")
    assert vb.plans is None and all(r.plans is None and r.plans_line == "" for r in vb.rows)
