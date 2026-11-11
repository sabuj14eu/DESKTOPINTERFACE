"""Configuration — SEPARATE from SignalMesh's BB_* namespace (prefix SMT_).

Nothing here is shared with the production platform's .env. The adapter
holds one READ-scoped SignalMesh API key and nothing else of the platform's.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMT_", env_file=".env", extra="ignore")

    # signalmesh = read the live platform through /api/v1 (production use)
    # fixture    = recorded responses on disk; DEVELOPMENT ONLY, loudly labelled
    provider: str = "signalmesh"
    signalmesh_url: str = "http://127.0.0.1:8000"
    signalmesh_api_key: str = ""          # a READ-scoped key (Dashboard -> API)
    signalmesh_timeout_s: float = 20.0

    # OPTIONAL pins for the Market Watch (SignalMesh canonical names). Empty = every instrument
    # SignalMesh has candles for, discovered automatically (see discovery.py).
    symbols: str = ""
    default_symbol: str = "GOLD"

    # How long one upstream answer is reused before re-asking (seconds).
    cache_ttl_s: float = 15.0
    # Suggested UI poll interval (the UI reads it from /api/terminal/health).
    poll_s: int = 15

    # WHO MAY OPEN THE TERMINAL.
    #   signalmesh  the user's own SignalMesh login: the browser's bb_session cookie
    #               (sent automatically when the terminal is served under the SignalMesh
    #               site, e.g. /terminal/) is checked against SignalMesh for every request
    #               (cached 60 s). No second password, no token.
    #   token       a separate SMT_ACCESS_TOKEN typed on the lock screen (standalone use).
    #   open        no check (local development only).
    auth: str = "signalmesh"
    access_token: str = ""
    # Where to send a browser that is not logged in (SignalMesh's own login page; the
    # path is relative to the site; ?next= brings the user back to the terminal).
    login_path: str = "/login?next=/terminal/"
    auth_cache_s: float = 60.0

    # Per-account broker rows (read). SignalMesh's /api/v1/portfolio is ONE total over every
    # reporting account; this route, when the platform has it, gives one row per account so
    # balances and positions are never mixed. A 404 falls back to the portfolio total, labelled
    # as such. Empty = do not ask.
    accounts_path: str = "/api/v1/accounts"

    # Execution. Phase 6 only. Even when true, place() refuses in this phase.
    execution_enabled: bool = False
    execution_phase: str = "PHASE_1_TO_5_DISPLAY_ONLY"

    # Where the built web UI lives (served as static files when present).
    web_dist: str = "../web/dist"

    # Signal lifecycle TTL mirrored from SignalMesh (chart.SIGNAL_TTL_H /
    # planner.SIGNAL_FRESH_H = 12h). A display rule, not a decision rule.
    signal_ttl_h: float = 12.0

    # FORECAST JOURNAL — the terminal's OWN store: one SQLite file on the terminal container's own
    # Docker volume (compose mounts it at /data). A file path, never a URL; never SignalMesh's
    # database. Empty = no journal (the tab says NOT CONFIGURED and nothing is recorded).
    journal_path: str = ""
    # The server-side recorder (forecasts at each closed bar + scoring), one pass every N seconds.
    journal_recorder: bool = True
    journal_interval_s: float = 60.0

    env: str = "development"
    cors_origins: str = ""

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
