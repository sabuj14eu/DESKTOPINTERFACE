"""A stand-in SignalMesh for a DRY RUN of the acceptance script: the fixture provider served over HTTP at the engine's own
paths, plus a few fresh EA / brain signals so that chart levels come from signals of several senders (what the box has).
Test data only. It lets scripts/verify_parity.py run end to end before it ever meets the box."""
import os, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "adapter"))
from fastapi import FastAPI, HTTPException
import uvicorn
from signalmesh_terminal.providers.fixture import FixtureProvider
from signalmesh_terminal.providers.base import ProviderError

p = FixtureProvider()
app = FastAPI()
T0 = datetime.now(timezone.utc)

def fresh():
    mk = lambda system, sid, sym, mins, status, e, sl, t1, t2: {"signal_id": sid, "system": system, "symbol": sym, "tf": "5m", "direction": "SELL", "entry": e, "sl": sl, "tp1": t1, "tp2": t2,
        "rr": 1.0, "grade": "", "status": status, "created_at": (T0 - timedelta(minutes=mins)).isoformat()}
    return [mk("NQ-EA", "NQ:XAUUSD:NQ-R1795644900", "GOLD", 3, "approved", 4251.0, 4256.0, 4246.0, 4241.0),
            mk("mt5", "PB-SELL--95597200", "SILVER", 25, "pending", 56.2, 56.9, 55.5, 55.0),
            mk("v18", "PB-SELL-20261125-0007", "BTC", 50, "approved", 112500.0, 113100.0, 111900.0, 111300.0)]

def wrap(fn):
    try:
        return fn()
    except ProviderError as exc:
        raise HTTPException(exc.status or 502, str(exc))
    except FileNotFoundError:
        raise HTTPException(404, "not in the fixture")

@app.get("/readyz")
def readyz(): return p.readiness()
@app.get("/api/v1/market/candles")
def candles(symbol: str, tf: str, n: int = 300): return wrap(lambda: p.candles(symbol, tf, n))
@app.get("/api/v1/market/snapshot")
def snapshot(symbol: str): return wrap(lambda: p.snapshot(symbol))
@app.get("/api/v1/market/desk")
def desk(symbol: str): return wrap(lambda: p.desk(symbol))
@app.get("/api/v1/market/outlook")
def outlook(symbol: str): return wrap(lambda: p.market_outlook(symbol))
@app.get("/api/v1/signals")
def signals(limit: int = 200): return (fresh() + p.signals(limit))[:limit]
@app.get("/api/v1/trades")
def trades(limit: int = 200, status: str = ""): return wrap(lambda: p.trades(limit, status))
@app.get("/api/v1/stats")
def stats(): return p.stats()
@app.get("/api/v1/portfolio")
def portfolio(): return p.portfolio()
@app.get("/api/v1/news/state")
def news_state(symbols: str = ""): return wrap(lambda: p.news_state([s for s in symbols.split(",") if s]))
@app.get("/api/v1/news/facts")
def news_facts(symbol: str): return wrap(lambda: p.news_facts(symbol))
@app.get("/api/v1/macro/scorecard")
def scorecard(): return p.macro_scorecard()
@app.get("/api/v1/macro/engine")
def engine(): return p.macro_engine()
@app.get("/api/v1/sources/evidence")
def evidence(): return p.sources_evidence()
@app.get("/api/v1/sources/senders")
def senders(): return p.sources_senders()
@app.get("/api/v1/ea/performance")
def ea(): return p.ea_performance()
@app.get("/api/v1/ledger/system")
def ledger(): return wrap(p.ledger_system)
@app.get("/api/v1/turning-points")
def tp(): return wrap(p.turning_points)
@app.get("/api/v1/accounts")
def accounts(): return wrap(lambda: p.accounts("/api/v1/accounts"))

uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8201")), log_level="warning")
