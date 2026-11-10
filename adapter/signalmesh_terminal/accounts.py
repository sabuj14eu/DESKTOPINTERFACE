"""BROKER ACCOUNTS — account-contract-v1. Broker truth only, never a SignalMesh figure.

Where the numbers come from, in this order:

  1. PER-ACCOUNT ROUTE (`SMT_ACCOUNTS_PATH`, default /api/v1/accounts): one row per
     broker account as the MT5 reporter heartbeats describe it. Each row becomes one
     selectable account; nothing is summed across rows.
  2. FALLBACK — SignalMesh's /api/v1/portfolio, which is ONE total over every
     reporting account. With exactly one account it IS that account. With more than
     one it is shown as a single entry marked COMBINED and attributed to no account,
     because splitting a total would be an invention.

Rules of this file:
  * a field the upstream row does not carry stays None — the UI prints NOT AVAILABLE;
  * nothing is derived: used margin is NOT equity minus free margin, margin level is
    NOT equity over margin. If the reporter did not send it, it is not shown;
  * DEMO / LIVE is read from the row (MT5 trade_mode or an explicit word), else UNKNOWN;
  * the full account number never leaves this module — only a masked form does;
  * `field_sources` names, per value, the upstream field it was read from.
"""
from __future__ import annotations

import hashlib

from .contract import AccountView
from .providers.base import ProviderError

RULE = ("account-contract-v1: broker-reported values only, one account per row, never summed by the terminal; "
        "a missing field is NOT AVAILABLE, never computed; DEMO/LIVE only when the broker row says so")

# upstream key aliases — MT5's own account_info() names first, then common spellings
_K = {
    "login": ("login", "account", "account_id", "account_number", "number"),
    "broker": ("broker", "company", "broker_name"),
    "server": ("server", "broker_server"),
    "platform": ("platform", "terminal", "venue"),
    "mode": ("trade_mode", "mode", "account_type", "type", "environment", "account_mode"),
    "currency": ("currency",),
    "leverage": ("leverage",),
    "balance": ("balance",),
    "equity": ("equity",),
    "floating_pnl": ("profit", "floating_pnl", "floating", "unrealized_pnl"),
    "used_margin": ("margin", "used_margin", "margin_used"),
    "free_margin": ("margin_free", "free_margin"),
    "margin_level": ("margin_level",),
    "online": ("online", "connected", "is_online"),
    "last_heartbeat": ("last_heartbeat", "heartbeat_at", "last_seen", "last_heartbeat_at", "last_seen_at"),
    "last_update": ("updated_at", "last_update", "account_updated_at", "as_of"),
    "positions": ("positions", "open_positions"),
    "orders": ("orders", "pending_orders"),
}
_TRADE_ACCOUNT_KEYS = ("account", "account_id", "login", "account_login")


def mask(ident) -> str:
    """12345678 -> ••••5678. Short ids keep only their last two characters."""
    s = str(ident or "").strip()
    if not s:
        return ""
    return ("•" * max(len(s) - 4, 2) + s[-4:]) if len(s) > 4 else "••" + s[-2:]


def account_key(platform: str, ident) -> str:
    """Opaque selector key: stable per account, does not reveal the number."""
    return platform.lower() + "-" + hashlib.sha1(str(ident).encode()).hexdigest()[:10]


def _pick(row: dict, name: str):
    for k in _K[name]:
        if k in row and row[k] not in (None, ""):
            return row[k], k
    return None, ""


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def environment(value) -> str:
    """DEMO | LIVE | UNKNOWN from the broker's own word. MT5 trade_mode: 0 demo, 1 contest, 2 real."""
    if value is None or isinstance(value, bool):
        return "UNKNOWN"
    s = str(value).strip().lower()
    if s in ("0", "demo", "account_trade_mode_demo", "practice", "paper"):
        return "DEMO"
    if s in ("2", "real", "live", "account_trade_mode_real"):
        return "LIVE"
    if s in ("1", "contest", "account_trade_mode_contest"):
        return "DEMO"
    if "demo" in s:
        return "DEMO"
    if "real" in s or "live" in s:
        return "LIVE"
    return "UNKNOWN"


