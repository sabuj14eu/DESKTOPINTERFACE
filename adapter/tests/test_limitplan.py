"""limit-checklist-v1 — Shyam's seven-step checklist for a pending limit order, read on closed daily and 4h bars.
A terminal study: display only, not a signal, not recorded. These tests pin the steps' own arithmetic and the refusals."""
import math
from pathlib import Path

import pytest

from signalmesh_terminal import limitplan as lp

SRC = Path(__file__).resolve().parent.parent / "signalmesh_terminal"
D0, H0 = 1_700_000_000 // 86400 * 86400, 1_700_000_000 // 14400 * 14400


def daily(n=320, start=1000.0, drift=-1.5, amp=30.0):
    out, prev = [], start
    for i in range(n):
        c = start + drift * i + amp * math.sin(i / 6.0)
        out.append({"t": D0 + i * 86400, "o": prev, "h": max(prev, c) + 2, "l": min(prev, c) - 2, "c": c})
        prev = c
    return out


def h4_down(end_price, n=120, fall=0.10, bounce=0.045):
    """A fall, then a relief rally of `bounce` into the newest bar: the shape step 2 waits for on a sell."""
    lo = end_price / (1 + bounce)
    top = lo * (1 + fall)
    out, prev = [], top
    for i in range(n):
        c = (top + (lo - top) * (i / (n - 26)) + 3 * math.sin(i / 2.0)) if i < n - 25 else (lo + (end_price - lo) * ((i - (n - 25)) / 24) + 1.5 * math.sin(i / 1.5))
        out.append({"t": H0 + i * 14400, "o": prev, "h": max(prev, c) + 1, "l": min(prev, c) - 1, "c": c})
        prev = c
    return out


def mirror(bars, axis):
    return [dict(k, o=2 * axis - k["o"], h=2 * axis - k["l"], l=2 * axis - k["h"], c=2 * axis - k["c"]) for k in bars]


def sell_case(cut):
    d = daily()[:cut]
    return lp.analyse("TEST", d, h4_down(d[-1]["c"]), "seed")


def buy_case(cut):
    d = daily(drift=1.5)[:cut]
    return lp.analyse("TEST", d, mirror(h4_down(d[-1]["c"]), d[-1]["c"]), "seed")


def status(r):
    return {s["n"]: s["status"] for s in r["steps"]}


def test_a_downtrend_reads_sell_and_every_level_obeys_the_checklist():
    r = sell_case(310)
    assert r["state"] == "OK" and r["side"] == "SELL" and r["verdict"] == "CHECKLIST HOLDS" and r["recorded"] is False
    assert [s["n"] for s in r["steps"]] == [1, 2, 3, 4, 5, 6, 7] and status(r)[6] == status(r)[7] == "BY HAND"
    p = r["plan"]
    assert p["order_type"] == "SELL LIMIT" and p["level_label"] == "HYPOTHETICAL ANALYSIS LEVEL"
    assert p["price"] < p["zone_low"] <= p["entry"] <= p["zone_high"] < p["sl"]                 # the limit is INSIDE the zone, the stop beyond it
    assert p["entry"] == pytest.approx((p["zone_low"] + p["zone_high"]) / 2)
    assert len({l["zone_kind"] for l in p["zone_levels"]}) >= 2                                   # two or more DIFFERENT kinds overlap
    assert p["zone_high"] - p["zone_low"] <= lp.ZONE_ATR * p["atr_4h"] + 1e-9
    assert p["risk_per_unit"] == pytest.approx(p["sl"] - p["entry"]) and p["entry"] - p["price"] >= p["risk_per_unit"]      # at least 1R from price
    assert p["tp2"] < p["tp1"] < p["price"] and p["tp1"] > p["tp1_level"]["value"] and p["tp2"] > p["tp2_level"]["value"]   # just ABOVE each support
    assert p["rr2"] == pytest.approx((p["entry"] - p["tp2"]) / p["risk_per_unit"], abs=0.01) and p["rr2"] >= lp.RR2_MIN


def test_an_uptrend_is_the_mirror_buy():
    r = buy_case(320)
    assert r["side"] == "BUY" and r["verdict"] == "CHECKLIST HOLDS"
    p = r["plan"]
    assert p["order_type"] == "BUY LIMIT" and p["sl"] < p["zone_low"] <= p["entry"] <= p["zone_high"] < p["price"] < p["tp1"] < p["tp2"]
    assert p["tp1"] < p["tp1_level"]["value"] and p["risk_per_unit"] == pytest.approx(p["entry"] - p["sl"]) and p["rr2"] >= lp.RR2_MIN


