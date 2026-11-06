"""MODE B — MT5 EXECUTION (Phase 6). Stub: DISABLED.

When built, this adapter will talk to the EXISTING SignalMesh MT5
integration (the reporter / executor on the Windows box), never to MT5
directly from the terminal, and only after Phase 6's gates exist.
"""
from __future__ import annotations

from .base import BrokerAdapter


class MT5Broker(BrokerAdapter):
    mode = "MT5"
    label = "MT5 (via existing SignalMesh integration)"

    def describe(self) -> dict:
        return {"mode": self.mode, "label": self.label, "state": "DISABLED",
                "note": "Phase 6: approve-and-place pending orders through the existing MT5 integration. Not built; nothing can be sent."}
