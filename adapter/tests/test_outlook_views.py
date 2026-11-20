"""outlook-views-v1 — Market Outlook, the system's own calls and the Turning Point record (platform 5.210), RESHAPED ONLY.
Every word, level, state, count, rate and verdict on the terminal equals the platform's; the terminal adds only `decimals`.
A route the platform does not have is NOT BUILT; UNKNOWN and a SERIES FAULT are answers, never a direction."""
import copy
import inspect
import re
from pathlib import Path

import pytest

from signalmesh_terminal import outlook as ov
from signalmesh_terminal import routes
from signalmesh_terminal.normalize import decimals_for
from signalmesh_terminal.providers.base import ProviderError
from signalmesh_terminal.providers.fixture import FixtureProvider

SRC = Path(__file__).resolve().parent.parent / "signalmesh_terminal"


def _fx():
    return FixtureProvider()


def _strip(d, extra=("decimals",)):
    """A terminal dict without the one thing the terminal adds."""
    return {k: v for k, v in d.items() if k not in extra}


# ---------------------------------------------------------------- Market Outlook
@pytest.mark.parametrize("sym,state", [("GOLD", "DOWN"), ("SILVER", "UP"), ("BTC", "NO CLEAR TREND"), ("US100", "UNKNOWN"), ("AAPL", "UNKNOWN")])
def test_outlook_carries_the_platforms_reading_untouched(sym, state):
    raw = _fx().market_outlook(sym)
    out = ov.market_outlook(copy.deepcopy(raw), sym, decimals_for)
    assert out["state"] == "OK" and out["read"]["state"] == state == raw["read"]["state"]
    assert out["rule"] == raw["rule"] == "market-scenarios-v1" and out["plain"] == raw["plain"] and out["authority"] == raw["authority"]
    assert out["as_of"] == raw["as_of"] and out["symbol"] == sym
    assert out["read"] == {k: raw["read"][k] for k in ov._READ_KEYS if k in raw["read"]}          # every shown key, every value
    for k in ("heading", "interesting", "wrong", "above", "below", "close", "atr", "bar_day", "bar_age_days", "reason", "series_fault", "structure"):
        assert out["read"][k] == raw["read"][k], k
    assert [_strip(x) for x in out["overview"]] == [{k: x[k] for k in ov._OVERVIEW_KEYS if k in x} for x in raw["overview"]]
    assert out["track"] == {k: raw["track"][k] for k in ov._TRACK_KEYS if k in raw["track"]}
    assert out["decimals"] == decimals_for(sym, raw["read"]["close"])
    assert all(x["decimals"] == decimals_for(x["symbol"], x["close"]) for x in out["overview"])


def test_three_questions_are_the_platforms_words_for_a_down_and_an_up_reading():
    g = ov.market_outlook(_fx().market_outlook("GOLD"), "GOLD", decimals_for)["read"]
    assert g["heading"]["word"] == "DOWN so far" and g["wrong"]["side"] == "above" and [i["kind"] for i in g["interesting"]] == ["WITH THE TREND", "CONTINUATION"]
    s = ov.market_outlook(_fx().market_outlook("SILVER"), "SILVER", decimals_for)["read"]
    assert s["heading"]["word"] == "UP so far" and s["wrong"]["side"] == "below"
    # "has been", never "will": the platform's words carry no future tense and the terminal adds none
    for r in (g, s):
        assert "so far" in r["heading"]["word"] and not re.search(r"\bwill\b", r["heading"]["why"])


def test_unknown_no_clear_trend_and_a_series_fault_are_answers_never_a_direction():
    b = ov.market_outlook(_fx().market_outlook("BTC"), "BTC", decimals_for)["read"]
    assert b["state"] == "NO CLEAR TREND" and b["wrong"] is None and b["heading"]["word"] == "NO CLEAR TREND"
    f = ov.market_outlook(_fx().market_outlook("US100"), "US100", decimals_for)["read"]
    assert f["state"] == "UNKNOWN" and "TWO daily bars" in f["series_fault"] and f["heading"] is None and f["wrong"] is None and f["above"] == []
    u = ov.market_outlook(_fx().market_outlook("ANT"), "ANT", decimals_for)["read"]
    assert u["state"] == "UNKNOWN" and u["series_fault"] == "" and "closed daily bars stored" in u["reason"] and u["heading"] is None


def test_the_track_record_is_carried_with_its_verdict_and_never_improved():
    raw = _fx().market_outlook("GOLD")
    t = ov.market_outlook(copy.deepcopy(raw), "GOLD", decimals_for)["track"]
    assert t["board"] == raw["track"]["board"] and t["here"] == raw["track"]["here"] and t["open"] == raw["track"]["open"]
    assert t["board"]["verdict"].startswith("UNPROVEN") and t["board"]["label"] == "UNPROVEN" and t["open"]["direction"] == "BEARISH"
    # a fault on the record is the platform's sentence, passed on
    raw["track"] = {"fault": "OperationalError: analyst_calls could not be read"}
    assert ov.market_outlook(raw, "GOLD", decimals_for)["track"] == {"fault": "OperationalError: analyst_calls could not be read"}


