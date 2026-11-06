"""The adapter must be unable to write to SignalMesh. Asserted by inspection
of the production provider's source: the only HTTP verb is GET."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "signalmesh_terminal"


def test_signalmesh_provider_only_gets():
    src = (SRC / "providers" / "signalmesh.py").read_text()
    for verb in ("post", "put", "patch", "delete"):
        assert not re.search(rf"\.{verb}\(", src), f"provider uses .{verb}( — forbidden"
    assert ".get(" in src


def test_no_signalmesh_imports_or_db():
    for p in SRC.rglob("*.py"):
        text = p.read_text()
        assert "from app." not in text and "import app." not in text, f"{p} imports SignalMesh code"
        assert "sqlalchemy" not in text.lower(), f"{p} touches a database"
        assert "/webhooks/" not in text, f"{p} references a webhook (write surface)"


def test_broker_place_always_refuses():
    from signalmesh_terminal.brokers.base import ExecutionRefused, PlanForTicket
    from signalmesh_terminal.brokers.ctrader import CTraderBroker
    from signalmesh_terminal.brokers.manual import ManualBroker
    from signalmesh_terminal.brokers.mt5 import MT5Broker
    plan = PlanForTicket("GOLD", "BUY", "BUY LIMIT", 1.0, 0.5, 2.0, None, 2.0, "SIG", "READY")
    for b in (ManualBroker(), MT5Broker(), CTraderBroker()):
        try:
            b.place(plan, approval="yes")
        except ExecutionRefused:
            continue
        raise AssertionError(f"{b.mode}.place did not refuse")
