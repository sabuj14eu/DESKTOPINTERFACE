"""signal-sender-v1 and sender-cards-v1 — whose plan is it, and whose win rate.

The platform's note of 2026-11-25: the plan the terminal printed as the BRAIN's was the EA's most of the time, because
`/api/v1/signals` returns the newest rows of every sender. Shyam's word the same day: "do not delete live brain trading
because i like this" — so nothing is removed and nothing gets quieter: the newest plan of every sender is still shown,
and each plan carries its sender's name. The word "brain" stays on rows whose `system` is v18.
"""
from datetime import datetime, timedelta, timezone

from signalmesh_terminal import normalize, routes, transparency
from signalmesh_terminal.providers.base import ProviderError

NOW = datetime(2026, 11, 25, 21, 0, tzinfo=timezone.utc)


def sig(system, sid, status="approved", direction="SELL", entry=41.436, sl=41.81, tp1=41.209, minutes=10, **more):
    return {"signal_id": sid, "system": system, "symbol": "SILVER", "tf": "15m", "direction": direction, "entry": entry, "sl": sl, "tp1": tp1, "tp2": 41.028,
            "status": status, "created_at": (NOW - timedelta(minutes=minutes)).isoformat(), **more}


def test_a_sender_is_read_from_the_rows_own_system_and_nothing_else():
    s = normalize.signal_sender
    assert s("v18", "PB-SELL-1") == {"system": "v18", "name": "Pine v18 · council", "brain": True, "note": s("v18")["note"]}
    assert s("v18", "SC-LONDON-1")["name"] == "session caller · v18" and s("v18", "SC-LONDON-1")["brain"] is True
    assert s("NQ-EA", "NQ:XAGUSD:NQ-P1")["name"] == "NRTR EA" and s("NQ-EA")["brain"] is False
    assert s("mt5", "PB-SELL--95597200")["name"] == "MT5 EA sensor" and s("mt5")["brain"] is False
    assert s("v7")["name"] == "v7" and s("v7")["brain"] is False                 # an unlisted word is printed as sent
    assert s("")["name"] == "sender not stated" and s(None)["brain"] is False
    assert s("V18")["brain"] is False and s(" v18 ")["brain"] is True            # exact, as the platform's own rule; only the edges are trimmed
    # the id never names a sender: a PB- id under system mt5 is the EA sensor's, whatever it looks like
    assert s("mt5", "PB-SELL--95597200")["brain"] is False


def test_the_latest_plan_is_still_the_newest_of_every_sender_and_now_says_whose():
    ea = normalize.signal_ref(sig("NQ-EA", "NQ:XAGUSD:NQ-P1", minutes=2), 12.0, NOW)
    brain = normalize.signal_ref(sig("v18", "PB-SELL-7", minutes=40), 12.0, NOW)
    bp = normalize.brain_plan(ea, None)                                          # the newest plan is the EA's: it is SHOWN, as before
    assert bp.state == "LIVE" and bp.signal.signal_id == "NQ:XAGUSD:NQ-P1" and bp.brain is False and bp.sender["name"] == "NRTR EA"
    bp = normalize.brain_plan(brain, None)
    assert bp.brain is True and bp.sender["name"] == "Pine v18 · council"
    assert "ANY sender" in bp.rule and "v18" in bp.rule
    none = normalize.brain_plan(None, None)
    assert none.state == "NEVER_POSTED" and none.brain is False and "any sender" in none.note


def test_reward_to_risk_to_the_first_target_comes_from_the_rows_own_prices():
    r = normalize.signal_ref(sig("NQ-EA", "X", direction="SELL", entry=100.0, sl=101.0, tp1=99.0), 12.0, NOW)
    assert r.rr_tp1 == 1.0
    r = normalize.signal_ref(sig("NQ-EA", "X", direction="BUY", entry=100.0, sl=98.5, tp1=101.0), 12.0, NOW)
    assert r.rr_tp1 == 0.67
    for bad in (dict(tp1=None), dict(sl=None), dict(direction=""), dict(direction="SELL", entry=100.0, sl=99.0, tp1=98.0),      # a stop on the wrong side: not measured
                dict(direction="BUY", entry=100.0, sl=99.0, tp1=99.5)):                                                        # a target on the wrong side
        assert normalize.signal_ref(sig("NQ-EA", "X", **{**dict(direction="SELL", entry=100.0, sl=101.0, tp1=99.0), **bad}), 12.0, NOW).rr_tp1 is None


