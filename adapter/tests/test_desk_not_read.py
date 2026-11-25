"""2.13.3 — a desk that was NOT READ is not a desk that found nothing.

Asked by the platform window on 2026-11-24: what does the screen show when GET /api/v1/market/desk times out? Until this
release the answer was a sentence about the MARKET made from silence — "no actionable structure → NO SETUP" under the
chart, "NO SETUP" in Validation, "the desk returned no lanes" in the Desk lanes box. A read that failed says nothing
about the market, and now the answer says exactly that. The snapshot's own verdict, levels and sides are untouched.
"""
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from signalmesh_terminal import normalize
from signalmesh_terminal.providers.base import ProviderError
from signalmesh_terminal.providers.signalmesh import SignalMeshProvider


def test_a_desk_that_was_not_read_makes_no_sentence_about_the_market():
    ls = normalize.lane_state(None)
    assert ls.decision == "UNKNOWN" and ls.stage == "NOT AVAILABLE" and ls.confirmation_status == "UNKNOWN"
    assert "could not be read" in ls.confirmation_text
    assert "no actionable structure" not in ls.confirmation_text and ls.stage != "NO SETUP"
    assert ls.entry is None and ls.reasons == []


def test_a_desk_that_answered_keeps_the_platforms_own_words():
    desk = {"desk": {"lanes": [{"label": "🟩 Intraday", "c": {"engine": "auto-v1", "decision": "WAIT", "reasons": ["STRUCTURE_MIXED"]}}]}}
    ls = normalize.lane_state(desk)
    assert ls.stage == "NO SETUP" and "mixed structure builds nothing" in ls.confirmation_text
    assert normalize.desk_read(desk).state == "OK" and normalize.desk_read(desk).note == ""


def test_the_decision_route_carries_not_read_with_the_reads_own_words(client, monkeypatch, caplog):
    from signalmesh_terminal import routes

    ok = client.get("/api/terminal/decision?symbol=GOLD").json()
    assert ok["desk_read"]["state"] == "OK" and ok["lanes"] and ok["lane"]["stage"] != "NOT AVAILABLE"

    def timed_out(symbol):
        raise ProviderError("SignalMesh unreachable: ReadTimeout: The read operation timed out", state="DOWN")
    routes.cache().clear()
    monkeypatch.setattr(routes.provider(), "desk", timed_out)
    d = client.get("/api/terminal/decision?symbol=GOLD")
    assert d.status_code == 200                      # the snapshot's verdict is still shown; only the desk is missing
    # the failed read leaves one line in the box's log, with the symbol, the wait and the read's own word — and no key
    lines = [r.getMessage() for r in caplog.records if "desk NOT READ" in r.getMessage()]
    assert len(lines) == 1 and "GOLD" in lines[0] and "DOWN" in lines[0] and "ReadTimeout" in lines[0] and "bb_" not in lines[0]
    d = d.json()
    assert d["desk_read"]["state"] == "NOT_READ" and d["desk_read"]["provider_state"] == "DOWN"
    assert "ReadTimeout" in d["desk_read"]["error"] and d["desk_read"]["timeout_s"] == 20.0
    assert d["lane"]["stage"] == "NOT AVAILABLE" and d["lane"]["decision"] == "UNKNOWN"
    assert d["lanes"] == [] and d["verdict_board"]["state"] == "NOT_AVAILABLE" and d["price"]["drift"] == {}
    blob = str(d["lane"]) + d["desk_read"]["note"]
    assert "NO SETUP" not in blob and "no actionable structure" not in blob
    # what the snapshot said is exactly what it said with the desk read
    for k in ("summary", "engine_status", "entry", "sl", "tp1", "bias", "structure", "levels", "invalidation"):
        assert d[k] == ok[k], k
    assert {s: v["state"] for s, v in d["sides"].items()} == {s: v["state"] for s, v in ok["sides"].items()}


def test_a_failed_desk_read_is_not_remembered_as_an_answer(client, monkeypatch):
    """The next refresh asks again, and the first answer that arrives replaces NOT READ."""
    from signalmesh_terminal import routes

    real = routes.provider().desk
    calls = []

    def flaky(symbol):
        calls.append(symbol)
        if len(calls) == 1:
            raise ProviderError("SignalMesh unreachable: ReadTimeout: timed out", state="DOWN")
        return real(symbol)
    routes.cache().clear()
    monkeypatch.setattr(routes.provider(), "desk", flaky)
    assert client.get("/api/terminal/decision?symbol=GOLD").json()["desk_read"]["state"] == "NOT_READ"
    again = client.get("/api/terminal/decision?symbol=GOLD").json()
    assert calls == ["GOLD", "GOLD"] and again["desk_read"]["state"] == "OK" and again["lanes"]


class _Slow(BaseHTTPRequestHandler):
    def do_GET(self):                                # noqa: N802
        time.sleep(1.0)
        try:
            self.send_response(200); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(b"{}")
        except OSError:
            pass                                     # the reader has gone — that is the point of the test

    def log_message(self, *a):                       # quiet
        pass


def test_a_platform_answer_slower_than_the_timeout_is_down_and_says_read_timeout():
    """What the read itself reports when the platform takes longer than SMT_SIGNALMESH_TIMEOUT_S: measured, not assumed."""
    srv = HTTPServer(("127.0.0.1", 0), _Slow)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        p = SignalMeshProvider(f"http://127.0.0.1:{srv.server_port}", "bb_testkey", timeout_s=0.2)
        t0 = time.monotonic()
        with pytest.raises(ProviderError) as e:
            p.desk("GOLD")
        waited = time.monotonic() - t0
        assert e.value.state == "DOWN" and "ReadTimeout" in str(e.value)
        assert 0.15 < waited < 0.9, waited           # it gave up at its own timeout, not at the server's pace
    finally:
        srv.shutdown(); srv.server_close()
