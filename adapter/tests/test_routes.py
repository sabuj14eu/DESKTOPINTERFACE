import pytest


def test_health_flags_fixture(client):
    h = client.get("/api/terminal/health").json()
    assert h["provider"]["is_fixture"] is True
    assert h["execution"]["can_place"] is False and h["execution"]["enabled"] is False
    assert {m["mode"] for m in h["execution"]["modes"]} == {"MANUAL", "MT5", "CTRADER"}


@pytest.mark.parametrize("path", [
    "/api/terminal/instruments", "/api/terminal/market-watch", "/api/terminal/candles?symbol=GOLD&tf=15m&n=50",
    "/api/terminal/decision?symbol=GOLD", "/api/terminal/signals?bucket=active", "/api/terminal/signals?bucket=history",
    "/api/terminal/trades?status=closed", "/api/terminal/performance", "/api/terminal/news?symbol=GOLD",
    "/api/terminal/sources", "/api/terminal/system", "/api/terminal/execution/modes", "/api/terminal/coverage?symbol=GOLD"])
def test_every_read_route_answers(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"


def test_bad_timeframe_is_named(client):
    r = client.get("/api/terminal/candles?symbol=GOLD&tf=2h")
    assert r.status_code == 400 and "tf must be" in r.text


def test_place_is_always_403(client):
    for mode in ("MANUAL", "MT5", "CTRADER"):
        r = client.post("/api/terminal/execution/place", json={"symbol": "GOLD", "mode": mode, "approval": "I approve"})
        assert r.status_code == 403, mode
        assert "DISABLED" in r.text


def test_manual_ticket_only_when_ready(client):
    r = client.post("/api/terminal/execution/ticket", json={"symbol": "GOLD", "mode": "MANUAL"})
    assert r.status_code == 200
    body = r.json()
    assert body["sent_to_broker"] is False and body["available"] is False and "WAIT" in body["note"]


def test_token_gate(monkeypatch):
    monkeypatch.setenv("SMT_PROVIDER", "fixture")
    monkeypatch.setenv("SMT_ENV", "test")
    monkeypatch.setenv("SMT_ACCESS_TOKEN", "s3cret")
    monkeypatch.setenv("SMT_AUTH", "token")
    from signalmesh_terminal import routes
    routes.reset_for_tests()
    from fastapi.testclient import TestClient
    from signalmesh_terminal.main import create_app
    c = TestClient(create_app())
    assert c.get("/api/terminal/health").status_code == 200          # health is open
    assert c.get("/api/terminal/market-watch").status_code == 401
    assert c.get("/api/terminal/market-watch", headers={"X-Terminal-Token": "wrong"}).status_code == 401
    assert c.get("/api/terminal/market-watch", headers={"X-Terminal-Token": "s3cret"}).status_code == 200
    routes.reset_for_tests()


def test_fixture_refused_in_production(monkeypatch):
    monkeypatch.setenv("SMT_PROVIDER", "fixture")
    monkeypatch.setenv("SMT_ENV", "production")
    from signalmesh_terminal import routes
    routes.reset_for_tests()
    from signalmesh_terminal.main import create_app
    with pytest.raises(RuntimeError):
        create_app()
    routes.reset_for_tests()


def test_sources_verdict_names_non_broker_data(client):
    s = client.get("/api/terminal/sources").json()
    assert s["verdict"].startswith("NOT ALL BROKER DATA") and "fixture" in s["verdict"]
    assert all(f.get("source_kind") for f in s["feeds"] if f.get("source"))


def test_decision_has_price_contract_and_sides(client):
    d = client.get("/api/terminal/decision?symbol=GOLD").json()
    assert d["price"]["rule"] == "price-contract-v1" and d["price"]["tick"]["state"] == "UNAVAILABLE"
    assert set(d["sides"]) == {"BUY", "SELL"} and d["side_rule"]
    assert d["levels"] == [] and d["expired_plan"]["signal"]["stale"] is True


def test_signalmesh_login_gate(monkeypatch):
    """auth=signalmesh: no bb_session -> 401 with the login url; a live session (SignalMesh
    answers 200 JSON to the probe) -> allowed; the read key in X-Terminal-Key -> allowed."""
    monkeypatch.setenv("SMT_PROVIDER", "fixture")
    monkeypatch.setenv("SMT_ENV", "test")
    monkeypatch.setenv("SMT_AUTH", "signalmesh")
    monkeypatch.setenv("SMT_SIGNALMESH_API_KEY", "bb_readkey")
    from signalmesh_terminal import auth, routes
    routes.reset_for_tests(); auth.reset_for_tests()

    class FakeResp:
        def __init__(self, code, ctype="application/json"):
            self.status_code, self.headers = code, {"content-type": ctype}

    class FakeClient:
        def get(self, url, params=None, cookies=None, headers=None):
            assert url.endswith("/chart/levels.json")
            return FakeResp(200) if cookies.get("bb_session") == "good" else FakeResp(302, "text/html")
    monkeypatch.setattr(auth, "_c", lambda: FakeClient())
    from fastapi.testclient import TestClient
    from signalmesh_terminal.main import create_app
    c = TestClient(create_app())
    r = c.get("/api/terminal/market-watch")
    assert r.status_code == 401 and r.json()["auth"] == "signalmesh" and r.json()["login_url"].startswith("/login")
    assert c.get("/api/terminal/market-watch", cookies={"bb_session": "bad"}).status_code == 401
    assert c.get("/api/terminal/market-watch", cookies={"bb_session": "good"}).status_code == 200
    assert c.get("/api/terminal/market-watch", headers={"X-Terminal-Key": "bb_readkey"}).status_code == 200
    assert c.get("/api/terminal/market-watch", headers={"X-Terminal-Key": "wrong"}).status_code == 401
    assert c.get("/api/terminal/health").status_code == 200   # health stays open
    assert c.get("/api/terminal/health").json()["adapter"]["auth"] == "signalmesh"
    routes.reset_for_tests(); auth.reset_for_tests()


def test_coverage_lists_every_timeframe(client):
    c = client.get("/api/terminal/coverage?symbol=GOLD").json()
    assert [r["tf"] for r in c["timeframes"]] == ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    assert all("stored" in r for r in c["timeframes"])


def test_instruments_are_discovered_not_configured(client):
    d = client.get("/api/terminal/instruments").json()
    syms = {i["symbol"]: i for i in d["instruments"]}
    # DEFAULT_SYMBOLS rows (fixture news_state) + symbols seen in signals
    assert {"GOLD", "SILVER", "BTC", "US100", "EURUSD"} <= set(syms)
    assert syms["GOLD"]["available"] and syms["GOLD"]["timeframes"] == ["1m", "15m", "1h", "1d"]
    assert syms["BTC"]["timeframes"] == ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    assert syms["US100"]["available"] is False and syms["US100"]["timeframes"] == []   # signals only, no candles
    assert syms["GOLD"]["category"] == "metals" and syms["BTC"]["category"] == "crypto" and syms["EURUSD"]["category"] == "forex"
    assert "DEFAULT_SYMBOLS (news/state)" in syms["GOLD"]["origins"] and "signals" in syms["US100"]["origins"]
    assert d["watch"] == ["GOLD", "SILVER", "BTC"]      # only instruments with data, no pins configured
    assert "news/state" in d["source"] and "nothing invented" in d["source"]


def test_market_watch_lists_every_available_instrument(client):
    mw = client.get("/api/terminal/market-watch").json()
    assert [r["symbol"] for r in mw["rows"]] == ["GOLD", "SILVER", "BTC"]
    assert all(r["category"] for r in mw["rows"])


def test_pins_restrict_but_never_add(monkeypatch):
    monkeypatch.setenv("SMT_PROVIDER", "fixture"); monkeypatch.setenv("SMT_ENV", "test"); monkeypatch.setenv("SMT_AUTH", "open")
    monkeypatch.setenv("SMT_SYMBOLS", "BTC,US100,FAKE")
    from signalmesh_terminal import routes
    routes.reset_for_tests()
    from fastapi.testclient import TestClient
    from signalmesh_terminal.main import create_app
    c = TestClient(create_app())
    assert c.get("/api/terminal/instruments").json()["watch"] == ["BTC"]   # US100 has no candles, FAKE is not SignalMesh's
    routes.reset_for_tests()
