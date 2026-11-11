"""FORECAST JOURNAL — the terminal's OWN small store (journal-v1) and its scorer (score-v1).

What it is: one SQLite file on the terminal container's own Docker volume. Every forecast a
terminal study makes is written here ONCE, at the closed bar it was made on, with its entry
zone, stop, targets, invalidation and expiry already fixed. Later the scorer marks what closed
candles did to it. Hit rates are counted from these rows and from nothing else.

What it is NOT: SignalMesh's database. It is a local file path, never a URL; it holds no
SignalMesh signal, trade, account or balance; nothing here is sent to SignalMesh. The levels
are HYPOTHETICAL ANALYSIS LEVELS of display-only studies — no order, no engine input.

APPEND-ONLY, enforced by the database itself: triggers refuse every UPDATE and DELETE on both
tables. A forecast row is never edited; its result is separate rows in `outcomes`, each naming
the closed bar that decided it. `INSERT OR IGNORE` on a deterministic id means the first record
of a forecast stands and a later re-detection of the same forecast changes nothing.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

JOURNAL_VERSION = "journal-v1"
SCORE_VERSION = "score-v1"
LEVEL_LABEL = "HYPOTHETICAL ANALYSIS LEVEL"

# sample-size words (Shyam's rule): under 20 scored forecasts is luck, about 100 to judge
LUCK_BELOW, JUDGE_FROM = 20, 100
MAX_HORIZON_BARS = 2000

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}
EVENTS = ("ENTRY", "TP1", "TP2", "SL", "INVALIDATED", "EXPIRED")
TERMINAL = ("TP2", "SL", "INVALIDATED", "EXPIRED")

RULES = [
    "A forecast is written once, at the closed bar it was made on, with entry zone, stop-loss, TP1, TP2, invalidation and expiry already fixed. A forecast missing any of them is refused, not recorded in part.",
    "Append-only: the database refuses every change and every deletion. Results are separate rows that name the closed bar which decided them.",
    "Scoring uses closed bars only, and only bars that closed AFTER the forecast's own bar.",
    "Entry: 'at close' forecasts count as entered at their own bar's close. 'Zone' forecasts are entered by the first later bar whose range touches the zone.",
    "Before entry, a CLOSE beyond the invalidation level ends the forecast as INVALIDATED (never entered).",
    "After entry: a bar that touches the stop-loss is SL, even if it also touched a target — the order inside one bar is unknown, so the worse case is taken. In the bar that touches a zone entry, a target does not count (it may have come before the entry); the stop does.",
    "TP2 implies TP1. TP1 followed later by the stop is recorded as both, in that order.",
    "A forecast with no final result when its horizon (a fixed number of bars, set at recording) has closed is EXPIRED.",
    "Hit rate = forecasts that reached the target / forecasts that were entered and are finished. Never-entered and still-open forecasts are counted and shown, and are not in the rate.",
    f"Sample size is always shown: under {LUCK_BELOW} finished forecasts is labelled LUCK, {LUCK_BELOW}–{JUDGE_FROM - 1} SMALL SAMPLE, {JUDGE_FROM} or more JUDGEABLE.",
    "LIVE = recorded at the bar it was made on. BACKFILL = calculated later from stored closed bars. The two are never mixed in one rate.",
    "Statistics are separate per module, per symbol and per timeframe: Gold and Silver are never pooled.",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS forecasts (
  id TEXT PRIMARY KEY, symbol TEXT NOT NULL, timeframe TEXT NOT NULL, module TEXT NOT NULL, method_version TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('LONG','SHORT')), pattern TEXT NOT NULL, status TEXT NOT NULL,
  entry_mode TEXT NOT NULL CHECK (entry_mode IN ('at_close','zone')), entry_low REAL NOT NULL, entry_high REAL NOT NULL,
  sl REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL NOT NULL, invalidation REAL NOT NULL,
  horizon_bars INTEGER NOT NULL, expires_bar INTEGER NOT NULL,
  made_bar INTEGER NOT NULL, made_bar_close INTEGER NOT NULL, made_price REAL NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('LIVE','BACKFILL')), lag_bars INTEGER NOT NULL,
  recorded_at TEXT NOT NULL, journal_version TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS outcomes (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, forecast_id TEXT NOT NULL REFERENCES forecasts(id),
  event TEXT NOT NULL, bar INTEGER NOT NULL, bar_close INTEGER NOT NULL, price REAL,
  score_version TEXT NOT NULL, recorded_at TEXT NOT NULL, UNIQUE (forecast_id, event)
);
CREATE INDEX IF NOT EXISTS forecasts_by_series ON forecasts (symbol, timeframe, made_bar);
CREATE TRIGGER IF NOT EXISTS forecasts_no_update BEFORE UPDATE ON forecasts BEGIN SELECT RAISE(ABORT, 'forecast journal is append-only: a forecast is never edited'); END;
CREATE TRIGGER IF NOT EXISTS forecasts_no_delete BEFORE DELETE ON forecasts BEGIN SELECT RAISE(ABORT, 'forecast journal is append-only: a forecast is never deleted'); END;
CREATE TRIGGER IF NOT EXISTS outcomes_no_update BEFORE UPDATE ON outcomes BEGIN SELECT RAISE(ABORT, 'forecast journal is append-only: an outcome is never edited'); END;
CREATE TRIGGER IF NOT EXISTS outcomes_no_delete BEFORE DELETE ON outcomes BEGIN SELECT RAISE(ABORT, 'forecast journal is append-only: an outcome is never deleted'); END;
"""
_TRIGGERS = ("forecasts_no_update", "forecasts_no_delete", "outcomes_no_update", "outcomes_no_delete")


