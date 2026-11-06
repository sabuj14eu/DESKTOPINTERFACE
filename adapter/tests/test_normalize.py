import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from signalmesh_terminal.normalize import (bar_ref, candle_series, decimals_for, decision_view, lane_state, levels_for,
                                           market_watch_row, side_states, signal_ref, source_kind)
from signalmesh_terminal.contract import LaneState

FX = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FX / f"{name}.json").read_text())


def test_candles_reshape_keeps_values_and_sorts():
    raw = load("candles_gold_15m")
    cs = candle_series("fixture", "GOLD", "15m", raw)
    assert cs.count == raw["count"] == len(cs.candles)
    assert cs.closed_only is True
    assert cs.freshness.state == raw["freshness"]["state"]
    # provenance = the per-candle source (authority), never the platform's static label
    assert cs.provenance.source == raw["candles"][-1]["source"] == "fixture:local-verification"
    assert cs.platform_label == raw["price_source"]
    assert cs.source_kind == "fixture" and "FIXTURE" in cs.source_warning
    assert cs.last_bar is not None and cs.last_bar.price == raw["candles"][-1]["close"]
    assert cs.last_bar.bar_close_ts > cs.last_bar.bar_open_ts
    assert cs.freshness_basis == "since_open"
    first_raw = raw["candles"][0]
    assert cs.candles[0].open == first_raw["open"] and cs.candles[0].close == first_raw["close"]
    assert cs.candles[0].time == int(datetime.fromisoformat(first_raw["ts"]).timestamp())
    assert [c.time for c in cs.candles] == sorted(c.time for c in cs.candles)
    assert cs.decimals == 2


def test_decimals_table_mirrors_platform():
    assert decimals_for("GOLD") == 2 and decimals_for("SILVER") == 3 and decimals_for("BTC") == 1
    assert decimals_for("EURUSD") == 5 and decimals_for("UNKNOWNSYM", 0.5) == 5


def test_signal_buckets_and_ttl():
    now = datetime.now(timezone.utc)
    fresh = {"signal_id": "A", "symbol": "GOLD", "status": "approved", "created_at": (now - timedelta(hours=1)).isoformat(),
             "council": {"approve": 6, "total": 6}}
    old = {**fresh, "signal_id": "B", "created_at": (now - timedelta(hours=13)).isoformat()}
    pend = {**fresh, "signal_id": "C", "status": "pending"}
    rej = {**fresh, "signal_id": "D", "status": "rejected"}
    assert signal_ref(fresh, 12).bucket == "ACTIVE" and signal_ref(fresh, 12).stale is False
    assert signal_ref(old, 12).bucket == "EXPIRED" and signal_ref(old, 12).stale is True
    assert signal_ref(pend, 12).bucket == "PENDING"
    assert signal_ref(rej, 12).bucket == "REJECTED"
    assert signal_ref(fresh, 12).council_approve == 6


def test_levels_rule_prefers_ready_plan_then_newest_signal():
    now = datetime.now(timezone.utc)
    sigs = [signal_ref({"signal_id": "NEW", "symbol": "GOLD", "status": "approved", "entry": 10, "sl": 9, "tp1": 12, "tp2": 13,
                        "direction": "BUY", "created_at": (now - timedelta(hours=20)).isoformat()}, 12),
            signal_ref({"signal_id": "REJ", "symbol": "GOLD", "status": "rejected", "entry": 1, "sl": 2, "tp1": 3,
                        "created_at": now.isoformat()}, 12)]
    lv, sig, exp = levels_for("GOLD", {"status": "READY", "entry": 100, "sl": 99, "tp1": 102, "tp2": None}, sigs)
    assert [l.value for l in lv] == [100, 99, 102] and all(l.origin == "plan" for l in lv)
    # an EXPIRED signal never becomes a current level: it goes to expired_plan
    lv, sig, exp = levels_for("GOLD", {"status": "WAIT"}, sigs)
    assert lv == [] and sig is None
    assert exp is not None and exp.signal.signal_id == "NEW" and all(l.stale for l in exp.levels)
    assert [l.key for l in exp.levels] == ["entry", "sl", "tp1", "tp2"] and "HISTORY" in exp.note
    # a live (non-expired) approved signal does draw
    live = [signal_ref({"signal_id": "LIVE", "symbol": "GOLD", "status": "approved", "entry": 10, "sl": 9, "tp1": 12,
                        "direction": "BUY", "created_at": (now - timedelta(hours=1)).isoformat()}, 12)]
    lv, sig, exp = levels_for("GOLD", {"status": "WAIT"}, live)
    assert [l.value for l in lv] == [10, 9, 12] and not any(l.stale for l in lv) and sig.signal_id == "LIVE" and exp is None
    assert levels_for("SILVER", {"status": "WAIT"}, sigs) == ([], None, None)


