"""Terminal V2: broker accounts are never mixed or invented; a signal is never called an
execution without a broker row that names it; execution adapters translate but never send."""
from signalmesh_terminal import accounts as acct
from signalmesh_terminal.normalize import signal_ref
from signalmesh_terminal.providers.base import ProviderError
from signalmesh_terminal.transparency import signal_detail


# ------------------------------------------------------------------ accounts
def test_accounts_lists_only_connected_and_masks_the_number(client):
    d = client.get("/api/terminal/accounts").json()
    assert d["mode"] == "PER_ACCOUNT"
    assert [(a["platform"], a["environment"]) for a in d["accounts"]] == [("MT5", "DEMO"), ("MT5", "LIVE")]
    assert [a["connection"] for a in d["disconnected"]] == ["OFFLINE"]
    blob = client.get("/api/terminal/accounts").text
    for full in ("52001234", "70445566", "52009999"):
        assert full not in blob
    assert d["accounts"][0]["login_masked"].endswith("1234") and d["accounts"][0]["login_masked"].startswith("•")
    assert not any(k.startswith("_") for k in d)


def test_account_values_are_the_brokers_and_missing_ones_stay_missing(client):
    d = client.get("/api/terminal/accounts").json()
    demo, live = d["accounts"]
    assert (demo["balance"], demo["equity"], demo["used_margin"], demo["margin_level"]) == (10000.0, 10240.0, 440.0, 2327.27)
    assert demo["field_sources"]["used_margin"].endswith("margin")
    # the live row sent no margin / margin_level: NOT derived from equity and free margin
    assert live["used_margin"] is None and live["margin_level"] is None and live["free_margin"] == 2500.0


def test_switching_accounts_never_mixes_rows(client):
    d = client.get("/api/terminal/accounts").json()
    demo, live = (client.get(f"/api/terminal/account?id={a['id']}").json() for a in d["accounts"])
    assert demo["account"]["balance"] == 10000.0 and live["account"]["balance"] == 2500.0
    assert [p["symbol"] for p in demo["positions"]] == ["GOLD"] and [o["symbol"] for o in demo["orders"]] == ["SILVER"]
    assert live["positions"] == [] and live["orders"] == []
    # the journal has no account field and there are 3 accounts: closed trades are not guessed onto either
    assert demo["closed"] == [] and live["closed"] == [] and "cannot be attributed" in demo["closed_source"]
    assert client.get("/api/terminal/account?id=nope").status_code == 404


class _NoRoute:
    def accounts(self, path):
        raise ProviderError("404", state="ERROR", status=404)


def test_fallback_single_account_is_that_account():
    d = acct.build(_NoRoute(), "/api/v1/accounts", {"balance": 10000.0, "equity": 10240.0, "free_margin": 9800.0, "floating_pnl": 240.0,
                                                    "accounts": 1, "online": 1}, ["52001234"])
    a = d["accounts"][0]
    assert d["mode"] == "PORTFOLIO_TOTAL" and "404" in d["note"]
    assert a.combined is False and a.balance == 10000.0 and a.login_masked.endswith("1234")
    # nothing the portfolio does not carry is filled in
    assert a.used_margin is None and a.margin_level is None and a.broker is None and a.server is None and a.environment == "UNKNOWN"
    rows, why = acct.journal_for(a, "52001234", d["_total"], [{"id": 1, "status": "open"}])
    assert len(rows) == 1 and "single account" in why


def test_fallback_total_of_several_accounts_is_labelled_combined():
    d = acct.build(_NoRoute(), "/api/v1/accounts", {"balance": 30000.0, "equity": 30100.0, "accounts": 3, "online": 2}, ["1", "2"])
    a = d["accounts"][0]
    assert a.combined is True and a.accounts_in_total == 3 and a.login_masked is None and "COMBINED TOTAL of 3" in a.notes[0]


def test_no_reporting_account_means_no_account():
    assert acct.build(_NoRoute(), "", {"accounts": 0, "online": 0}, [])["accounts"] == []
    d = acct.build(_NoRoute(), "", {"balance": 1.0, "accounts": 1, "online": 0}, [])
    assert d["accounts"] == [] and d["disconnected"][0].connection == "OFFLINE"


