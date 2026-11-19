"""chart-read-v1 — a read of closed bars for the operator: a table, chart labels and a condition count. Not a signal,
not recorded. What the first n bars report is never restated by later bars, on series with and without daily breaks."""
import math

import pytest

from signalmesh_terminal import chartread as cr
from signalmesh_terminal import smc
from signalmesh_terminal import studies as st
from test_studies import STEP, T0, gapped, walk

DEF = ("kind", "label", "side", "price", "time", "confirmed_at")


def _labels(bars):
    return cr.analyse("X", "15m", bars)["labels"]


@pytest.mark.parametrize("seed", [1, 7, 23, 99])
@pytest.mark.parametrize("series", [walk, gapped])
def test_labels_never_look_ahead_and_are_never_restated(seed, series):
    bars = series(seed=seed) if series is gapped else series(seed=seed, swing=25, drift=1.4)
    full = _labels(bars)
    assert any(x["kind"] == "swing" for x in full) and any(x["kind"] == "pattern" for x in full)
    for n in range(80, len(bars), 53):
        part = _labels(bars[:n])
        known_by = bars[n - 1]["t"] + STEP
        want = [x for x in full if x["confirmed_at"] <= known_by]
        assert [tuple(x[k] for k in DEF) for x in part] == [tuple(x[k] for k in DEF) for x in want], f"n={n}"
        assert all(x["confirmed_at"] <= known_by for x in part)


def test_swing_labels_compare_a_pivot_with_the_previous_one_of_its_kind():
    from test_studies import zigzag
    b = zigzag([105, 100, 110, 104, 112, 106, 109, 101, 105], per=14)
    labs = [(x["label"], round(x["price"])) for x in cr.swing_labels(b, STEP)]
    assert labs == [("L", 100), ("H", 110), ("HL", 104), ("HH", 112), ("HL", 106), ("LH", 109), ("LL", 101)]
    assert all(x["confirmed_at"] >= x["time"] + (cr.SWING_L + 1) * STEP for x in cr.swing_labels(b, STEP))


def _flat(n, px=100.0):
    return [{"t": T0 + i * STEP, "o": px, "h": px + 0.5, "l": px - 0.5, "c": px, "v": 100.0} for i in range(n)]


def test_a_bearish_rejection_is_a_long_upper_wick_at_the_high_closing_low():
    b = _flat(40)
    b.append({"t": T0 + 40 * STEP, "o": 100.2, "h": 103.0, "l": 100.0, "c": 100.1, "v": 300.0})      # wick 2.8, body 0.1, closes at the bottom
    got = cr.candle_patterns(b, st.atr_rma(b), STEP)
    assert [x["label"] for x in got] == ["BEAR REJECTION"] and got[0]["price"] == 103.0 and got[0]["confirmed_at"] == b[-1]["t"] + STEP
    # the same shape that is NOT at the high of the last bars is not a rejection
    b2 = _flat(40)
    b2[35] = {**b2[35], "h": 104.0}
    b2.append(b[-1])
    assert [x for x in cr.candle_patterns(b2, st.atr_rma(b2), STEP) if x["time"] == b2[-1]["t"]] == []      # (bar 35 is itself one; the last bar is not)
    # mirrored: bullish
    b3 = _flat(40)
    b3.append({"t": T0 + 40 * STEP, "o": 99.8, "h": 100.0, "l": 97.0, "c": 99.9, "v": 300.0})
    assert [x["label"] for x in cr.candle_patterns(b3, st.atr_rma(b3), STEP)] == ["BULL REJECTION"]


def test_engulfing_needs_the_body_to_cover_the_previous_opposite_body():
    b = _flat(40)
    b.append({"t": T0 + 40 * STEP, "o": 100.0, "h": 101.1, "l": 99.9, "c": 101.0, "v": 100.0})
    b.append({"t": T0 + 41 * STEP, "o": 101.2, "h": 101.3, "l": 99.4, "c": 99.5, "v": 100.0})
    labs = [x["label"] for x in cr.candle_patterns(b, st.atr_rma(b), STEP)]
    assert "BEAR ENGULF" in labs


