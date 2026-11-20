"""desk-evidence-v1 — the platform's lane history, evidence verdicts, break word and verdict board (5.202 / 5.203), whether its
history cells are loaded (5.206) and the lane-history rule name it sends (v2 since 5.211), RESHAPED ONLY. Every number and word
on the terminal equals the platform's; an absent key is NOT AVAILABLE."""
import copy
import inspect

from signalmesh_terminal import normalize
from signalmesh_terminal.providers.fixture import FixtureProvider


def _desk(sym="GOLD"):
    return FixtureProvider().desk(sym)


def test_lane_cards_carry_the_platforms_own_values_untouched():
    raw = _desk()
    cards = {c.label: c for c in normalize.lane_cards(raw)}
    for lane in raw["desk"]["lanes"]:
        card, c = cards[lane["label"]], lane["c"]
        assert card.decision == c["decision"] and card.structure == c.get("structure")
        measured = next((k for k in lane["validity"]["checks"] if k.get("label") == "Measured history"), {})
        if lane.get("own_history"):
            assert card.own_history == lane["own_history"]                       # every key, every value
            assert card.verdict_v1 == measured["verdict"] and card.verdict_v2 == measured["verdict_v2"]
            assert card.measured_detail == measured["detail"] and card.measured_population == measured["population"]
        else:
            assert card.own_history is None and card.verdict_v1 is None and card.verdict_v2 is None
        assert card.lab_history_applies == lane["history"]["applies_to_lane"]
        if c.get("stale_context"):
            assert card.stale_context == c["stale_context"]
        else:
            assert card.stale_context is None


def test_a_stale_lane_keeps_its_wait_and_gains_only_a_word():
    raw = _desk()
    stale = next(c for c in normalize.lane_cards(raw) if c.stale_context)
    assert stale.decision == "WAIT" and "DATA_STALE" in stale.reasons and stale.entry is None
    assert stale.stale_context["word"] == "SCHEDULED BREAK" and stale.stale_context["rule"] == "stale-context-v1"
    # without the key there is no word at all: nothing is inferred from the reason
    bare = copy.deepcopy(raw)
    for lane in bare["desk"]["lanes"]:
        lane["c"].pop("stale_context", None)
    assert all(c.stale_context is None for c in normalize.lane_cards(bare))


def test_the_comparison_labs_history_is_never_carried_as_the_lanes_own():
    raw = _desk()
    for lane in raw["desk"]["lanes"]:
        lane["history"].update(n=999, expectancy=9.99)           # a number that must not appear anywhere on the card
        lane["own_history"] = None
    for card in normalize.lane_cards(raw):
        assert card.own_history is None and "999" not in card.model_dump_json() and "9.99" not in card.model_dump_json()


def test_a_platform_before_5202_gives_plain_lanes():
    raw = _desk()
    for lane in raw["desk"]["lanes"]:
        lane.pop("own_history", None)
        lane["c"].pop("stale_context", None)
        lane["history"] = {"n": 5}
        lane["validity"]["checks"] = [k for k in lane["validity"]["checks"] if k.get("label") != "Measured history"]
    for card in normalize.lane_cards(raw):
        assert (card.own_history, card.stale_context, card.verdict_v1, card.verdict_v2, card.lab_history_applies) == (None, None, None, None, None)


