import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from signalmesh_terminal.normalize import (candle_series, decimals_for, decision_view, lane_state, levels_for,
                                           market_watch_row, signal_ref)

FX = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FX / f"{name}.json").read_text())


def test_candles_reshape_keeps_values_and_sorts():
    raw = load("candles_gold_15m")
    cs = candle_series("fixture", "GOLD", "15m", raw)
    assert cs.count == raw["count"] == len(cs.candles)
    assert cs.closed_only is True
    assert cs.freshness.state == raw["freshness"]["state"]
    assert cs.provenance.source == raw["price_source"]
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
    lv, sig = levels_for("GOLD", {"status": "READY", "entry": 100, "sl": 99, "tp1": 102, "tp2": None}, sigs)
    assert [l.value for l in lv] == [100, 99, 102] and all(l.origin == "plan" for l in lv)
    lv, sig = levels_for("GOLD", {"status": "WAIT"}, sigs)
    assert sig.signal_id == "NEW" and all(l.stale for l in lv) and lv[0].label.startswith("OLD PLAN")
    assert [l.key for l in lv] == ["entry", "sl", "tp1", "tp2"]
    assert levels_for("SILVER", {"status": "WAIT"}, sigs) == ([], None)


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