class ForecastRefused(ValueError):
    """The forecast is incomplete or inconsistent, so it is not recorded at all."""


def _iso(epoch: int | None) -> str | None:
    return None if epoch is None else datetime.fromtimestamp(int(epoch), timezone.utc).isoformat()


def forecast_id(module: str, symbol: str, timeframe: str, made_bar: int, direction: str, pattern: str) -> str:
    """Deterministic: the same forecast found again gets the same id, so it cannot be recorded twice."""
    h = hashlib.sha1(f"{module}|{symbol}|{timeframe}|{made_bar}|{direction}|{pattern}".encode()).hexdigest()[:8]
    stamp = datetime.fromtimestamp(int(made_bar), timezone.utc).strftime("%Y%m%d-%H%M")
    return f"F-{stamp}-{symbol}-{timeframe}-{module}-{direction[0]}-{h}"


def validate(f: dict) -> dict:
    """Everything that decides the result must be fixed BEFORE recording. Returns the clean row."""
    need = ("symbol", "timeframe", "module", "method_version", "direction", "pattern", "status", "entry_mode",
            "entry_low", "entry_high", "sl", "tp1", "tp2", "invalidation", "horizon_bars", "made_bar", "made_price")
    missing = [k for k in need if f.get(k) is None or f.get(k) == ""]
    if missing:
        raise ForecastRefused(f"missing {', '.join(missing)}")
    tf = str(f["timeframe"])
    if tf not in TF_SECONDS:
        raise ForecastRefused(f"unknown timeframe {tf!r}")
    d = str(f["direction"]).upper()
    if d not in ("LONG", "SHORT"):
        raise ForecastRefused("direction must be LONG or SHORT")
    if f["entry_mode"] not in ("at_close", "zone"):
        raise ForecastRefused("entry_mode must be at_close or zone")
    try:
        lo, hi, sl, tp1, tp2, inv, px = (float(f[k]) for k in ("entry_low", "entry_high", "sl", "tp1", "tp2", "invalidation", "made_price"))
        horizon, made = int(f["horizon_bars"]), int(f["made_bar"])
    except (TypeError, ValueError) as exc:
        raise ForecastRefused(f"a level is not a number: {exc}") from None
    if any(v != v or v in (float("inf"), float("-inf")) for v in (lo, hi, sl, tp1, tp2, inv, px)):
        raise ForecastRefused("a level is not a finite number")
    if not 1 <= horizon <= MAX_HORIZON_BARS:
        raise ForecastRefused(f"horizon_bars must be 1..{MAX_HORIZON_BARS}")
    if lo > hi:
        raise ForecastRefused("entry_low is above entry_high")
    ok = (sl < lo and hi < tp1 <= tp2 and inv < lo) if d == "LONG" else (sl > hi and lo > tp1 >= tp2 and inv > hi)
    if not ok:
        raise ForecastRefused(f"levels are not in {d} order (stop and invalidation beyond the entry zone on one side, TP1 then TP2 on the other)")
    if f["entry_mode"] == "at_close" and not lo <= px <= hi:
        raise ForecastRefused("an at_close entry zone must contain the forecast bar's close")
    step = TF_SECONDS[tf]
    sym, module, pattern = str(f["symbol"]).upper(), str(f["module"]), str(f["pattern"])
    return {"id": forecast_id(module, sym, tf, made, d, pattern), "symbol": sym, "timeframe": tf, "module": module,
            "method_version": str(f["method_version"]), "direction": d, "pattern": pattern, "status": str(f["status"]),
            "entry_mode": f["entry_mode"], "entry_low": lo, "entry_high": hi, "sl": sl, "tp1": tp1, "tp2": tp2, "invalidation": inv,
            "horizon_bars": horizon, "expires_bar": made + horizon * step, "made_bar": made, "made_bar_close": made + step, "made_price": px,
            "detail": json.dumps(f.get("detail") or {}, sort_keys=True, default=str)}