def test_verdict_board_equals_the_platforms_cell_by_cell():
    raw = _desk("GOLD")
    vb = normalize.verdict_board(raw, "GOLD")
    src = raw["verdict_board"]
    assert vb.state == "OK" and vb.rule == "verdict-board-v1" and len(vb.rows) == 8 == len(src["rows"])
    for mine, theirs in zip(vb.rows, src["rows"]):
        for k in normalize._BOARD_ROW_KEYS:
            assert getattr(mine, k) == theirs[k] or (theirs[k] is None and getattr(mine, k) in (None, "", False)), k
        assert mine.v1 == theirs["v1"] and mine.v2 == theirs["v2"]
    assert vb.summary == src["summary"] and vb.rules == src["rules"] and vb.is_not == src["not"] and vb.authority == src["authority"]
    assert sum(1 for r in vb.rows if r.current) == 1 and next(r for r in vb.rows if r.current).engine == "session-v1"
    assert any(r.backed_off for r in vb.rows) and {r.change for r in vb.rows} >= {"SAME WORD", "TICK WITHDRAWN", "CROSS WITHDRAWN", "UNDER THE FLOOR"}
    # the platform page's CSS class names are not data and are not carried
    assert "text-emerald" not in vb.model_dump_json() and "_class" not in vb.model_dump_json()
    # the live-setup row is the lane's own cell
    cur = next(r for r in vb.rows if r.current)
    lane = next(c for c in normalize.lane_cards(raw) if c.engine == cur.engine)
    assert lane.own_history["n"] == cur.n and lane.verdict_v2 == cur.v2 and lane.verdict_v1 == cur.v1


def test_fault_absent_key_and_unreadable_desk_are_three_named_states():
    f = normalize.verdict_board(_desk("SILVER"), "SILVER")
    assert f.state == "FAULT" and "lane_observations" in f.fault and f.rows == []
    a = normalize.verdict_board(_desk("BTC"), "BTC")
    assert a.state == "NOT_AVAILABLE" and "NOT AVAILABLE on this platform build" in a.note and a.rows == [] and a.summary is None
    n = normalize.verdict_board(None, "GOLD")
    assert n.state == "NOT_AVAILABLE" and "could not be read" in n.note


def test_the_terminal_computes_none_of_it():
    """No interval, verdict, expectancy or break word is derived here: the reshapers contain no arithmetic and
    name no verdict or break word of their own."""
    src = inspect.getsource(normalize.lane_cards) + inspect.getsource(normalize.verdict_board) + inspect.getsource(normalize._only)
    code = "\n".join(line.split("#")[0] for line in src.split("\n") if not line.strip().startswith(('"""', "#")))
    for word in ("POSITIVE", "NEGATIVE", "CANNOT SEPARATE", "SCHEDULED BREAK", "NOT A BREAK", "WITHDRAWN", "sqrt", "mean(", " ** ", "1.645"):
        assert word not in code, word
    assert "desk-evidence-v1" in normalize.DESK_EVIDENCE_RULE and "computes no interval" in normalize.DESK_EVIDENCE_RULE


def test_decision_route_hands_it_out_and_stays_read_only(client):
    d = client.get("/api/terminal/decision?symbol=GOLD").json()
    assert d["verdict_board"]["state"] == "OK" and d["verdict_board"]["paper"] is True and len(d["verdict_board"]["rows"]) == 8
    assert any(l["stale_context"] for l in d["lanes"]) and any(l["own_history"] for l in d["lanes"])
    assert client.get("/api/terminal/decision?symbol=SILVER").json()["verdict_board"]["state"] == "FAULT"
    assert client.get("/api/terminal/decision?symbol=BTC").json()["verdict_board"]["state"] == "NOT_AVAILABLE"
    assert client.post("/api/terminal/decision?symbol=GOLD").status_code == 405
    assert client.get("/api/terminal/execution/modes").json()["can_place"] is False


# ---------------------------------------------------------------- platform 5.206 and 5.211
def test_not_loaded_yet_is_carried_as_the_platforms_state_never_as_no_history():
    """The minute after a platform restart: every cell COMPUTING, the board not ready. The terminal copies the state, the
    platform's sentence and the note; it draws no verdict from an unloaded cell and invents no n."""
    raw = _desk("ETH")
    card = next(c for c in normalize.lane_cards(raw) if c.own_history)
    src = next(l for l in raw["desk"]["lanes"] if l.get("own_history"))["own_history"]
    assert card.own_history == src and card.own_history["state"] == "COMPUTING" and card.own_history["cells_age_s"] is None
    assert "history cells COMPUTING" in card.own_history["level"] and card.verdict_v2 is None and "NOT LOADED YET" in card.measured_detail
    vb = normalize.verdict_board(raw, "ETH")
    assert vb.state == "OK" and vb.cells_ready is False and vb.cells_note == raw["verdict_board"]["cells_note"] and vb.cells_note.startswith("HISTORY CELLS NOT LOADED YET")
    assert len(vb.rows) == 8 and all(r.cells_state == "COMPUTING" and r.cells_age_s is None for r in vb.rows)