def test_demo_live_only_from_the_brokers_word():
    assert [acct.environment(v) for v in (0, "demo", 2, "real", "LIVE", None, "", "hedging", True)] == \
        ["DEMO", "DEMO", "LIVE", "LIVE", "LIVE", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"]


# ------------------------------------------------------------------ signal origin
RAW = {"signal_id": "SIG-1", "system": "v18", "symbol": "GOLD", "tf": "M15", "direction": "BUY", "entry": 100.0, "sl": 99.0,
       "tp1": 102.0, "tp2": 104.0, "rr": 2.0, "status": "approved", "confidence": 71.0, "council": {"approve": 6, "total": 6},
       "created_at": "2026-11-05T03:31:58", "market_structure": "HH/HL",
       "raw_payload": {"method": "pullback", "news_window": "clear", "trend": "bull"}}


def _detail(raw, trades):
    return signal_detail(signal_ref(raw, 12.0), raw, trades, 12.0)


def test_origin_names_its_fields_and_unknown_is_unknown():
    d = _detail(RAW, [])
    assert d["origin"]["originating_engine"] == {"value": "v18", "source": "signal.system"}
    assert d["origin"]["strategy_name"] == {"value": "pullback", "source": "signal.raw_payload.method"}
    assert d["origin"]["strategy_version"] == {"value": "UNKNOWN", "source": ""}
    assert d["validation"]["news"]["value"] == "clear" and d["validation"]["structure"]["value"] == "HH/HL"
    bare = _detail({"signal_id": "SIG-2", "symbol": "GOLD", "status": "pending"}, [])
    assert {bare["origin"][k]["value"] for k in ("originating_engine", "strategy_name", "timeframe", "entry", "confidence")} == {"UNKNOWN"}


def test_an_approved_signal_is_not_an_executed_trade():
    d = _detail(RAW, [{"id": 9, "symbol": "GOLD", "direction": "BUY", "entry": 100.0, "status": "closed"}])   # look-alike, no signal_id
    assert d["is_broker_execution"] is False and ("NOT an executed trade" in d["headline"] or "never executed" in d["headline"])
    st = {s["key"]: s["state"] for s in d["lifecycle"]}
    assert st == {"generated": "DONE", "council": "DONE", "user": "NOT_RECORDED", "submitted": "NOT_RECORDED",
                  "filled": "NOT_RECORDED", "closed": "NOT_RECORDED"}
    assert d["execution"]["execution_price"]["value"] == "UNKNOWN" and d["execution"]["account"]["value"] == "UNKNOWN"


def test_executed_status_without_a_linked_trade_is_reported_not_filled():
    d = _detail({**RAW, "status": "executed"}, [])
    st = {s["key"]: s["state"] for s in d["lifecycle"]}
    assert st["submitted"] == "REPORTED" and st["filled"] == "UNKNOWN" and d["is_broker_execution"] is False


def test_a_journal_row_naming_the_signal_is_the_execution():
    t = {"id": 7, "signal_id": "SIG-1", "account": "52001234", "symbol": "GOLD", "direction": "BUY", "lots": 0.1,
         "entry": 100.2, "exit": 102.0, "status": "closed", "profit": 18.0, "open_time": "a", "close_time": "b"}
    d = _detail(RAW, [t])
    assert d["is_broker_execution"] is True and {s["key"]: s["state"] for s in d["lifecycle"]}["closed"] == "DONE"
    assert d["execution"]["execution_price"]["value"] == 100.2 and d["execution"]["account"]["value"].endswith("1234")
    assert "52001234" not in str(d["execution"])


def test_signal_route(client):
    d = client.get("/api/terminal/signals/SIG-20261105-0071").json()
    assert d["origin"]["originating_engine"]["value"] == "v18" and d["is_broker_execution"] is False
    assert {a["mode"] for a in d["execution"]["adapters"]} == {"MANUAL", "MT5", "CTRADER"}
    assert client.get("/api/terminal/signals/NOPE").status_code == 404


# ------------------------------------------------------------------ execution adapters (dark)
def test_one_intent_translates_for_both_brokers_and_nothing_is_sent():
    from signalmesh_terminal.brokers.base import ExecutionRefused, PlanForTicket, intent_from_plan, intent_from_signal
    from signalmesh_terminal.brokers.ctrader import CTraderBroker
    from signalmesh_terminal.brokers.mt5 import MT5Broker
    plan = PlanForTicket("GOLD", "BUY", "BUY LIMIT", 100.0, 99.0, 102.0, None, 2.0, "SIG-1", "READY")
    intent = intent_from_plan(plan)
    m, c = MT5Broker().translate(intent), CTraderBroker().translate(intent)
    assert m["request"]["type"] == "ORDER_TYPE_BUY_LIMIT" and m["request"]["price"] == 100.0 and m["request"]["comment"] == "SIG-1"
    assert c["request"]["orderType"] == "LIMIT" and c["request"]["tradeSide"] == "BUY" and c["request"]["limitPrice"] == 100.0
    assert m["sent_to_broker"] is False and c["sent_to_broker"] is False
    assert intent_from_signal(signal_ref(RAW, 12.0)).order_kind == "UNRESOLVED"
    for b in (MT5Broker(), CTraderBroker()):
        assert b.preflight(intent)["allowed"] is False and b.describe()["can_place"] is False
        try:
            b.place(plan, "yes")
            raise AssertionError("placed")
        except ExecutionRefused:
            pass


def test_broker_package_opens_no_connection():
    from pathlib import Path
    for p in (Path(__file__).resolve().parent.parent / "signalmesh_terminal" / "brokers").glob("*.py"):
        text = p.read_text()
        for word in ("import httpx", "import requests", "import socket", "MetaTrader5", "urllib", "websocket"):
            assert word not in text, f"{p.name} contains {word}"


# ------------------------------------------------------------------ the platform's real shapes (5.200)
def test_platform_account_row_shape_is_read():
    """The row a GET /api/v1/accounts built from SignalMesh's MT5Account table would carry:
    no DEMO/LIVE, no used margin, no margin level — those stay UNKNOWN / NOT AVAILABLE."""
    v, login = acct.from_row({"login": "52834417", "broker": "Some Broker", "server": "Some-Server", "currency": "USD", "status": "active",
                              "balance": 10000.0, "equity": 10010.5, "free_margin": 9000.0, "floating_pnl": 10.5,
                              "online": True, "last_heartbeat": "2026-11-10T23:58:00+00:00"}, "/api/v1/accounts")
    assert (v.connection, v.environment, v.used_margin, v.margin_level) == ("ONLINE", "UNKNOWN", None, None)
    assert v.broker == "Some Broker" and v.server == "Some-Server" and v.login_masked == "••••4417" and login == "52834417"


def test_open_and_pending_rows_are_asked_for_by_status(client, monkeypatch):
    """An old position that is still open is not on the newest-200 list; the account view asks by status."""
    from signalmesh_terminal.providers.fixture import FixtureProvider
    old_open = {"id": 9001, "symbol": "GOLD", "direction": "BUY", "lots": 0.1, "entry": 1.0, "status": "open", "account_login": "70445566",
                "signal_id": "SIG-20261105-0071", "ticket": "777", "open_time": "2026-01-01T00:00:00"}
    real = FixtureProvider.trades
    monkeypatch.setattr(FixtureProvider, "trades", lambda self, limit=200, status="": ([old_open] if status == "open" else real(self, limit, status)))
    monkeypatch.setattr(FixtureProvider, "accounts", lambda self, path: [{"login": "70445566", "online": True, "balance": 1.0}, {"login": "52001234", "online": True, "balance": 2.0}])
    d = client.get("/api/terminal/accounts").json()
    a, b = (client.get(f"/api/terminal/account?id={x['id']}").json() for x in d["accounts"])
    assert [p["ticket"] for p in a["positions"]] == ["777"] and a["positions"][0]["signal_id"] == "SIG-20261105-0071"
    assert b["positions"] == []          # the other account never sees it