def _platform(value) -> str:
    s = str(value or "").strip().lower()
    if "ctrader" in s:
        return "CTRADER"
    if "mt5" in s or "metatrader" in s:
        return "MT5"
    return ""


def from_row(row: dict, route: str, index: int = 0) -> tuple[AccountView, str]:
    """One upstream account row -> one AccountView (+ the unmasked id, kept server-side)."""
    src: dict[str, str] = {}

    def take(name, conv=lambda v: v):
        v, k = _pick(row, name)
        if k:
            src[name] = f"{route} · {k}"
        return conv(v) if k else None

    login = take("login", str) or ""
    platform = _platform(_pick(row, "platform")[0])
    if platform:
        src["platform"] = f"{route} · {_pick(row, 'platform')[1]}"
    else:
        platform = "MT5"
        src["platform"] = "SignalMesh accounts are MT5 reporter accounts (row names no platform)"
    mode_v, mode_k = _pick(row, "mode")
    env = environment(mode_v)
    if env == "UNKNOWN" and isinstance(row.get("is_demo", row.get("demo")), bool):
        env = "DEMO" if row.get("is_demo", row.get("demo")) else "LIVE"
        mode_k = "is_demo" if "is_demo" in row else "demo"
    if env != "UNKNOWN":
        src["environment"] = f"{route} · {mode_k}"
    online_v, online_k = _pick(row, "online")
    if not online_k and isinstance(row.get("status"), str):
        online_v, online_k = row["status"].strip().lower() in ("online", "connected", "live"), "status"
    connection = "UNKNOWN" if not online_k else ("ONLINE" if bool(online_v) else "OFFLINE")
    if online_k:
        src["connection"] = f"{route} · {online_k}"
    view = AccountView(
        id=account_key(platform, login or f"row-{index}"), platform=platform, environment=env,
        broker=take("broker", str), server=take("server", str), login_masked=mask(login) or None,
        currency=take("currency", str), leverage=take("leverage", _num),
        connection=connection, last_heartbeat=take("last_heartbeat", str), last_update=take("last_update", str),
        balance=take("balance", _num), equity=take("equity", _num), floating_pnl=take("floating_pnl", _num),
        used_margin=take("used_margin", _num), free_margin=take("free_margin", _num), margin_level=take("margin_level", _num),
        combined=False, accounts_in_total=1, source=f"SignalMesh {route} (MT5 reporter heartbeat, per account)",
        field_sources=src, notes=[])
    if login:
        view.field_sources["login_masked"] = view.field_sources.pop("login")
    return view, login


def from_portfolio(pf: dict, reporter_logins: list[str]) -> AccountView | None:
    """The fallback: SignalMesh's one portfolio total. Honest about what it is."""
    n = pf.get("accounts")
    online = pf.get("online")
    if not isinstance(n, (int, float)) or n < 1:
        return None
    n, online = int(n), int(online or 0)
    route = "/api/v1/portfolio"
    src = {k: f"{route} · {k}" for k in ("balance", "equity", "free_margin", "floating_pnl") if pf.get(k) is not None}
    src["platform"] = "SignalMesh portfolio = MT5 reporter heartbeats"
    src["connection"] = f"{route} · online/accounts"
    combined = n > 1
    notes = ["SignalMesh's read API gives broker, server, account type, used margin, margin level and the heartbeat time "
             "per account only through a per-account route; that route did not answer, so those fields are NOT AVAILABLE."]
    login = None
    if combined:
        notes.insert(0, f"COMBINED TOTAL of {n} accounts as summed by SignalMesh — not one account's figures. "
                        "The terminal does not split it and does not attribute it to an account.")
    elif len(reporter_logins) == 1:
        login = reporter_logins[0]
        src["login_masked"] = "per-candle source `mt5:<login>` stamped by the reporter (single account)"
    return AccountView(
        id="mt5-combined" if combined else account_key("MT5", login or "single"), platform="MT5", environment="UNKNOWN",
        broker=None, server=None, login_masked=mask(login) or None, currency=None, leverage=None,
        connection="ONLINE" if online >= 1 else "OFFLINE", last_heartbeat=None, last_update=None,
        balance=_num(pf.get("balance")), equity=_num(pf.get("equity")), floating_pnl=_num(pf.get("floating_pnl")),
        used_margin=None, free_margin=_num(pf.get("free_margin")), margin_level=None,
        combined=combined, accounts_in_total=n, online_in_total=online,
        source=f"SignalMesh {route} ({online}/{n} MT5 account(s) online)", field_sources=src, notes=notes)