def score(f: dict, bars: list[dict]) -> list[dict]:
    """score-v1 — a pure function of the forecast row and CLOSED bars [{t,o,h,l,c}] (ascending).
    Only bars after the forecast's own bar are read, one by one, so the events found on a
    prefix of the series are exactly the first events found on the whole series (tested)."""
    step = TF_SECONDS[f["timeframe"]]
    long = f["direction"] == "LONG"
    lo, hi, sl, tp1, tp2, inv = f["entry_low"], f["entry_high"], f["sl"], f["tp1"], f["tp2"], f["invalidation"]
    events: list[dict] = []
    ev = lambda name, b, price: events.append({"event": name, "bar": b["t"], "bar_close": b["t"] + step, "price": price})  # noqa: E731
    entered = f["entry_mode"] == "at_close"
    if entered:
        events.append({"event": "ENTRY", "bar": f["made_bar"], "bar_close": f["made_bar"] + step, "price": f["made_price"]})
    got_tp1 = False
    n = 0
    for b in bars:
        if b["t"] <= f["made_bar"]:
            continue
        n += 1
        if n > f["horizon_bars"]:
            break
        entry_bar = False
        if not entered:
            if b["l"] <= hi and b["h"] >= lo:
                entered = entry_bar = True
                ev("ENTRY", b, min(max(b["o"], lo), hi))
            elif (b["c"] < inv) if long else (b["c"] > inv):
                ev("INVALIDATED", b, b["c"])
                return events
        if entered:
            if (b["l"] <= sl) if long else (b["h"] >= sl):
                ev("SL", b, sl)
                return events
            if not entry_bar:
                if (b["h"] >= tp2) if long else (b["l"] <= tp2):
                    if not got_tp1:
                        ev("TP1", b, tp1)
                    ev("TP2", b, tp2)
                    return events
                if not got_tp1 and ((b["h"] >= tp1) if long else (b["l"] <= tp1)):
                    got_tp1 = True
                    ev("TP1", b, tp1)
        if n == f["horizon_bars"]:
            ev("EXPIRED", b, b["c"])
            return events
    return events


def r_multiple(events: list[str], rr1: float | None, rr2: float | None) -> float | None:
    """r-v1 — the result in units of the forecast's own risk, DERIVED from the recorded events (never stored):
    TP2 reached = +R:R of TP2; TP1 reached and nothing better = +R:R of TP1 (the first target counts as banked);
    SL before any target = -1; expired after entry with no target, or never entered = not measured (None):
    the scorer records no exit price at expiry."""
    s = set(events)
    if "TP2" in s:
        return rr2
    if "TP1" in s:
        return rr1
    if "SL" in s:
        return -1.0
    return None


