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

    # Symbols shown in the Market Watch (SignalMesh canonical names).
    symbols: str = "GOLD,SILVER,BTC"
    default_symbol: str = "GOLD"

    # How long one upstream answer is reused before re-asking (seconds).
    cache_ttl_s: float = 15.0
    # Suggested UI poll interval (the UI reads it from /api/terminal/health).
    poll_s: int = 15

    # OPTIONAL access token for the terminal itself. The adapter holds the
    # SignalMesh key, so an internet-facing terminal must not be anonymous.
    access_token: str = ""

    # Execution. Phase 6 only. Even when true, place() refuses in this phase.
    execution_enabled: bool = False
    execution_phase: str = "PHASE_1_TO_5_DISPLAY_ONLY"

    # Where the built web UI lives (served as static files when present).
    web_dist: str = "../web/dist"

    # Signal lifecycle TTL mirrored from SignalMesh (chart.SIGNAL_TTL_H /
    # planner.SIGNAL_FRESH_H = 12h). A display rule, not a decision rule.
    signal_ttl_h: float = 12.0

    env: str = "development"
    cors_origins: str = ""

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