def test_no_council_word_is_printed_for_a_row_the_council_did_not_judge():
    raw = sig("NQ-EA", "NQ:XAGUSD:NQ-P1")
    d = transparency.signal_detail(normalize.signal_ref(raw, 12.0, NOW), raw, [], 12.0)
    assert "brain" not in d["headline"].lower() and "NRTR EA" in d["headline"] and "council did not judge" in d["headline"]
    b1 = next(s for s in d["lifecycle"] if s["key"] == "council")
    assert b1["state"] == "NOT_RECORDED" and "not judged by the council" in b1["detail"] and "NRTR EA" in b1["detail"]
    raw = sig("v18", "PB-SELL-7")
    d = transparency.signal_detail(normalize.signal_ref(raw, 12.0, NOW), raw, [], 12.0)
    assert "approved by the brain council" in d["headline"]
    assert next(s for s in d["lifecycle"] if s["key"] == "council")["state"] == "DONE"
    raw = sig("mt5", "PB-SELL--95597200", status="rejected")
    d = transparency.signal_detail(normalize.signal_ref(raw, 12.0, NOW), raw, [], 12.0)
    assert "brain" not in d["headline"].lower() and "MT5 EA sensor" in d["headline"]


def test_chart_levels_name_the_sender_of_the_signal_they_come_from():
    r = normalize.signal_ref(sig("mt5", "PB-SELL--95597200"), 12.0, NOW)
    lv = normalize._signal_levels(r, False)
    assert lv and all(x.sender == "MT5 EA sensor" for x in lv)
    # `origin` keeps its exact form: the box's acceptance run reads the signal id out of it and compares it by exact match.
    # 2.14.0 put the sender's name INSIDE origin; on the box that failed 13 instruments ("signal … · NRTR EA exists in engine")
    # and silently switched off the check "expired plan is not drawn as a current level". A new fact gets a new field.
    assert all(x.origin == "signal PB-SELL--95597200" for x in lv)


def test_the_signals_route_carries_the_sender_and_its_rule(client):
    d = client.get("/api/terminal/signals?bucket=all").json()
    assert "signal-sender-v1" in d["sender_rule"] and d["rows"]
    for r in d["rows"]:
        assert r["sender"]["system"] == r["system"] and (r["sender"]["brain"] is True) == (r["system"] == "v18")


# ---------------------------------------------------------------- sender cards on the Performance tab
def test_the_performance_route_hands_over_signalmeshs_cards_untouched(client):
    d = client.get("/api/terminal/performance").json()
    s = d["senders"]
    raw = routes.provider().sources_senders()
    assert s["state"] == "OK" and s["rule"] == "signal-senders-v1" and "sender-cards-v1" in s["terminal_rule"]
    assert s["cards"] == raw["cards"]                                             # every number and word is the platform's
    assert "pooled" not in str(s["cards"]).lower()
    line = s["cards"][0]["tables"][0]["rows"][0]
    assert {"label", "sent", "n", "wins", "losses", "win_rate", "ci", "avg_rr", "planned_be", "evidence", "reading"} <= set(line)


def test_not_built_not_loaded_fault_and_not_read_are_four_named_states(client, monkeypatch):
    p = routes.provider()
    real = p.sources_senders

    def state_of(fn):
        routes.cache().clear()
        monkeypatch.setattr(p, "sources_senders", fn)
        return client.get("/api/terminal/performance").json()["senders"]

    def missing():
        raise ProviderError("SignalMesh answered 404 for /api/v1/sources/senders: Not Found", state="ERROR", status=404)

    def down():
        raise ProviderError("SignalMesh unreachable: ReadTimeout: timed out", state="DOWN")
    s = state_of(missing)
    assert s["state"] == "NOT_BUILT" and s["cards"] == [] and "5.233" in s["note"]
    s = state_of(down)
    assert s["state"] == "NOT_READ" and s["cards"] == [] and "ReadTimeout" in s["note"]
    s = state_of(lambda: {**real(), "loaded": False})
    assert s["state"] == "NOT_LOADED" and s["cards"] == [] and "STILL BEING COUNTED" in s["note"] and "no sender has posted" in s["note"]
    s = state_of(lambda: {**real(), "fault": "OperationalError: signals could not be read"})
    assert s["state"] == "FAULT" and s["cards"] == [] and "OperationalError" in s["note"]
    for st in ("NOT_BUILT", "NOT_READ", "NOT_LOADED", "FAULT"):
        assert st.replace("_", " ") in routes.SENDER_CARDS_RULE.replace("_", " ")