def result_of(events: list[str]) -> str:
    """One word for a forecast's events so far."""
    s = set(events)
    if "TP2" in s:
        return "TP2 HIT"
    if "SL" in s:
        return "TP1 HIT, THEN SL" if "TP1" in s else "SL HIT"
    if "INVALIDATED" in s:
        return "INVALIDATED (never entered)"
    if "EXPIRED" in s:
        return "TP1 HIT, THEN EXPIRED" if "TP1" in s else ("EXPIRED" if "ENTRY" in s else "EXPIRED (never entered)")
    if "TP1" in s:
        return "TP1 HIT · open for TP2"
    return "OPEN · entered" if "ENTRY" in s else "OPEN · waiting for entry"


def sample_word(n: int) -> str:
    if n == 0:
        return "NO FINISHED FORECASTS"
    if n < LUCK_BELOW:
        return f"LUCK — n={n}, under {LUCK_BELOW}"
    return f"SMALL SAMPLE — n={n}, about {JUDGE_FROM} to judge" if n < JUDGE_FROM else f"JUDGEABLE — n={n}"


class Journal:
    """One file, one writer (the adapter runs ONE worker), a lock around every statement."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------------ writing (inserts only)
    def record(self, forecast: dict, lag_bars: int = 0) -> tuple[str, bool]:
        """Write a forecast once. Returns (id, newly_written). Raises ForecastRefused when incomplete."""
        row = validate(forecast)
        lag = max(0, int(lag_bars))
        row.update(origin="LIVE" if lag == 0 else "BACKFILL", lag_bars=lag,
                   recorded_at=datetime.now(timezone.utc).isoformat(), journal_version=JOURNAL_VERSION)
        cols = ", ".join(row)
        with self._lock:
            cur = self._db.execute(f"INSERT OR IGNORE INTO forecasts ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
            return row["id"], cur.rowcount == 1

    def add_outcomes(self, fid: str, events: list[dict]) -> int:
        """Append events not yet stored for this forecast. An event already stored is left as it is."""
        now, new = datetime.now(timezone.utc).isoformat(), 0
        with self._lock:
            for e in events:
                cur = self._db.execute("INSERT OR IGNORE INTO outcomes (forecast_id, event, bar, bar_close, price, score_version, recorded_at) VALUES (?,?,?,?,?,?,?)",
                                       (fid, e["event"], e["bar"], e["bar_close"], e.get("price"), SCORE_VERSION, now))
                new += cur.rowcount
        return new

    def backup(self, dest: str | Path) -> Path:
        """A consistent copy made by SQLite itself (safe while the adapter is writing)."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = sqlite3.connect(str(dest))
        try:
            with self._lock:
                self._db.backup(out)
        finally:
            out.close()
        return dest

    # ------------------------------------------------------------------ reading
    def _rows(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def _events(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for e in self._rows("SELECT forecast_id, event, bar, bar_close, price, score_version, recorded_at FROM outcomes ORDER BY seq"):
            out.setdefault(e.pop("forecast_id"), []).append(e)
        return out

    def events_of(self, fid: str) -> list[dict]:
        return self._rows("SELECT event, bar, bar_close, price FROM outcomes WHERE forecast_id = ? ORDER BY seq", (fid,))

    def open_forecasts(self) -> list[dict]:
        """Forecasts with no final result yet — what the scorer still has to look at."""
        marks = ", ".join(f"'{t}'" for t in TERMINAL)
        return self._rows(f"SELECT * FROM forecasts WHERE id NOT IN (SELECT forecast_id FROM outcomes WHERE event IN ({marks})) ORDER BY made_bar")

    def forecasts(self, module: str = "", symbol: str = "", timeframe: str = "", limit: int = 200) -> list[dict]:
        where, args = [], []
        for col, val in (("module", module), ("symbol", symbol.upper()), ("timeframe", timeframe)):
            if val:
                where.append(f"{col} = ?")
                args.append(val)
        rows = self._rows(f"SELECT * FROM forecasts {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY made_bar DESC, id LIMIT ?", (*args, int(limit)))
        events = self._events()
        for r in rows:
            self._dress(r, events.get(r["id"], []))
        return rows

    @staticmethod
    def _dress(r: dict, evs: list[dict]) -> None:
        r["detail"] = json.loads(r.get("detail") or "{}")
        r["made_bar_utc"], r["made_bar_close_utc"], r["expires_utc"] = _iso(r["made_bar"]), _iso(r["made_bar_close"]), _iso(r["expires_bar"] + TF_SECONDS[r["timeframe"]])
        r["outcomes"] = [{**e, "bar_utc": _iso(e["bar"]), "bar_close_utc": _iso(e["bar_close"])} for e in evs]
        names = [e["event"] for e in evs]
        r["result"] = result_of(names)
        r["finished"] = any(n in TERMINAL for n in names)
        r["decided_at_utc"] = next((_iso(e["bar_close"]) for e in reversed(evs) if e["event"] in TERMINAL), None)
        risk = abs(r["made_price"] - r["sl"]) if r["entry_mode"] == "at_close" else max(abs(r["entry_low"] - r["sl"]), abs(r["entry_high"] - r["sl"]))
        ref = r["made_price"] if r["entry_mode"] == "at_close" else (r["entry_low"] + r["entry_high"]) / 2
        r["rr1"] = round(abs(r["tp1"] - ref) / risk, 2) if risk > 0 else None
        r["rr2"] = round(abs(r["tp2"] - ref) / risk, 2) if risk > 0 else None
        r["r_multiple"] = r_multiple(names, r["rr1"], r["rr2"])
        r["level_label"] = LEVEL_LABEL

    def stats(self) -> list[dict]:
        """Hit rates per module / METHOD VERSION / symbol / timeframe / origin, each WITH its sample size.
        A changed method never shares a hit rate with the one it replaced: old rows stay (append-only) under their own version."""
        events = self._events()
        groups: dict[tuple, dict] = {}
        for f in self._rows("SELECT id, module, method_version, symbol, timeframe, origin, entry_mode, entry_low, entry_high, made_price, sl, tp1, tp2 FROM forecasts"):
            g = groups.setdefault((f["module"], f["method_version"], f["symbol"], f["timeframe"], f["origin"]), {
                "module": f["module"], "method_version": f["method_version"], "symbol": f["symbol"], "timeframe": f["timeframe"], "origin": f["origin"],
                "recorded": 0, "open": 0, "never_entered": 0, "finished": 0, "tp1": 0, "tp2": 0, "sl_before_tp1": 0, "expired_entered": 0, "r_n": 0, "r_total": 0.0})
            names = {e["event"] for e in events.get(f["id"], [])}
            g["recorded"] += 1
            if not names & set(TERMINAL):
                g["open"] += 1
            elif "ENTRY" not in names:
                g["never_entered"] += 1
            else:
                g["finished"] += 1
                g["tp1"] += "TP1" in names
                g["tp2"] += "TP2" in names
                g["sl_before_tp1"] += "SL" in names and "TP1" not in names
                g["expired_entered"] += "EXPIRED" in names and "TP1" not in names
                risk = abs(f["made_price"] - f["sl"]) if f["entry_mode"] == "at_close" else max(abs(f["entry_low"] - f["sl"]), abs(f["entry_high"] - f["sl"]))
                ref = f["made_price"] if f["entry_mode"] == "at_close" else (f["entry_low"] + f["entry_high"]) / 2
                rm = r_multiple(list(names), abs(f["tp1"] - ref) / risk if risk > 0 else None, abs(f["tp2"] - ref) / risk if risk > 0 else None)
                if rm is not None:
                    g["r_n"] += 1
                    g["r_total"] += rm
        out = []
        for g in groups.values():
            n = g["finished"]
            g["tp1_rate_pct"] = round(100.0 * g["tp1"] / n, 1) if n else None
            g["tp2_rate_pct"] = round(100.0 * g["tp2"] / n, 1) if n else None
            g["r_total"] = round(g["r_total"], 2)
            g["r_avg"] = round(g["r_total"] / g["r_n"], 2) if g["r_n"] else None
            g["sample"] = sample_word(n)
            g["judgeable"] = n >= JUDGE_FROM
            out.append(g)
        return sorted(out, key=lambda g: (g["module"], g["symbol"], g["timeframe"], g["origin"], g["method_version"]))

    def info(self) -> dict:
        with self._lock:
            n_f = self._db.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0]
            n_o = self._db.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
            trig = {r[0] for r in self._db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
            first = self._db.execute("SELECT MIN(recorded_at) FROM forecasts").fetchone()[0]
        return {"state": "READY", "store": "the terminal's own SQLite file on its own Docker volume — not SignalMesh's database",
                "file": self.path.name, "size_bytes": self.path.stat().st_size if self.path.exists() else 0,
                "forecasts": n_f, "outcomes": n_o, "first_recorded_at": first,
                "append_only": all(t in trig for t in _TRIGGERS), "journal_version": JOURNAL_VERSION, "score_version": SCORE_VERSION}


if __name__ == "__main__":   # python -m signalmesh_terminal.journal backup <journal file> <copy>   (scripts/journal_backup.sh)
    import sys

    if len(sys.argv) == 4 and sys.argv[1] == "backup":
        if not Path(sys.argv[2]).exists():
            print("NO_JOURNAL")
            sys.exit(3)
        j = Journal(sys.argv[2])
        j.backup(sys.argv[3])
        i = j.info()
        print(f"OK forecasts={i['forecasts']} outcomes={i['outcomes']} append_only={i['append_only']}")
    elif len(sys.argv) == 4 and sys.argv[1] == "restore-check":
        # RESTORE REHEARSAL (scripts/journal_restore_test.sh): the backup file is copied to a scratch place and opened
        # exactly as the terminal would open a restored journal. The live journal is only read. Nothing is replaced.
        import shutil
        import tempfile

        live_path, backup_path = sys.argv[2], sys.argv[3]
        scratch = Path(tempfile.mkdtemp()) / "restored.sqlite"
        shutil.copy(backup_path, scratch)
        r, live = Journal(scratch), Journal(live_path)
        problems = []
        if [x for x in r._rows("PRAGMA integrity_check")] != [{"integrity_check": "ok"}]:
            problems.append("the backup file fails SQLite's integrity check")
        ri, li = r.info(), live.info()
        lf = {x["id"]: x for x in live._rows("SELECT * FROM forecasts")}
        rf = r._rows("SELECT * FROM forecasts")
        missing = [x["id"] for x in rf if x["id"] not in lf]
        changed = [x["id"] for x in rf if x["id"] in lf and lf[x["id"]] != x]
        lo = {(x["forecast_id"], x["event"]): x for x in live._rows("SELECT * FROM outcomes")}
        ro = r._rows("SELECT * FROM outcomes")
        o_bad = [x for x in ro if lo.get((x["forecast_id"], x["event"])) != x]
        if missing:
            problems.append(f"{len(missing)} forecasts of the backup are not in the live journal")
        if changed:
            problems.append(f"{len(changed)} forecasts differ between backup and live (a recorded forecast was changed)")
        if o_bad:
            problems.append(f"{len(o_bad)} outcome marks of the backup are missing or different in the live journal")
        refused = 0
        for sql in ("UPDATE forecasts SET sl = sl + 1", "DELETE FROM forecasts", "DELETE FROM outcomes"):
            try:
                r._db.execute(sql)
            except Exception:  # noqa: BLE001 — the triggers must refuse
                refused += 1
        if rf and refused != 3:
            problems.append("the restored journal accepted an edit or a deletion")
        readable = len(r.forecasts(limit=1000)) == min(ri["forecasts"], 1000) and isinstance(r.stats(), list)
        if not readable:
            problems.append("the restored journal could not be read back through the terminal's own code")
        print(f"{'OK  ' if not problems else 'FAIL'} journal restore rehearsal: backup holds {ri['forecasts']} forecasts / {ri['outcomes']} outcome marks, live holds "
              f"{li['forecasts']} / {li['outcomes']}; every backup row is in the live journal unchanged: {not (missing or changed or o_bad)}; restored copy opens and reads: {readable}; "
              f"edits and deletions refused: {refused} of 3" + ("" if not problems else " — " + "; ".join(problems)))
        r.close()
        live.close()
        shutil.rmtree(scratch.parent, ignore_errors=True)
        sys.exit(0 if not problems else 1)
    else:
        sys.exit("usage: python -m signalmesh_terminal.journal backup <journal file> <copy> | restore-check <journal file> <backup file>")