def test_an_absent_block_stays_absent():
    out = ov.market_outlook({"rule": "market-scenarios-v1", "symbol": "GOLD"}, "GOLD", decimals_for)
    assert out["state"] == "OK" and out["read"] is None and out["track"] is None and out["overview"] == [] and out["plain"] == ""
    assert ov.market_outlook(None, "GOLD", decimals_for)["read"] is None


# ---------------------------------------------------------------- Call Ledger
def test_ledger_rows_and_scoreboard_equal_the_platforms():
    raw = _fx().ledger_system()
    out = ov.system_ledger(copy.deepcopy(raw), decimals_for)
    assert out["state"] == "OK" and out["rule"] == "system-daily-call-v1" and out["scoring_rule"] == "analyst-ledger-v1" and out["analyst"] == "SignalMesh daily"
    assert out["board"] == raw["board"] and out["definition"] == raw["definition"] and out["plain"] == raw["plain"] and out["as_of"] == raw["as_of"]
    assert len(out["rows"]) == len(raw["rows"]) == 6
    for mine, theirs in zip(out["rows"], raw["rows"]):
        assert _strip(mine) == {k: theirs[k] for k in ov._LEDGER_ROW_KEYS if k in theirs}
        assert mine["decimals"] == decimals_for(theirs["symbol"], theirs["ref_price"])
    assert {r["outcome"] for r in out["rows"]} == {"PENDING", "TARGET HIT", "INVALIDATED", "EXPIRED", "BOTH IN ONE BAR"}
    # the order is the platform's (newest first); the terminal sorts nothing
    assert [r["id"] for r in out["rows"]] == [r["id"] for r in raw["rows"]]
    # under 20 finished calls the verdict is the platform's UNPROVEN sentence, whatever the counts are
    assert out["board"]["verdict"].startswith("UNPROVEN") and out["board"]["resolved"] == 4


# ---------------------------------------------------------------- Turning Point
def test_turning_point_record_equals_the_platforms_cell_by_cell():
    raw = _fx().turning_points()
    out = ov.turning_points(copy.deepcopy(raw), decimals_for)
    assert out["state"] == "OK" and out["rule"] == "turning-point-record-v1" and out["plain"] == raw["plain"]
    assert out["overall"] == raw["overall"] and out["gate"] == raw["gate"] and out["question"] == raw["question"] and out["words"] == raw["words"]
    assert out["overall"]["word"] == "NO ROBUST EDGE" and out["gate"]["open"] is False and out["gate"]["why"].startswith("NO FORECAST CARD")
    assert len(out["cells"]) == len(raw["cells"]) == 2
    for mine, theirs in zip(out["cells"], raw["cells"]):
        for k in ov._TP_CELL_KEYS:
            assert mine[k] == theirs[k], k
        for seg in ("search", "holdout"):
            assert mine[seg] == (None if theirs.get(seg) is None else {k: theirs[seg][k] for k in ov._TP_SEGMENT_KEYS if k in theirs[seg]})
    btc = next(c for c in out["cells"] if c["symbol"] == "BTC")
    assert btc["word"] == "CANDIDATE FAILED ITS HOLDOUT" and btc["holdout_state"].startswith("SPENT") and btc["held_words"] == []
    assert btc["search"]["example"] == {"as_of": "2020-03-05T00:00:00+00:00", "price": 100.0, "atr": 1.0, "down_at": 99.0, "up_at": 101.0}
    gold = next(c for c in out["cells"] if c["symbol"] == "GOLD")
    assert gold["word"] == "NO ROBUST EDGE" and gold["holdout"] is None and gold["holdout_state"] == "NOT SPENT"


def test_the_stored_rows_are_never_asked_for_and_never_carried():
    raw = _fx().turning_points()
    raw["cells"][0]["search"]["rows"] = [{"as_of": "2020-01-06T00:00:00+00:00", "p_down": 0.9, "p_up": 0.1, "word": "PROBABLE TOP", "outcome": "down"}]
    out = ov.turning_points(raw, decimals_for)
    assert "rows" not in out["cells"][0]["search"] and "p_down" not in str(out)
    assert "rows=1" not in (SRC / "providers" / "signalmesh.py").read_text()


# ---------------------------------------------------------------- the laws, by inspection
def test_the_terminal_calculates_none_of_it():
    """No level, state, hit rate, verdict or distance is derived here: the reshapers contain no arithmetic and name no
    state, outcome or verdict word of their own."""
    src = "".join(inspect.getsource(f) for f in (ov.market_outlook, ov.system_ledger, ov.turning_points, ov._only))
    code = "\n".join(line.split("#")[0] for line in src.split("\n") if not line.strip().startswith(('"""', "#")))
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    for word in ("UP", "DOWN", "NO CLEAR TREND", "UNKNOWN", "UNPROVEN", "TARGET HIT", "INVALIDATED", "NO ROBUST EDGE", "PROBABLE", " / ", " * ", " - ", " + ", "sum(", "len(", "round(", "sorted("):
        assert word not in code, word
    assert "outlook-views-v1" in ov.OUTLOOK_RULE and "calculates none of it" in ov.OUTLOOK_RULE and "not a forecast" in ov.OUTLOOK_RULE