def test_a_mixed_trend_is_no_trade_and_no_level_is_made():
    d = daily(drift=0.0)
    r = lp.analyse("TEST", d, h4_down(d[-1]["c"]), "seed")
    assert r["state"] == "OK" and r["side"] is None and r["verdict"] == "NO TRADE" and r["plan"] is None
    assert status(r)[1] == "MIXED" and all(status(r)[n] == "NOT APPLICABLE" for n in range(2, 8))


def test_a_limit_closer_than_1r_and_a_thin_reward_are_said_not_hidden():
    near = sell_case(320)                     # the zone is only about half an R above price
    assert near["verdict"] == "WAIT" and status(near)[3] == "WAIT" and "closer than 1R" in near["steps"][2]["text"] and near["plan"]["entry_distance_r"] < 1
    thin = sell_case(300)                     # TP2 gives less than 1:2
    assert status(thin)[5] == "FAIL" and "skip the trade" in thin["steps"][4]["text"] and thin["plan"]["rr2"] < lp.RR2_MIN and thin["verdict"] == "WAIT"
    assert "CHECKLIST HOLDS" not in (near["verdict"], thin["verdict"])


def test_the_bounce_range_is_the_checklists_own():
    d = daily()[:310]
    small = lp.analyse("TEST", d, h4_down(d[-1]["c"], bounce=0.01), "seed")
    big = lp.analyse("TEST", d, h4_down(d[-1]["c"], bounce=0.12, fall=0.2), "seed")
    assert status(small)[2] == "WAIT" and "TOO SMALL" in small["steps"][1]["text"] and small["verdict"] == "WAIT"
    assert status(big)[2] == "WAIT" and "LARGER THAN USUAL" in big["steps"][1]["text"]
    assert (lp.BOUNCE_MIN, lp.BOUNCE_MAX) == (3.0, 8.0)


def test_no_level_sits_just_past_the_stop():
    """Step 4, the lesson of 62,000 under the average at 62,102: whenever the step reads PASS, nothing the study knows of
    lies within 0.5% beyond the stop — the 200-day average included."""
    seen = 0
    for cut in range(260, 321, 4):
        for r in (sell_case(cut), buy_case(cut)):
            if not r["plan"] or r["plan"].get("sl") is None or status(r)[4] != "PASS":
                continue
            seen += 1
            s, sl = (1 if r["side"] == "SELL" else -1), r["plan"]["sl"]
            assert s * (sl - r["plan"]["entry"]) > 0
            for v in (r["averages"]["ema50"], r["averages"]["ema100"], r["averages"]["ema200"]):
                assert not (0 < s * (v - sl) <= sl * lp.SL_CLEAR), (cut, r["side"], v, sl)
    assert seen >= 10


def test_thin_data_and_a_doubled_series_are_refused():
    d = daily()
    h = h4_down(d[-1]["c"])
    thin = lp.analyse("ANT", d[:150], h, "seed")
    assert thin["state"] == "NOT_AVAILABLE" and "200 are needed" in thin["note"] and thin["steps"] == [] and thin["plan"] is None
    assert lp.analyse("X", d, h[:20], "seed")["state"] == "NOT_AVAILABLE"
    twin = d[:300] + [dict(d[299], t=d[299]["t"] + 3600)] + d[300:]          # the same day stamped an hour apart: the series-fault shape
    r = lp.analyse("GOLD", twin, h, "seed")
    assert r["state"] == "SERIES_FAULT" and "daily series" in r["note"] and r["plan"] is None and r["verdict"] == "NOT AVAILABLE"
    assert lp.series_fault(d, 86400) == ""
    dst = [dict(k, t=k["t"] - (3600 if i >= 100 else 0)) for i, k in enumerate(d)]            # a broker day 23 hours long at a clock change is NOT a fault
    assert lp.series_fault(dst, 86400) == ""