def test_loaded_cells_carry_their_state_and_age_untouched():
    raw = _desk("GOLD")
    vb = normalize.verdict_board(raw, "GOLD")
    assert vb.cells_ready is True and vb.cells_note == raw["verdict_board"]["cells_note"]
    for mine, theirs in zip(vb.rows, raw["verdict_board"]["rows"]):
        assert (mine.cells_state, mine.cells_age_s) == (theirs["cells_state"], theirs["cells_age_s"]) == ("FRESH", 240)
    card = next(c for c in normalize.lane_cards(raw) if c.own_history)
    assert (card.own_history["state"], card.own_history["cells_age_s"]) == ("FRESH", 240)


def test_a_platform_before_5206_sends_no_cell_state_and_none_is_invented():
    raw = _desk("GOLD")
    for k in ("cells_ready", "cells_note"):
        raw["verdict_board"].pop(k)
    for r in raw["verdict_board"]["rows"]:
        r.pop("cells_state"), r.pop("cells_age_s")
    for lane in raw["desk"]["lanes"]:
        if lane.get("own_history"):
            lane["own_history"].pop("state"), lane["own_history"].pop("cells_age_s")
    vb = normalize.verdict_board(raw, "GOLD")
    assert vb.state == "OK" and vb.cells_ready is None and vb.cells_note == "" and all(r.cells_state is None and r.cells_age_s is None for r in vb.rows)
    card = next(c for c in normalize.lane_cards(raw) if c.own_history)
    assert "state" not in card.own_history and "cells_age_s" not in card.own_history


def test_the_lane_history_rule_name_is_the_platforms_whichever_it_sends():
    """lane-history-v1 until platform 5.210, v2 from 5.211. The terminal prints the payload's string and names neither itself."""
    assert next(c for c in normalize.lane_cards(_desk("GOLD")) if c.own_history).own_history["rule"] == "lane-history-v2"
    assert next(c for c in normalize.lane_cards(_desk("BTC")) if c.own_history).own_history["rule"] == "lane-history-v1"
    assert normalize.verdict_board(_desk("GOLD"), "GOLD").rules["cell"].startswith("lane-history-v2")
    src = inspect.getsource(normalize)
    assert "lane-history-v1" not in src and "lane-history-v2" not in src


def test_a_single_stocks_small_cell_is_its_own_and_says_why():
    """lane-history-v2: NVDA, AAPL and ANT are never pooled with other assets. backed_off is false and `level` carries the reason."""
    for sym in ("NVDA", "AAPL", "ANT"):
        raw = _desk(sym)
        card = next(c for c in normalize.lane_cards(raw) if c.own_history)
        h = card.own_history
        assert h["backed_off"] is False and h["n"] == h["symbol_n"] == 3 and h["symbol"] == sym
        assert h["level"].endswith("a single stock is never pooled with other assets") and "all symbols" not in h["level"]
        vb = normalize.verdict_board(raw, sym)
        assert vb.state == "OK" and not any(r.backed_off for r in vb.rows) and vb.summary["backed_off"] == 0


def test_decision_route_hands_out_the_cell_state(client):
    d = client.get("/api/terminal/decision?symbol=ETH").json()
    assert d["verdict_board"]["cells_ready"] is False and "NOT LOADED YET" in d["verdict_board"]["cells_note"]
    assert {r["cells_state"] for r in d["verdict_board"]["rows"]} == {"COMPUTING"}
    assert next(l for l in d["lanes"] if l["own_history"])["own_history"]["state"] == "COMPUTING"
    g = client.get("/api/terminal/decision?symbol=GOLD").json()
    assert g["verdict_board"]["cells_ready"] is True and g["verdict_board"]["rows"][0]["cells_state"] == "FRESH"
