"""Provider contract — the only door through which engine data enters.

A provider answers the SAME questions the SignalMesh REST mirror answers,
with the SAME payload shapes (it is the mirror's shape, verbatim). The
normaliser then reshapes one provider's answers; so swapping providers
can never change what the UI shows for the same facts.

Providers are READ-ONLY by type: the protocol has no write method.
"""
from __future__ import annotations

from typing import Protocol


class ReadOnlyProvider(Protocol):
    name: str
    is_fixture: bool

    def readiness(self) -> dict: ...
    def candles(self, symbol: str, tf: str, n: int) -> dict: ...
    def snapshot(self, symbol: str) -> dict: ...
    def desk(self, symbol: str) -> dict: ...
    def signals(self, limit: int = 200) -> list[dict]: ...
    def trades(self, limit: int = 200, status: str = "") -> list[dict]: ...
    def stats(self) -> dict: ...
    def portfolio(self) -> dict: ...
    def news_state(self, symbols: list[str]) -> dict: ...
    def news_facts(self, symbol: str) -> dict: ...
    def macro_scorecard(self) -> dict: ...
    def macro_engine(self) -> dict: ...
    def sources_evidence(self) -> dict: ...
    def ea_performance(self) -> dict: ...
    def sources_senders(self) -> dict: ...   # signal-senders-v1 cards (platform 5.233); ProviderError(status=404) on an older build
    def live_candles(self, symbol: str, tf_minutes: str, n: int, session_cookie: str) -> dict: ...   # the platform's live chart feed (forming bar), display only
    def accounts(self, path: str) -> list | dict: ...   # per-account broker rows; ProviderError(status=404) when the platform has no such route
    # platform 5.210 — three read routes; each raises ProviderError(status=404) on a platform that has not shipped it
    def market_outlook(self, symbol: str) -> dict: ...   # market-scenarios-v1: three questions from closed daily candles
    def ledger_system(self) -> dict: ...                 # system-daily-call-v1: the system's own calls and scoreboard
    def turning_points(self) -> dict: ...                # turning-point-record-v1: the old skill test's score (stored rows not asked for)


class ProviderError(Exception):
    """Upstream unreachable / refused / malformed. The UI shows the state;
    it never shows a number in its place."""

    def __init__(self, message: str, state: str = "DOWN", status: int | None = None):
        super().__init__(message)
        self.state = state
        self.status = status