def test_round_numbers_and_purity():
    assert lp.round_step(60143) == 1000 and lp.round_step(3537) == 100 and lp.round_step(1.0965) == pytest.approx(0.1) and lp.round_step(158.5) == 10
    a, b = sell_case(310), sell_case(310)
    for r in (a, b):
        r.pop("calculated_at")
    assert a == b                                                               # the same closed bars give the same answer
    d = daily()[:310]
    h = h4_down(d[-1]["c"])
    before = (len(d), d[-1]["c"], len(h), h[-1]["c"])
    lp.analyse("TEST", d, h, "seed")
    assert before == (len(d), d[-1]["c"], len(h), h[-1]["c"])                    # and the bars are not touched


def test_it_is_a_study_and_can_reach_nothing():
    src = (SRC / "limitplan.py").read_text()
    imports = [l for l in src.splitlines() if l.startswith(("import ", "from "))]
    assert set(imports) == {"from __future__ import annotations", "import math", "from datetime import datetime, timezone", "from .chartread import ema, swing_labels",
                            "from .smc import atr_series"}
    for p in SRC.rglob("*.py"):
        if p.name not in ("limitplan.py", "routes.py"):
            assert "limitplan" not in p.read_text(), p                          # the journal, the recorder, the brokers and the decision never read it
    assert "not a signal" in lp.METHODOLOGY["what_it_is"] and "Not tested against outcomes" in lp.METHODOLOGY["what_it_is"]


def test_route_is_read_only_and_says_what_it_cannot_read(client):
    g = client.get("/api/terminal/limit-checklist?symbol=GOLD").json()         # the fixture stores no 4h bars for GOLD
    assert g["state"] == "NOT_AVAILABLE" and "4h bars" in g["note"] and g["recorded"] is False and g["decimals"] == 2
    b = client.get("/api/terminal/limit-checklist?symbol=btc").json()
    assert b["symbol"] == "BTC" and b["state"] == "OK" and b["verdict"] in ("NO TRADE", "WAIT", "CHECKLIST HOLDS") and len(b["steps"]) == 7
    assert b["method_version"] == "limit-checklist-v1" and b["level_label"] == "HYPOTHETICAL ANALYSIS LEVEL" and "freshness" in b
    for verb in (client.post, client.put, client.delete):
        assert verb("/api/terminal/limit-checklist?symbol=BTC").status_code == 405
    assert client.get("/api/terminal/execution/modes").json()["can_place"] is False


def test_a_short_series_is_checked_for_doubled_bars_before_it_is_called_thin():
    """The terminal's own series check is the witness both other sides asked for: "too few bars" must never hide a doubled series."""
    d = daily()[:150]
    twin = d[:100] + [dict(d[99], t=d[99]["t"] + 3600)] + d[100:]
    h = h4_down(d[-1]["c"])
    assert lp.analyse("VIX", twin, h, "seed")["state"] == "SERIES_FAULT"
    assert lp.analyse("VIX", d, h, "seed")["state"] == "NOT_AVAILABLE"


def test_a_target_is_measured_from_the_entry_and_one_that_is_not_beyond_it_fails():
    """Seen on the box (2.13.1, DOT and OIL): price sitting on a support puts "just above it" a little over the price NOW. That is
    still a target once the limit above has filled. What may never pass is a target that is not beyond the ENTRY."""
    for cut in range(260, 321, 2):
        for r in (sell_case(cut), buy_case(cut)):
            p = r["plan"] or {}
            if p.get("tp1") is None or p.get("entry") is None:
                continue
            s = 1 if r["side"] == "SELL" else -1
            if status(r)[5] == "PASS":
                assert s * (p["entry"] - p["tp1"]) > 0 and s * (p["tp1"] - p["tp2"]) > 0 and p["rr1"] > 0
            if s * (p["entry"] - p["tp1"]) <= 0:
                assert status(r)[5] == "FAIL" and r["verdict"] != "CHECKLIST HOLDS"


# ---- the price the steps measure from is the newest closed 1m close, not the last 4h close ----
# Seen on production (Shyam's paste, 2026-11-25 ~21:50 UTC, SILVER): "Price now 39.858" was the 18:00 UTC 4h close while the
# market stood at 41.351 — above the checklist's own stop 40.930 — and the tab still offered a SELL LIMIT at 40.383, BELOW the price.
def test_the_price_now_is_the_newest_closed_1m_close_and_the_tab_says_which_bar():
    d = daily()[:310]
    h = h4_down(d[-1]["c"])
    old = lp.analyse("TEST", d, h, "seed")
    assert old["plan"]["price"] == h[-1]["c"] and old["plan"]["price_is_1m"] is False and "4h close" in old["plan"]["price_basis"] and "four hours old" in old["plan"]["price_basis"]
    t = h[-1]["t"] + 14400 + 3 * 3600                     # a 1m bar closing three hours after the last 4h close
    same = lp.analyse("TEST", d, h, "seed", h[-1]["c"], t)
    assert same["plan"]["price"] == h[-1]["c"] and same["plan"]["price_is_1m"] is True and "1m close" in same["plan"]["price_basis"]
    assert same["plan"]["entry"] == old["plan"]["entry"] and same["verdict"] == old["verdict"]      # the same price gives the same checklist


