"""daily-forecast-v1 / rotation-v1 — display-only studies ported from Shyam's Pine scripts: closed
bars only, no lookahead, no repaint, and never more than the data supports."""
import random

import pytest

from signalmesh_terminal import audit
from signalmesh_terminal import forecast as fc
from signalmesh_terminal import journal as fj

STEP, DAY = 900, 86400
D0 = 1_790_000_000 // DAY * DAY + 22 * 3600          # a broker day opening 22:00 UTC


def market(days=30, seed=3, vol=0.35):
    """A seeded 15m random walk and the daily bars it aggregates to (22:00 UTC day)."""
    r = random.Random(seed)
    m15, px = [], 2000.0
    for i in range(days * 96):
        o = px
        c = o + r.gauss(0, vol) + 0.25 * vol * (1 if (i // 300) % 2 == 0 else -1)
        m15.append({"t": D0 + i * STEP, "o": o, "h": max(o, c) + abs(r.gauss(0, vol / 2)), "l": min(o, c) - abs(r.gauss(0, vol / 2)), "c": c})
        px = c
    daily = []
    for d in range(days):
        b = m15[d * 96:(d + 1) * 96]
        daily.append({"t": D0 + d * DAY, "o": b[0]["o"], "h": max(x["h"] for x in b), "l": min(x["l"] for x in b), "c": b[-1]["c"]})
    return daily, m15


def flat_daily(n=15, rng=10.0, close=100.0):
    return [{"t": D0 + i * DAY, "o": close, "h": close + rng / 2, "l": close - rng / 2, "c": close} for i in range(n)]


def bar(i, o, h, l, c, day=15):
    return {"t": D0 + day * DAY + i * STEP, "o": o, "h": h, "l": l, "c": c}


# ------------------------------------------------------------------ the Pine formulas
def test_top_and_bottom_are_low_plus_adr_and_high_minus_adr():
    ev = fc.evaluate(flat_daily(), [bar(0, 100, 101, 99, 100.5), bar(1, 100.5, 102, 100, 101)])
    assert ev["adr"] == 10.0 and ev["top_raw"] == 109.0 and ev["bottom_raw"] == 92.0
    assert (ev["top"], ev["bottom"], ev["top_done"], ev["bottom_done"]) == (109.0, 92.0, False, False)
    assert round(ev["used_pct"]) == 30 and round(ev["move_pct"]) == 10 and ev["status"].startswith("ADR 30% used")


def test_adr_uses_completed_days_only_and_only_the_last_fourteen():
    daily = [{"t": D0 - DAY, "o": 1, "h": 1000, "l": 0, "c": 1}] + flat_daily()        # a wild 16th-oldest day must not count
    assert fc.evaluate(daily, [bar(0, 100, 101, 99, 100)])["adr"] == pytest.approx((14 * 10.0) / 14)


def test_a_completed_side_becomes_the_days_extreme_and_says_so():
    ev = fc.evaluate(flat_daily(), [bar(0, 100, 100.5, 99, 100), bar(1, 100, 110.5, 100, 110)])     # high 110.5 >= low 99 + 10
    # Pine's two "done" tests are one condition, so both are true together and the status is Pine's "BOTH SIDES DONE";
    # the terminal adds which extreme completed the range
    assert ev["top_done"] and ev["bottom_done"] and ev["top"] == 110.5 and ev["status"].startswith("BOTH SIDES DONE")
    assert ev["completed_by"] == {"side": "TOP", "bar": D0 + 15 * DAY + STEP}
    low = fc.evaluate(flat_daily(), [bar(0, 100, 100.5, 99, 100), bar(1, 100, 100, 89, 90)])
    assert low["completed_by"]["side"] == "BOTTOM" and low["bottom"] == 89
    near = fc.evaluate(flat_daily(), [bar(0, 100, 104.5, 96, 100)])
    assert near["status"].startswith("NEAR FULL ADR 85%")


def test_snap_moves_a_raw_level_onto_a_nearby_level_and_only_then():
    day = [bar(0, 100, 101, 99, 100)]                                    # top_raw 109, bottom_raw 91
    assert fc.evaluate(flat_daily(), day, {"res": 109.4, "sup": None, "atr": 1.0})["top"] == 109.4            # within 0.5 x ATR
    assert fc.evaluate(flat_daily(), day, {"res": 109.4, "sup": None, "atr": 1.0})["top_snapped_to"] == "4h swing high"
    assert fc.evaluate(flat_daily(), day, {"res": 109.6, "sup": None, "atr": 1.0})["top"] == 109.0            # too far
    assert fc.evaluate(flat_daily(), day, {})["top"] == 109.0                                                   # no 4h bars = no snap
    prev_high = flat_daily()[-1]["h"]                                    # 105: not near 109
    assert fc.evaluate(flat_daily(), day, {"res": None, "sup": None, "atr": 10.0})["top"] == prev_high          # previous day's high within tolerance


# ------------------------------------------------------------------ which bars are "today"
def test_today_is_the_broker_day_and_missing_data_is_said_not_guessed():
    daily = flat_daily()                                                 # last closed day opens D0 + 14 days
    ok = fc.split_day(daily, [bar(0, 1, 1, 1, 1), bar(1, 1, 1, 1, 1)], STEP)
    assert ok["state"] == "OK" and ok["start"] == D0 + 15 * DAY and len(ok["bars"]) == 2
    weekend = fc.split_day(daily, [bar(0, 1, 1, 1, 1, day=17)], STEP)    # Friday's bar, then Sunday-evening open
    assert weekend["state"] == "OK" and weekend["start"] == D0 + 17 * DAY
    assert fc.split_day(daily[:10], [bar(0, 1, 1, 1, 1)], STEP)["state"] == "NOT_AVAILABLE"
    assert fc.split_day(daily, [bar(-5, 1, 1, 1, 1, day=15)], STEP)["state"] == "NOT_AVAILABLE"                 # no bar of the new day yet
    behind = [bar(i, 1, 1, 1, 1, day=15) for i in range(96)] + [bar(i, 1, 1, 1, 1, day=16) for i in range(96)] + [bar(0, 1, 1, 1, 1, day=17)]
    assert "behind" in fc.split_day(daily, behind, STEP)["note"]


def test_payload_labels_and_unknowns():
    daily, m15 = market(days=30)
    d = fc.daily_forecast("GOLD", daily[:-1], m15, "15m")
    assert d["state"] == "OK" and d["confidence"] == "UNKNOWN" and d["levels_are"] == "CALCULATED" and d["horizons_are"] == "ESTIMATES"
    assert d["through_close"] == m15[-1]["t"] + STEP and d["day_start"] == daily[-1]["t"]
    assert d["outlooks"]["6-month"]["state"] == "UNKNOWN" and d["outlooks"]["monthly"]["state"] == "UNKNOWN"   # 30 days of history
    assert all(s["level_label"] == "HYPOTHETICAL ANALYSIS LEVEL" and s["confidence"] == "UNKNOWN" for s in d["scenarios"])
    assert len(d["history"]) == 5 and all(h["top"] >= h["high"] and h["bottom"] <= h["low"] for h in d["history"])
    none = fc.daily_forecast("GOLD", daily[:5], m15, "15m")
    assert none["state"] == "NOT_AVAILABLE" and "top" not in none and none["scenarios"] == []


def test_longer_outlooks_need_fourteen_completed_periods():
    daily = [{"t": D0 + i * DAY, "o": 100, "h": 101 + (i % 5), "l": 99 - (i % 3), "c": 100} for i in range(-900, 0)]
    out = fc.outlooks(daily, {"high": 101, "low": 99, "last": 100, "start": D0})
    assert out["weekly"]["state"] == "OK" and out["monthly"]["state"] == "OK"
    assert out["6-month"]["state"] == "UNKNOWN" and "14 are needed" in out["6-month"]["note"]
    w = out["weekly"]
    assert w["top"] >= w["high"] and w["bottom"] <= w["low"] and w["confidence"] == "UNKNOWN"


# ------------------------------------------------------------------ the journal scenario
def test_fade_scenario_is_made_once_at_the_first_closed_bar_that_completes_a_side():
    day = [bar(0, 100, 100.5, 99, 100), bar(1, 100, 109.5, 100, 109), bar(2, 109, 112, 108, 111), bar(3, 111, 113, 110, 112)]
    fs = fc.fade_scenarios("GOLD", flat_daily(), day, D0 + 15 * DAY, STEP)
    assert len(fs) == 1 and fs[0]["made_bar"] == day[1]["t"] and fs[0]["direction"] == "SHORT"
    f = fs[0]
    assert f["sl"] == pytest.approx(109.5 + 2.5) and f["tp1"] == pytest.approx(109 - 2.5) and f["tp2"] == pytest.approx(109 - 5) and f["invalidation"] == f["sl"]
    assert f["horizon_bars"] == 96 - 2                                   # every bar left in the broker day
    row = fj.validate({**f, "symbol": "GOLD", "timeframe": "15m", "module": "daily-forecast", "method_version": fc.DAILY_VERSION})
    assert row["direction"] == "SHORT"
    assert fc.fade_scenarios("GOLD", flat_daily(), day[:1], D0 + 15 * DAY, STEP) == []                          # nothing before the side is completed
    late = [bar(93, 100, 100.5, 99, 100), bar(94, 100, 110, 100, 109)]
    assert fc.fade_scenarios("GOLD", flat_daily(), late, D0 + 15 * DAY, STEP) == [], "too close to the day's end: not recorded"


@pytest.mark.parametrize("seed", [1, 7, 23, 99])
def test_daily_forecast_module_never_looks_ahead_and_never_repaints(seed):
    daily, m15 = market(days=30, seed=seed, vol=0.5)
    a = audit.daily_forecast_audit("GOLD", daily, m15[-96 * 9:], stride=5)
    assert a["forecasts"] >= 3 and a["disagreements"] == 0 and a["refused"] == 0 and a["checks"] > 100, a


def test_the_module_uses_only_daily_bars_from_before_each_day():
    daily, m15 = market(days=30, seed=4, vol=0.5)
    m = fc.DailyForecastModule()
    base = m.forecasts("GOLD", "15m", m15[-96 * 6:], lambda s, t: daily)
    wild = [dict(d) for d in daily]
    wild[-1]["h"] += 500                                                 # change the LAST day's own bar: no forecast of that day may move
    again = m.forecasts("GOLD", "15m", m15[-96 * 6:], lambda s, t: wild)
    last_day = daily[-1]["t"]
    assert [f for f in base if f["detail"]["day_start"] <= last_day] == [f for f in again if f["detail"]["day_start"] <= last_day]


# ------------------------------------------------------------------ the rotation ladder
def test_ladder_states_actions_and_score_are_pines():
    assert fc.rot_state(20, 5) == ("FRESH (quiet)", "wait break / session open")
    assert fc.rot_state(40, 5) == ("MOVING UP", "buy pullbacks") and fc.rot_state(40, -5) == ("MOVING DOWN", "sell rallies")
    assert fc.rot_state(90, 5)[0] == "NEAR FULL" and fc.rot_state(100, 5) == ("DONE - sleep", "no chase: fade / trap only")
    assert fc.rot_score(40, 30, True) == pytest.approx(60 * 0.5 + 30) and fc.rot_score(40, 90, True) == pytest.approx(30 + 60)
    assert fc.rot_score(40, 30, False) == pytest.approx(30.0) and fc.rot_score(100, 80, True) == 0.0


def test_sessions_follow_new_york_time():
    from datetime import datetime, timezone
    t = int(datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc).timestamp())      # 09:00 New York (winter)
    s = fc.sessions_at(t)
    assert s == {"asia": False, "london": False, "ny": True}
    assert fc.session_ok("US100", s) and fc.session_ok("GOLD", s) and fc.session_ok("BTCUSD", s)
    night = fc.sessions_at(int(datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc).timestamp()))   # 21:00 New York
    assert night["asia"] and not fc.session_ok("GOLD", night) and fc.session_ok("USDJPY", night) and not fc.session_ok("US100", night)


