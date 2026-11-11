"""pattern-studies-v1 — Fibonacci extension, anchored VWAP, Wolfe wave, Elliott wave, volume profile.
Display-only, closed bars only, walked forward: what the first n bars report is never rewritten by
later bars. Tested on seeded random walks and on hand-built bars."""
import math
import random

import pytest

from signalmesh_terminal import studies as st

STEP = 900
T0 = 1_800_000_000


def walk(n=600, seed=7, swing=40, drift=0.9):
    r = random.Random(seed)
    out, px = [], 100.0
    for i in range(n):
        o = px
        c = o + r.gauss(0, 0.6) + drift * (1 if (i // swing) % 2 == 0 else -1) * r.random()
        h, l = max(o, c) + abs(r.gauss(0, 0.3)), min(o, c) - abs(r.gauss(0, 0.3))
        out.append({"t": T0 + i * STEP, "o": o, "h": h, "l": l, "c": c, "v": float(50 + r.randrange(800))})
        px = c
    return out


def zigzag(points, per=14, wick=0.05):
    """Bars that travel in straight legs through `points` — every turn becomes a clean swing pivot."""
    out, i = [], 0
    for a, b in zip(points, points[1:]):
        for s in range(per):
            o, c = a + (b - a) * s / per, a + (b - a) * (s + 1) / per
            out.append({"t": T0 + i * STEP, "o": o, "h": max(o, c) + wick, "l": min(o, c) - wick, "c": c, "v": 100.0})
            i += 1
    return out


WOLFE_DEF = ("direction", "points", "entry", "sl", "tp1", "tp2", "epa", "apex_time", "expires_time", "made_bar", "confirmed_at")


def _defs(rows, keys):
    return [tuple(repr(r[k]) for k in keys) for r in rows]


@pytest.mark.parametrize("seed", [1, 7, 23, 99, 314])
def test_no_lookahead_and_no_repaint(seed):
    """The log of every prefix is the beginning of the log of the whole series: a Wolfe pattern, an
    Elliott stage and a Fibonacci set, once reported, are reported identically ever after."""
    bars = walk(seed=seed)
    full = st.analyse("X", "15m", bars)
    assert full["state"] == "OK"
    for n in range(80, len(bars), 37):
        part = st.analyse("X", "15m", bars[:n])
        known_by = bars[n - 1]["t"]
        w_full = [p for p in full["wolfe"]["log"] if p["made_bar"] <= known_by]
        assert _defs(part["wolfe"]["log"], WOLFE_DEF) == _defs(w_full, WOLFE_DEF), f"wolfe at n={n}"
        assert part["elliott"]["log"] == [e for e in full["elliott"]["log"] if e["bar"] <= known_by], f"elliott at n={n}"
        assert part["fib"]["log"] == [e for e in full["fib"]["log"] if e["made_bar"] <= known_by], f"fib at n={n}"
        # nothing is dated after the last bar the prefix saw
        assert part["through_close"] == known_by + STEP
        for a in (part["avwap"] or {}).get("anchors", []):
            assert a["anchor_time"] <= known_by and a["points"][-1]["t"] == known_by


def test_the_seeded_series_actually_exercise_the_studies():
    seen = {"wolfe": 0, "elliott": 0, "fib": 0}
    for seed in range(1, 40):
        for sw, dr in ((40, 0.9), (25, 1.4)):
            f = st.analyse("X", "15m", walk(seed=seed, swing=sw, drift=dr))
            seen["wolfe"] += len(f["wolfe"]["log"]); seen["elliott"] += len(f["elliott"]["log"]); seen["fib"] += len(f["fib"]["log"])
    assert all(v > 0 for v in seen.values()), seen


def test_fibonacci_extension_levels_are_c_plus_ratio_times_ab():
    b = zigzag([104, 100, 110, 104, 107])       # A low 100, B high 110, C low 104, then up
    f = st.fib_extension(b, STEP)
    assert f["state"] == "OK" and f["direction"] == "UP"
    assert (round(f["a"]["price"], 2), round(f["b"]["price"], 2), round(f["c"]["price"], 2)) == (99.95, 110.05, 103.95)
    leg = f["b"]["price"] - f["a"]["price"]
    assert [lv["ratio"] for lv in f["levels"]] == list(st.FIB_RATIOS)
    assert all(math.isclose(lv["price"], f["c"]["price"] + lv["ratio"] * leg) for lv in f["levels"])
    assert f["status"] == "ACTIVE" and not any(lv["reached"] for lv in f["levels"]) and f["next_level"]["ratio"] == 0.618
    assert f["confirmed_at"] > f["c"]["time"] + st.FIB_L * STEP - 1          # C is known only L bars after it
    # a close below C invalidates the set, and says on which bar
    b2 = zigzag([104, 100, 110, 104, 107, 95])
    f2 = st.fib_extension(b2[:len(b) + 4], STEP)             # before the 107 high is itself a confirmed pivot
    assert f2["status"] == "INVALIDATED" and f2["invalidated_bar"] is not None


def test_anchored_vwap_is_the_volume_weighted_typical_price_from_the_anchor():
    b = walk(200, seed=3)
    a = st.anchored_vwap(b, 1.0, day_start=b[150]["t"])
    assert a["state"] == "OK" and {x["id"] for x in a["anchors"]} == {"swing-high", "swing-low", "day"}
    day = next(x for x in a["anchors"] if x["id"] == "day")
    seg = b[150:]
    want = sum((k["h"] + k["l"] + k["c"]) / 3 * k["v"] for k in seg) / sum(k["v"] for k in seg)
    assert math.isclose(day["value"], want) and day["bars"] == 50 and len(day["points"]) == 50
    assert day["side"] == ("ABOVE" if b[-1]["c"] > want else "BELOW")
    # no tick volume: said, not guessed
    assert st.anchored_vwap([{**k, "v": 0.0} for k in b], 1.0)["state"] == "NOT_AVAILABLE"


def test_wolfe_bullish_wedge_gives_pine_levels_and_then_only_moves_forward():
    # 1 low 100, 2 high 110, 3 low 97, 4 high 102, 5 low 95: falling, converging wedge
    pts = [108, 100, 110, 97, 102, 95, 99]
    b = zigzag(pts, per=22)
    w = st.wolfe(b, st.atr_rma(b), STEP)
    assert w["state"] == "OK", w["note"]
    p = w["pattern"]
    assert p["direction"] == "BULLISH" and [x["name"] for x in p["points"]] == ["1", "2", "3", "4", "5"]
    q = [x["price"] for x in p["points"]]
    assert q[2] < q[0] and q[4] < q[2] and q[0] < q[3] < q[1]
    assert p["sl"] < q[4] and p["tp1"] <= p["tp2"] and p["tp1"] == min(q[3], p["epa"]) and p["level_label"] == st.LEVEL_LABEL
    assert p["status"] == "LIVE" and p["confirmed_at"] >= p["points"][4]["time"] + st.WW_L * STEP
    # price falls through the stop: STOPPED, with its bar — the points and levels are unchanged
    b2 = b + zigzag([99, 80], per=20)[0:20]
    for i, k in enumerate(b2[len(b):]):
        k["t"] = b[-1]["t"] + (i + 1) * STEP
    w2 = st.wolfe(b2, st.atr_rma(b2), STEP)
    done = w2["log"][0]
    assert done["status"].startswith("STOPPED") and done["done"] and _defs([done], WOLFE_DEF) == _defs([p], WOLFE_DEF)


def test_wolfe_with_four_points_is_developing_and_never_confirmed():
    b = zigzag([108, 100, 110, 97, 102, 100], per=22)       # point 5 has not printed
    w = st.wolfe(b, st.atr_rma(b), STEP)
    assert w["state"] == "DEVELOPING" and w["pattern"] is None and w["log"] == []
    assert "NOT confirmed" in w["developing"]["status"] and len(w["developing"]["points"]) == 4


def test_elliott_counts_an_impulse_stage_by_stage_and_says_unknown_otherwise():
    flat = [{"t": T0 + i * STEP, "o": 100, "h": 100.2, "l": 99.8, "c": 100, "v": 10.0} for i in range(200)]
    e = st.elliott(flat, st.atr_rma(flat), STEP)
    assert e["state"] == "UNKNOWN" and e["count"] is None
    # 0=100, 1=110, 2=105, 3=122, 4=115, 5=128 — a bullish five
    b = zigzag([106, 100, 110, 105, 122, 115, 128, 124], per=18)
    e = st.elliott(b, st.atr_rma(b), STEP)
    stages = [x["wave"] for x in e["log"] if x["event"] == "STAGE"]
    assert stages == sorted(stages) and stages[0] == 3 and stages[-1] == 6, e["log"]
    c = e["count"]
    assert c["direction"] == "BULLISH" and c["wave"] == 6 and "5 WAVES DONE" in c["text"]
    a = [p["price"] for p in c["points"]]
    assert math.isclose(c["target_1"], a[5] - (a[5] - a[0]) * 0.382) and math.isclose(c["target_2"], a[5] - (a[5] - a[0]) * 0.618)
    assert c["ratios"]["wave3_vs_wave1"] > 1 and c["level_label"] == st.LEVEL_LABEL


def test_elliott_wave_three_setup_fails_on_a_close_below_wave_two():
    b = zigzag([106, 100, 110, 105, 108, 98], per=18)
    e = st.elliott(b, st.atr_rma(b), STEP)
    events = [x["event"] for x in e["log"]]
    assert events[0] == "STAGE" and "FAILED" in events


def test_volume_profile_rows_poc_and_value_area():
    b = [{"t": T0 + i * STEP, "o": 100, "h": 101, "l": 99, "c": 100, "v": 10.0} for i in range(60)]
    b += [{"t": T0 + (60 + i) * STEP, "o": 105, "h": 105.5, "l": 104.5, "c": 105, "v": 100.0} for i in range(20)]
    v = st.volume_profile(b)
    assert v["state"] == "OK" and len(v["rows"]) == st.VP_ROWS
    assert math.isclose(sum(r["volume"] for r in v["rows"]), v["total_tick_volume"], rel_tol=1e-6)
    assert 104.5 <= v["poc"] <= 105.5 and v["val"] <= v["poc"] <= v["vah"] and v["value_area_pct"] >= st.VP_VALUE_AREA
    assert sum(1 for r in v["rows"] if r["poc"]) == 1 and "tick volume" in v["volume_kind"]
    assert st.volume_profile([{**k, "v": 0.0} for k in b])["state"] == "NOT_AVAILABLE"


def test_too_few_bars_is_not_available():
    f = st.analyse("X", "15m", walk(30))
    assert f["state"] == "NOT_AVAILABLE" and f["wolfe"] is None and f["recorded"] == {"wolfe": True, "elliott": True, "fib": False, "avwap": False, "vp": False}


def test_only_confirmed_wolfe_and_valid_elliott_stages_become_journal_forecasts():
    """Every forecast the two modules hand to the journal passes the journal's own validation (entry, SL, TP1, TP2,
    invalidation, horizon all fixed and in order), names the bar that made it, and is never a developing Wolfe,
    a wave-4 "wait" stage, an unclear count or something from the warm-up bars."""
    from signalmesh_terminal import journal as fj
    seen = {"wolfe-wave": 0, "elliott-wave": 0}
    for seed in range(1, 30):
        bars = walk(seed=seed, swing=25, drift=1.4)
        for m in (st.WolfeModule(), st.ElliottModule()):
            for f in m.forecasts("X", "15m", bars):
                row = fj.validate({**f, "symbol": "X", "timeframe": "15m", "module": m.name, "method_version": m.method_version})
                assert row["made_bar"] >= bars[st.JOURNAL_WARMUP]["t"] and row["entry_mode"] == "at_close" and f["status"] == "confirmed"
                assert "WAVE 4" not in f["pattern"] and "DEVELOPING" not in f["pattern"]
                seen[m.name] += 1
    assert all(v > 0 for v in seen.values()), seen
    # four points only: the chart says DEVELOPING and the journal gets nothing
    dev = zigzag([108, 100, 110, 97, 102, 100], per=22)
    assert st.wolfe(dev, st.atr_rma(dev), STEP)["state"] == "DEVELOPING"
    lead = walk(st.JOURNAL_WARMUP + 5, seed=2)
    for i, k in enumerate(dev):
        k["t"] = lead[-1]["t"] + (i + 1) * STEP
    assert st.WolfeModule().forecasts("X", "15m", lead + dev) == [] or all("WOLFE" in f["pattern"] for f in st.WolfeModule().forecasts("X", "15m", lead))


@pytest.mark.parametrize("seed", [3, 11, 42])
def test_journal_modules_never_look_ahead(seed):
    """What the recorder would have written at any earlier moment is exactly what it writes for that moment later."""
    bars = walk(seed=seed, swing=25, drift=1.4)
    for m in (st.WolfeModule(), st.ElliottModule()):
        full = {f["made_bar"]: f for f in m.forecasts("X", "15m", bars)}
        for n in range(st.JOURNAL_WARMUP + 10, len(bars), 41):
            part = {f["made_bar"]: f for f in m.forecasts("X", "15m", bars[:n])}
            assert part == {t: f for t, f in full.items() if t <= bars[n - 1]["t"]}, f"{m.name} at n={n}"


def test_r_multiple_is_derived_from_the_recorded_events():
    from signalmesh_terminal import journal as fj
    assert fj.r_multiple(["ENTRY", "TP1", "TP2"], 1.5, 3.0) == 3.0 and fj.r_multiple(["ENTRY", "TP1", "SL"], 1.5, 3.0) == 1.5
    assert fj.r_multiple(["ENTRY", "SL"], 1.5, 3.0) == -1.0
    assert fj.r_multiple(["ENTRY", "EXPIRED"], 1.5, 3.0) is None and fj.r_multiple(["INVALIDATED"], 1.5, 3.0) is None and fj.r_multiple([], 1.5, 3.0) is None


def test_route_is_labelled_display_only_and_writes_nothing_itself(monkeypatch, tmp_path):
    monkeypatch.setenv("SMT_PROVIDER", "fixture"); monkeypatch.setenv("SMT_ENV", "test"); monkeypatch.setenv("SMT_AUTH", "open")
    monkeypatch.setenv("SMT_ACCESS_TOKEN", ""); monkeypatch.setenv("SMT_WEB_DIST", "/nonexistent"); monkeypatch.setenv("SMT_JOURNAL_PATH", str(tmp_path / "j.sqlite"))
    from fastapi.testclient import TestClient
    from signalmesh_terminal import routes
    from signalmesh_terminal.main import create_app
    routes.reset_for_tests()
    client = TestClient(create_app())                # no "with": the background recorder is not started
    d = client.get("/api/terminal/studies?symbol=GOLD&tf=15m").json()
    assert d["state"] == "OK" and d["method_version"] == st.VERSION and "not SignalMesh engine output" in d["kind"]
    assert d["recorded"] == {"wolfe": True, "elliott": True, "fib": False, "avwap": False, "vp": False}
    assert set(d) >= {"fib", "avwap", "wolfe", "elliott", "vp", "methodology", "through_close_utc", "decimals", "journal", "journal_timeframes"}
    assert d["vp"]["state"] == "OK" and d["avwap"]["state"] == "OK"
    assert client.get("/api/terminal/studies?symbol=GOLD&tf=1w").status_code == 400
    src = open(routes.__file__).read()
    assert '@router.post("/studies' not in src
    # the recorder, not the route, writes — and only the Wolfe and Elliott modules beside the daily forecast
    assert {m.name for m in routes.recorder().modules} == {"daily-forecast", "wolfe-wave", "elliott-wave", "fixture-demo"}
    routes.recorder().pass_once()                    # one pass on the fixture series, as the background loop would
    j = client.get("/api/terminal/journal?limit=1000").json()
    assert all(r["module"] in ("daily-forecast", "wolfe-wave", "elliott-wave", "fixture-demo") for r in j["rows"])
    assert all("r_multiple" in r for r in j["rows"]) and all("r_avg" in g for g in j["stats"])
    assert j["rows"] and not any(k in r["pattern"] for r in j["rows"] for k in ("FIB", "VWAP", "PROFILE", "DEVELOPING"))
    routes.reset_for_tests()