def test_the_three_reads_are_get_only_and_reach_no_execution():
    sm = (SRC / "providers" / "signalmesh.py").read_text()
    for path in ov.ROUTES.values():
        assert f'self._get("{path}"' in sm
    # outlook.py imports nothing: it cannot reach a broker, a ticket, the journal, the recorder or the network
    src = (SRC / "outlook.py").read_text()
    assert [l for l in src.splitlines() if l.startswith(("import ", "from "))] == ["from __future__ import annotations"]
    # nothing else in the adapter reads these views: only routes.py imports the module ...
    for p in SRC.rglob("*.py"):
        if p.name not in ("outlook.py", "routes.py"):
            assert "outlook as ov" not in p.read_text() and "from .outlook" not in p.read_text() and "from . import outlook" not in p.read_text(), p
    # ... and inside routes.py neither the decision panel, the order ticket nor the journal touches them
    for fn in (routes.decision, routes.execution_ticket, routes.execution_place, routes.journal_view, routes.market_watch):
        code = inspect.getsource(fn)
        assert "ov." not in code and "_outlook_view" not in code and "market_outlook" not in code, fn.__name__


# ---------------------------------------------------------------- the routes
def test_routes_hand_out_the_three_views_and_refuse_writes(client):
    o = client.get("/api/terminal/outlook?symbol=GOLD").json()
    assert o["state"] == "OK" and o["read"]["state"] == "DOWN" and o["decimals"] == 2 and o["read_at"] and o["is_fixture"] is True
    assert o["plain"].startswith("Three questions") and o["terminal_rule"] == ov.OUTLOOK_RULE
    assert client.get("/api/terminal/outlook?symbol=us100").json()["read"]["series_fault"]            # the symbol is upper-cased; a fault is a 200
    led = client.get("/api/terminal/call-ledger").json()
    assert led["state"] == "OK" and led["board"]["verdict"].startswith("UNPROVEN") and len(led["rows"]) == 6
    tp = client.get("/api/terminal/turning-points").json()
    assert tp["state"] == "OK" and tp["overall"]["word"] == "NO ROBUST EDGE" and len(tp["cells"]) == 2
    for path in ("/api/terminal/outlook?symbol=GOLD", "/api/terminal/call-ledger", "/api/terminal/turning-points"):
        for verb in (client.post, client.put, client.delete, client.patch):
            assert verb(path).status_code == 405
    assert client.get("/api/terminal/execution/modes").json()["can_place"] is False


def test_a_platform_without_the_route_reads_not_built_never_an_empty_panel(client, monkeypatch):
    def gone(*a, **k):
        raise ProviderError("SignalMesh answered 404 for the route: Not Found", state="ERROR", status=404)
    p = routes.provider()
    for name in ("market_outlook", "ledger_system", "turning_points"):
        monkeypatch.setattr(p, name, gone)
    routes.cache().clear()
    for path, route in (("/api/terminal/outlook?symbol=GOLD", "/api/v1/market/outlook"), ("/api/terminal/call-ledger", "/api/v1/ledger/system"),
                        ("/api/terminal/turning-points", "/api/v1/turning-points")):
        r = client.get(path)
        d = r.json()
        assert r.status_code == 200 and d["state"] == "NOT_BUILT" and d["note"].startswith("NOT BUILT") and route in d["note"] and d["route"] == route
        assert "read" not in d and "rows" not in d and "cells" not in d and "board" not in d          # nothing is shown in its place
    routes.cache().clear()


def test_an_unreachable_platform_is_an_error_not_not_built(client, monkeypatch):
    def down(*a, **k):
        raise ProviderError("SignalMesh unreachable: ConnectError", state="DOWN")
    def refused(*a, **k):
        raise ProviderError("SignalMesh answered 500 for /api/v1/ledger/system: boom", state="ERROR", status=500)
    p = routes.provider()
    monkeypatch.setattr(p, "market_outlook", down)
    monkeypatch.setattr(p, "ledger_system", refused)
    routes.cache().clear()
    r = client.get("/api/terminal/outlook?symbol=GOLD")
    assert r.status_code == 503 and r.json()["detail"]["state"] == "DOWN"
    r = client.get("/api/terminal/call-ledger")
    assert r.status_code == 502 and "500" in r.json()["detail"]["error"]
    routes.cache().clear()


def test_outlook_views_have_their_own_cache_keys(client):
    """Two readers with different lifetimes never share a cache key (the 2.8.1 law)."""
    routes.cache().clear()
    client.get("/api/terminal/outlook?symbol=GOLD"), client.get("/api/terminal/call-ledger"), client.get("/api/terminal/turning-points")
    keys = set(routes.cache()._store)
    assert {"outlook:GOLD", "call-ledger", "turning-points"} <= keys
    assert not ({"snapshot:GOLD", "desk:GOLD"} & keys)