def build(provider, accounts_path: str, portfolio: dict | None, reporter_logins: list[str]) -> dict:
    """-> {mode, accounts (connected), disconnected, rule, note, _logins (server-side only)}"""
    rows, why = None, ""
    if accounts_path:
        try:
            raw = provider.accounts(accounts_path)
            rows = raw.get("accounts") if isinstance(raw, dict) else raw
            if not isinstance(rows, list):
                rows, why = None, f"{accounts_path} answered an unexpected shape"
        except ProviderError as exc:
            why = (f"SignalMesh has no per-account read route at {accounts_path} (404)" if exc.status == 404
                   else f"{accounts_path}: {exc}")
    else:
        why = "per-account route disabled (SMT_ACCOUNTS_PATH is empty)"
    logins: dict[str, str] = {}
    embedded: dict[str, dict] = {}
    if rows is not None:
        views = []
        for i, r in enumerate(rows):
            if not isinstance(r, dict):
                continue
            v, login = from_row(r, accounts_path, i)
            logins[v.id] = login
            embedded[v.id] = {"positions": _pick(r, "positions")[0], "orders": _pick(r, "orders")[0]}
            views.append(v)
        mode, note = "PER_ACCOUNT", f"one row per broker account from SignalMesh {accounts_path}"
    else:
        v = from_portfolio(portfolio or {}, reporter_logins)
        views = [v] if v else []
        if v and not v.combined and len(reporter_logins) == 1:
            logins[v.id] = reporter_logins[0]
        mode = "PORTFOLIO_TOTAL"
        note = why + " — showing SignalMesh's portfolio total instead" + ("" if views else "; it reports no account")
    connected = [v for v in views if v.connection == "ONLINE"]
    other = [v for v in views if v.connection != "ONLINE"]
    return {"mode": mode, "accounts": connected, "disconnected": other, "rule": RULE, "note": note,
            "supported_types": ["MT5 Demo", "MT5 Live", "cTrader Demo", "cTrader Live"],
            "_logins": logins, "_embedded": embedded, "_total": len(views)}


def journal_for(account: AccountView, login: str, total_accounts: int, trades: list[dict]) -> tuple[list[dict], str]:
    """The SignalMesh trade-journal rows that belong to ONE account, or none when that
    cannot be known. Never another account's rows."""
    keyed = [t for t in trades if any(t.get(k) not in (None, "") for k in _TRADE_ACCOUNT_KEYS)]
    if keyed and login:
        mine = [t for t in keyed if any(str(t.get(k)) == str(login) for k in _TRADE_ACCOUNT_KEYS)]
        return mine, "journal rows matched on their own account field"
    if account.combined:
        return trades, f"COMBINED journal of {account.accounts_in_total} accounts — rows carry no account field"
    if total_accounts == 1:
        return trades, "single account: every journal row is this account's"
    return [], ("the journal rows carry no account field, so they cannot be attributed to one of "
                f"{total_accounts} accounts — nothing is shown here rather than mixed; see Trade History for the combined journal")