def test_a_sell_limit_is_never_offered_below_the_price_now():
    d = daily()[:310]
    h = h4_down(d[-1]["c"])
    old = lp.analyse("TEST", d, h, "seed")["plan"]
    up = old["sl"] * 1.004                                # the market has run ABOVE the old stop since the last 4h close
    r = lp.analyse("TEST", d, h, "seed", up, h[-1]["t"] + 14400 + 3 * 3600)
    p = r["plan"]
    assert p["price"] == pytest.approx(up) and p["h4_close"] == h[-1]["c"] and p["price_is_1m"] is True
    assert r["verdict"] != "CHECKLIST HOLDS" or p["entry"] > p["price"]
    if p.get("entry") is not None:                        # whatever zone it reads now is on the entry side of the price NOW
        assert p["entry"] > p["price"] and p["zone_low"] > p["price"] and p["entry"] != old["entry"]
    assert all(lv["value"] > p["price"] for lv in p.get("zone_levels") or [])
    bounce = next(s for s in r["steps"] if s["n"] == 2)
    assert bounce["bounce_pct"] > next(s for s in lp.analyse("TEST", d, h, "seed")["steps"] if s["n"] == 2)["bounce_pct"]     # measured to the price now


def test_a_1m_bar_older_than_the_last_4h_close_is_not_used():
    d = daily()[:310]
    h = h4_down(d[-1]["c"])
    r = lp.analyse("TEST", d, h, "seed", h[-1]["c"] * 1.05, h[-1]["t"] + 14400 - 60)
    assert r["plan"]["price"] == h[-1]["c"] and r["plan"]["price_is_1m"] is False


def test_the_route_reads_the_1m_bar_for_the_price_now(client):
    """The route hands the study the terminal's own header price: the close of the newest closed 1m bar."""
    from datetime import datetime, timezone
    from signalmesh_terminal import routes

    d = daily()[:310]
    h = h4_down(d[-1]["c"])
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()      # noqa: E731
    pay = lambda bars: {"candles": [{"ts": iso(k["t"]), "open": k["o"], "high": k["h"], "low": k["l"], "close": k["c"], "source": "seed"} for k in bars], "freshness": {"state": "LIVE"}}      # noqa: E731
    now_t = h[-1]["t"] + 14400 + 3 * 3600
    px_now = round(lp.analyse("TEST", d, h, "seed")["plan"]["sl"] * 1.004, 3)
    one = {"candles": [{"ts": iso(now_t - 60), "open": px_now, "high": px_now, "low": px_now, "close": px_now, "source": "seed"}], "freshness": {"state": "LIVE"}}
    p = routes.provider()
    p.candles = lambda sym, tf, n: pay(d) if tf == "1d" else pay(h) if tf == "4h" else one
    routes.cache().clear()
    lc = client.get("/api/terminal/limit-checklist?symbol=GOLD").json()
    assert lc["state"] == "OK", lc.get("note")
    assert lc["plan"]["price"] == pytest.approx(px_now) and lc["plan"]["price_is_1m"] is True and "1m close" in lc["plan"]["price_basis"]
    assert lc["plan"]["h4_close"] == pytest.approx(h[-1]["c"]) and lc["verdict"] != "CHECKLIST HOLDS"
    # without a 1m bar the study falls back to the 4h close and SAYS so
    p.candles = lambda sym, tf, n: pay(d) if tf == "1d" else pay(h) if tf == "4h" else {"candles": []}
    routes.cache().clear()
    lc = client.get("/api/terminal/limit-checklist?symbol=GOLD").json()
    assert lc["plan"]["price_is_1m"] is False and lc["plan"]["price"] == pytest.approx(h[-1]["c"]) and "four hours old" in lc["plan"]["price_basis"]