def test_decision_view_is_verbatim_engine_output():
    snap = load("snapshot_gold")
    desk = load("desk_gold")
    sigs = [signal_ref(s, 12) for s in load("signals")]
    dv = decision_view("fixture", "GOLD", snap, sigs, desk)
    dec = snap["snapshot"]["decision"]
    assert dv.engine_status == dec["status"] == "WAIT" and dv.summary == "WAIT"
    assert dv.reason == dec["reason"] and dv.why == dec["why"]
    assert dv.last_close == snap["snapshot"]["market"]["last_close"]
    assert dv.atr == snap["snapshot"]["market"]["atr"]
    assert dv.bias == snap["snapshot"]["market"]["validated_bias"]
    assert dv.freshness["plan"].state == "STALE"
    assert dv.lane.engine == "auto-v1" and dv.lane.decision == "WAIT" and dv.lane.reasons == ["STRUCTURE_UNKNOWN"]
    assert dv.lane.confirmation_text.startswith("wait for structure to be MEASURED")
    assert dv.gates and dv.gates[0]["gate"] == "DATA"
    assert dv.provenance.source == snap["price_source"]
    # the fixture's plan signal is 41h old: history, not a level
    assert dv.levels == [] and dv.expired_plan is not None and dv.expired_plan.signal.signal_id == "SIG-20261105-0071"
    assert dv.sides["SELL"].state == "INVALID" and "EXPIRED" in dv.sides["SELL"].reason
    assert dv.sides["BUY"].state == "WAIT"
    # price contract: engine reference = snapshot last_close on the 15m bar it names
    assert dv.price.engine_reference.price == snap["snapshot"]["market"]["last_close"]
    assert dv.price.engine_reference.bar_open_ts.startswith(snap["snapshot"]["market"]["last_bar_ts"][:16])
    assert dv.price.tick["state"] == "UNAVAILABLE"
    assert dv.price.drift.get("rule") == "ref-drift-v1"


def test_summary_word_mapping():
    base = load("snapshot_gold")
    for eng, word in (("READY", "READY"), ("WAIT", "WAIT"), ("NO TRADE", "INVALIDATED"), ("??", "UNKNOWN")):
        snap = json.loads(json.dumps(base))
        snap["snapshot"]["decision"]["status"] = eng
        assert decision_view("fixture", "GOLD", snap, []).summary == word


def test_lane_wording_mixed_structure():
    desk = {"desk": {"lanes": [{"label": "🟩 Intraday", "c": {"engine": "auto-v1", "decision": "WAIT", "reasons": ["STRUCTURE_MIXED"]}}]}}
    ls = lane_state(desk)
    assert "mixed structure builds nothing" in ls.confirmation_text and ls.stage == "NO SETUP"


def test_market_watch_row_never_upgrades_freshness():
    c = load("candles_gold_15m")
    c["freshness"]["state"] = "STALE"
    row = market_watch_row("GOLD", c, load("snapshot_gold"), load("desk_gold"))
    assert row.freshness.state == "STALE" and row.price == c["candles"][-1]["close"]
    assert row.change_basis.startswith("session")
    empty = market_watch_row("GOLD", None, None, None, error="down")
    assert empty.price is None and empty.freshness.state == "UNKNOWN" and empty.error == "down"


def test_side_states_rule():
    lane = LaneState()
    r = side_states("READY", "BUY LIMIT", "confirmed brain plan (v18), 1h old", [], None, lane)
    assert r["BUY"].state == "READY" and r["SELL"].state == "WAIT"
    r = side_states("NO TRADE", None, "high-impact news window", [], None, lane)
    assert r["BUY"].state == r["SELL"].state == "INVALID" and r["BUY"].reason == "high-impact news window"
    sell_old = signal_ref({"signal_id": "X", "symbol": "GOLD", "status": "approved", "direction": "SELL",
                           "created_at": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()}, 12)
    r = side_states("WAIT", None, "last approved plan is 30h old — EXPIRED, wait for a fresh one", [], sell_old, lane)
    assert r["SELL"].state == "INVALID" and r["BUY"].state == "WAIT"
    r = side_states("WAIT", None, "buy zone — no confirmed brain entry yet", [], None, LaneState(decision="BUY", stage="DEVELOPING"))
    assert r["BUY"].state == "WAIT" and r["BUY"].lane == "desk lane BUY · DEVELOPING"


def test_source_kind_classification():
    assert source_kind("mt5:52834417")[0] == "mt5_reporter" and source_kind("mt5:52834417")[1] == ""
    assert source_kind("fixture:local-verification")[0] == "fixture"
    assert source_kind("")[0] == "unstated"
    assert source_kind("bridge")[0] == "bridge"
    assert source_kind("pine")[0] == "other" and source_kind("pine")[1]


def test_bar_ref_names_both_clocks():
    raw = load("candles_gold_15m")
    b = bar_ref("GOLD", "15m", raw)
    assert b.tf == "15m" and abs(b.since_open_min - b.since_close_min - 15.0) < 0.01
    assert b.source_kind == "fixture"
    assert bar_ref("GOLD", "15m", {"candles": []}) is None


def test_market_watch_row_carries_source_kind():
    c = load("candles_gold_15m")
    row = market_watch_row("GOLD", c, load("snapshot_gold"), load("desk_gold"))
    assert row.source_kind == "fixture" and row.source_warning and row.bar_close_ts and row.since_close_min is not None