def test_ranking_orders_by_score_names_the_asset_with_most_room_and_never_guesses():
    f = lambda used, move: {"state": "OK", "used_pct": used, "move_pct": move, "adr": 1.0}      # noqa: E731
    from datetime import datetime, timezone
    now = int(datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc).timestamp())
    r = fc.ranking([{"symbol": "GOLD", "forecast": f(105, 80)}, {"symbol": "SILVER", "forecast": f(40, 30)}, {"symbol": "EURUSD", "forecast": f(20, 5)},
                    {"symbol": "OIL", "forecast": {"state": "NOT_AVAILABLE", "note": "no daily bars"}}], now, "GOLD")
    assert [x["symbol"] for x in r["rows"]] == ["SILVER", "EURUSD", "GOLD", "OIL"] and [x["rank"] for x in r["rows"]] == [1, 2, 3, None]
    assert r["rows"][-1]["state"] == "NOT AVAILABLE" and r["rows"][-1]["used_pct"] is None
    assert r["go_trade"].startswith("GOLD move DONE (105% ADR): let it sleep -> GO TRADE SILVER") and r["go_symbol"] == "SILVER"
    stay = fc.ranking([{"symbol": "GOLD", "forecast": f(30, 20)}, {"symbol": "SILVER", "forecast": f(90, 5)}], now, "GOLD")
    assert stay["go_trade"].startswith("STAY on GOLD")
    none = fc.ranking([{"symbol": "GOLD", "forecast": f(120, 20)}], now, "GOLD")
    assert none["go_trade"].startswith("No asset shows clear room") and none["go_symbol"] is None
    assert "not recorded in the forecast journal" in r["note"]


# ------------------------------------------------------------------ the routes
def test_forecast_routes_answer_and_are_labelled(client):
    d = client.get("/api/terminal/forecast/daily?symbol=GOLD").json()
    assert d["state"] == "OK" and d["kind"].startswith("TERMINAL STUDY") and d["method_version"] == "daily-forecast-v1" and d["confidence"] == "UNKNOWN"
    assert d["top"] >= d["day_high"] and d["bottom"] <= d["day_low"] and d["through_close_utc"] and len(d["methodology"]) >= 10
    r = client.get("/api/terminal/forecast/ranking?symbol=GOLD").json()
    assert {x["symbol"] for x in r["rows"]} == {"GOLD", "SILVER", "BTC"} and r["go_trade"] and r["method_version"] == "rotation-v1"
    assert client.get("/api/terminal/forecast/daily?symbol=NOPE").json()["state"] == "NOT_AVAILABLE"
    assert client.post("/api/terminal/forecast/daily", json={}).status_code == 405
