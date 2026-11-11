"""smc-v1 — the Smart Money Concepts studies are display-only, use closed bars only, never look
ahead, and never repaint a confirmed structure. Tested on seeded random walks and on hand-built bars."""
import random
from datetime import datetime, timezone

import pytest

from signalmesh_terminal import smc

STEP = 900


def walk(n=320, seed=7, t0=1_800_000_000):
    r = random.Random(seed)
    out, px = [], 100.0
    for i in range(n):
        o = px
        c = o + r.gauss(0, 0.6) + 0.9 * (1 if (i // 40) % 2 == 0 else -1) * r.random()
        h, l = max(o, c) + abs(r.gauss(0, 0.3)), min(o, c) - abs(r.gauss(0, 0.3))
        out.append({"t": t0 + i * STEP, "o": o, "h": h, "l": l, "c": c})
        px = c
    return out


def bar(i, o, h, l, c, t0=1_800_000_000):
    return {"t": t0 + i * STEP, "o": o, "h": h, "l": l, "c": c}


# what DEFINES a structure (never changes) vs. its status (moves forward only)
DEFINING = {"swings": ("scope", "kind", "price", "time", "confirmed_at"), "structure": ("type", "dir", "scope", "level", "swing_time", "time", "confirmed_at"),
            "fvg": ("dir", "low", "high", "time", "confirmed_at"), "order_blocks": ("dir", "low", "high", "time", "confirmed_at", "from", "strength_atr"),
            "inducement": ("dir", "level", "time", "confirmed_at")}


def keyed(result, feature):
    return {tuple(row[k] for k in DEFINING[feature]) for row in result[feature]}


@pytest.mark.parametrize("seed", [1, 7, 23, 99])
def test_no_lookahead_and_no_repaint(seed):
    """Every structure the first n bars establish exists, identically, in the analysis of ALL bars —
    and nothing the full analysis dates inside the first n bars is missing from the n-bar analysis."""
    bars = walk(seed=seed)
    full = smc.analyse("X", "15m", bars)
    assert full["state"] == "OK" and all(len(full[f]) > 0 for f in ("swings", "structure", "fvg", "order_blocks"))
    for n in (60, 120, 200, 260, 319):
        part = smc.analyse("X", "15m", bars[:n])
        known_by = bars[n - 1]["t"] + STEP                      # the close of the last bar the prefix saw
        for f in DEFINING:
            a, b = keyed(part, f), {k for k in keyed(full, f) if k[DEFINING[f].index("confirmed_at")] <= known_by}
            assert a == b, f"{f} at n={n}: only-in-prefix {sorted(a - b)[:2]} only-in-full {sorted(b - a)[:2]}"


def test_nothing_is_dated_before_it_could_be_known():
    bars = walk()
    r = smc.analyse("X", "15m", bars)
    for f in DEFINING:
        for row in r[f]:
            assert row["confirmed_at"] > row["time"] and row["confirmed_at"] <= r["through_close"]
            if row.get("status_at") is not None:
                assert row["status_at"] >= row["confirmed_at"]
    for s in r["swings"]:                                       # a pivot is confirmed exactly L bars after it
        L = smc.L_EXTERNAL if s["scope"] == "external" else smc.L_INTERNAL
        assert s["confirmed_at"] == s["time"] + (L + 1) * STEP


def test_a_close_breaks_and_a_wick_sweeps():
    b = [bar(i, 10, 10.5, 9.5, 10) for i in range(20)]
    b[8] = bar(8, 10, 12, 9.8, 10.2)                            # swing high 12, confirmed at bar 13
    b[16] = bar(16, 10, 12.4, 9.9, 11.0)                        # wick above 12, close back below -> SWEEP, not a break
    r = smc.analyse("X", "15m", b + [bar(20 + i, 10, 10.5, 9.5, 10) for i in range(15)])
    high = next(l for l in r["liquidity"] if l["side"] == "BSL" and l["level"] == 12)
    assert high["status"] == "swept" and not [e for e in r["structure"] if e["level"] == 12]
    b[16] = bar(16, 10, 12.6, 9.9, 12.3)                        # CLOSE above 12 -> break of structure
    r = smc.analyse("X", "15m", b + [bar(20 + i, 12.3, 12.6, 12.0, 12.3) for i in range(15)])
    ev = [e for e in r["structure"] if e["level"] == 12 and e["scope"] == "external"]
    assert ev and ev[0]["type"] == "BOS" and ev[0]["dir"] == "bull" and ev[0]["time"] == b[16]["t"]
    assert next(l for l in r["liquidity"] if l["level"] == 12)["status"] == "broken"


def test_choch_is_a_break_against_the_trend():
    bars = walk(seed=7)
    ev = [e for e in smc.analyse("X", "15m", bars)["structure"] if e["scope"] == "external"]
    trend = None
    for e in sorted(ev, key=lambda e: e["confirmed_at"]):
        assert e["type"] == ("CHoCH" if trend and trend != e["dir"] else "BOS")
        trend = e["dir"]
    assert {e["type"] for e in ev} == {"BOS", "CHoCH"}


def test_fvg_is_the_three_candle_gap_and_its_mitigation_moves_forward():
    flat = [bar(i, 10, 10.4, 9.6, 10) for i in range(20)]
    b = flat + [bar(20, 10, 10.4, 9.9, 10.3), bar(21, 10.3, 12.2, 10.3, 12.0), bar(22, 12.0, 12.6, 11.4, 12.4)]   # low[22]=11.4 > high[20]=10.4
    after = [bar(23 + i, 12.4, 12.8, 12.1, 12.5) for i in range(10)]
    g = [x for x in smc.analyse("X", "15m", b + after)["fvg"] if x["dir"] == "bull"]
    assert g and (g[-1]["low"], g[-1]["high"], g[-1]["status"]) == (10.4, 11.4, "fresh") and g[-1]["time"] == b[21]["t"]
    dip = [bar(23, 12.4, 12.5, 10.9, 12.2)] + [bar(24 + i, 12.2, 12.5, 12.0, 12.3) for i in range(9)]        # enters the gap, does not cross it
    g = [x for x in smc.analyse("X", "15m", b + dip)["fvg"] if x["dir"] == "bull"][-1]
    assert g["status"] == "partial" and g["filled_pct"] == 50
    fill = [bar(23, 12.4, 12.5, 10.2, 11.0)] + [bar(24 + i, 11, 11.3, 10.8, 11) for i in range(9)]
    assert [x for x in smc.analyse("X", "15m", b + fill)["fvg"] if x["dir"] == "bull"][-1]["status"] == "mitigated"


def test_order_blocks_come_from_structure_breaks_and_have_a_life():
    r = smc.analyse("X", "15m", walk(seed=23))
    assert r["order_blocks"]
    for ob in r["order_blocks"]:
        assert ob["status"] in ("fresh", "tested", "invalidated") and ob["low"] < ob["high"] and "BOS" in ob["from"] or "CHoCH" in ob["from"]
        assert (ob["mitigation"] == "unmitigated") == (ob["status"] == "fresh")
    assert {ob["status"] for ob in r["order_blocks"]} & {"tested", "invalidated"}


def test_too_few_bars_draws_nothing():
    r = smc.analyse("X", "15m", walk(n=10))
    assert r["state"] == "TOO_FEW_BARS" and r["structure"] == [] and r["sr"] == [] and "guessed" in r["note"]
    assert smc.analyse("X", "15m", [])["state"] == "NO_CANDLES"


def test_weeks_are_closed_iso_weeks_and_key_levels_come_from_closed_bars():
    now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)                       # a Wednesday
    day0 = int(datetime(2026, 10, 26, tzinfo=timezone.utc).timestamp())             # Monday two weeks before
    daily = [{"t": day0 + i * 86400, "o": 100 + i, "h": 105 + i, "l": 95 + i, "c": 101 + i} for i in range(17)]   # through Wed 11 Nov
    weeks = smc.weekly_from_daily(daily, now)
    assert len(weeks) == 2 and weeks[-1]["t"] == day0 + 7 * 86400 and weeks[-1]["h"] == 105 + 13      # the running week is not a bar
    h0 = int(datetime(2026, 11, 10, tzinfo=timezone.utc).timestamp())
    hourly = [{"t": h0 + i * 3600, "o": 112, "h": 113, "l": 111, "c": 112} for i in range(36)]
    hourly[30] = {"t": h0 + 30 * 3600, "o": 112, "h": 125, "l": 111, "c": 112}      # 06:00 on the 11th: wick above PDH, close back
    lv = {x["kind"]: x for x in smc.key_levels(daily, hourly, now)}
    assert lv["PDH"]["level"] == 105 + 15 and lv["PDH"]["status"] == "swept" and lv["PDL"]["status"] == "unswept"
    assert lv["PWH"]["level"] == 105 + 13 and {"LONDON high", "NEW YORK low", "ASIA high"} <= set(lv)


def test_routes_and_engine_independence(client):
    before = client.get("/api/terminal/decision?symbol=GOLD").json()
    r = client.get("/api/terminal/smc?symbol=GOLD&tf=15m").json()
    assert r["state"] == "OK" and "display-only" in r["rule"] and set(r["methodology"]) >= {"fvg", "structure", "order_blocks", "liquidity", "inducement", "sr"}
    assert all(row["tf"] == "15m" for f in ("structure", "fvg", "order_blocks", "liquidity", "sr") for row in r[f])
    assert client.get("/api/terminal/smc?symbol=GOLD&tf=4h").json()["state"] == "NO_CANDLES"      # the fixture stores no 4h GOLD bars
    assert client.get("/api/terminal/smc?symbol=GOLD&tf=1m").status_code == 400
    assert client.get("/api/terminal/smc/key-levels?symbol=GOLD").status_code == 200
    after = client.get("/api/terminal/decision?symbol=GOLD").json()
    for k in ("engine_status", "summary", "entry", "sl", "tp1", "tp2", "levels", "brain_plan", "lanes", "sides", "grade", "score"):
        assert before[k] == after[k]                                              # the studies change nothing the engine says