def test_rsi_macd_and_ema_are_the_textbook_ones():
    up = [100 + i for i in range(60)]
    assert cr.rsi(up)[-1] == 100.0 and cr.rsi(list(reversed(up)))[-1] == 0.0
    flat = [100.0] * 60
    assert cr.ema(flat, 20)[-1] == 100.0 and cr.ema(flat, 20)[18] is None
    line, sig = cr.macd(up)
    assert line[-1] > 0 and sig[-1] is not None and math.isclose(line[-1], sig[-1], rel_tol=0.05)      # a steady trend: MACD settles on its signal


def test_conditions_are_counted_per_side_with_reasons_and_weights():
    bars = walk(seed=7, swing=25, drift=1.4)
    r = cr.analyse("X", "15m", bars, {"15m": smc.analyse("X", "15m", bars)})
    for side in ("SELL", "BUY"):
        c = r["conditions"][side]
        assert [x["name"] for x in c["conditions"]] == ["rejection", "engulfing", "swing", "bos", "choch", "ema"] and c["of"] == 6
        assert all(x["status"] in ("CONFIRMED", "WAITING", "FAILED", "NOT APPLICABLE") and x["reason"] for x in c["conditions"])
        assert c["weight"] == sum(x["weight"] for x in c["conditions"] if x["status"] == "CONFIRMED") and c["weight_of"] == 14
        assert c["confirmed"] == sum(1 for x in c["conditions"] if x["status"] == "CONFIRMED")
    # structure outweighs a moving-average relation
    assert cr.WEIGHTS["bos"] > cr.WEIGHTS["ema"] and cr.WEIGHTS["choch"] > cr.WEIGHTS["ema"] and cr.WEIGHTS["rejection"] > cr.WEIGHTS["ema"]
    # the EMA condition cannot be confirmed on both sides at once, and a newest BOS cannot be
    ema_s = next(x for x in r["conditions"]["SELL"]["conditions"] if x["name"] == "ema")["status"]
    ema_b = next(x for x in r["conditions"]["BUY"]["conditions"] if x["name"] == "ema")["status"]
    assert {ema_s, ema_b} == {"CONFIRMED", "FAILED"}


def test_rows_say_not_available_instead_of_guessing():
    bars = walk(seed=7)
    r = cr.analyse("X", "15m", bars)                    # no other timeframe, no daily forecast, no engine, no Pine signal
    rows = {x["key"]: x for x in r["rows"]}
    assert rows["weekly"]["value"] == "NOT AVAILABLE" and rows["day_forecast"]["value"] == "NOT AVAILABLE" and rows["engine"]["value"] == "NOT AVAILABLE"
    assert rows["tester"]["value"] == "NOT AVAILABLE" and "TradingView" in rows["tester"]["note"] and rows["pine"]["value"] == "NONE"
    assert all(x["source"] and x["label"] for x in r["rows"]) and r["recorded"] is False and "not a signal" in r["kind"]
    assert cr.analyse("X", "15m", bars[:30])["state"] == "NOT_AVAILABLE"
    # no volume stored: said
    nov = cr.analyse("X", "15m", [{**k, "v": 0.0} for k in bars])
    assert next(x for x in nov["rows"] if x["key"] == "volume")["value"] == "NOT AVAILABLE"


def test_route_is_a_read_only_study_and_writes_nothing(client):
    d = client.get("/api/terminal/chart-read?symbol=GOLD&tf=15m").json()
    assert d["state"] == "OK" and d["method_version"] == cr.VERSION and d["recorded"] is False and "freshness" in d and "decimals" in d
    keys = [x["key"] for x in d["rows"]]
    for k in ("weekly", "daily", "h4", "h1", "swing", "last_confirm", "resistance", "support", "momentum", "volatility", "price_zone", "volume", "engine",
              "cond_sell", "cond_buy", "fvg", "order_block", "liquidity", "inducement", "day_forecast", "adr", "pine", "tester"):
        assert k in keys, k
    assert client.get("/api/terminal/chart-read?symbol=GOLD&tf=1w").status_code == 400
    assert client.post("/api/terminal/chart-read?symbol=GOLD").status_code == 405
    from signalmesh_terminal import routes
    assert '@router.post("/chart-read' not in open(routes.__file__).read()
    assert client.get("/api/terminal/execution/modes").json()["can_place"] is False
