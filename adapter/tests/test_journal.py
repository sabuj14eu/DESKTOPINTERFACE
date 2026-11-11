"""journal-v1 / score-v1 — the forecast journal is the terminal's own append-only store, and the
scorer reads closed bars only, never looks ahead and never moves a result backwards."""
import json
import os
import random
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from signalmesh_terminal import journal as fj
from signalmesh_terminal import recorder as rec

STEP = 900
T0 = 1_800_000_000
# Recorded production candles are NOT in this public repository. On the box the same check runs inside
# the container (scripts/export_history.sh -> scripts/history_check.py). Locally, point SMT_HISTORY_DIR
# at a folder of exported files (or drop them in the git-ignored fixtures/history/) to run it here.
HISTORY = Path(os.environ.get("SMT_HISTORY_DIR") or Path(__file__).parent / "fixtures" / "history")


def walk(n=400, seed=7):
    r = random.Random(seed)
    out, px = [], 100.0
    for i in range(n):
        o = px
        c = o + r.gauss(0, 0.6) + 0.9 * (1 if (i // 40) % 2 == 0 else -1) * r.random()
        h, l = max(o, c) + abs(r.gauss(0, 0.3)), min(o, c) - abs(r.gauss(0, 0.3))
        out.append({"t": T0 + i * STEP, "o": o, "h": h, "l": l, "c": c})
        px = c
    return out


def bar(i, o, h, l, c):
    return {"t": T0 + i * STEP, "o": o, "h": h, "l": l, "c": c}


def long_at_close(**over):
    f = {"symbol": "GOLD", "timeframe": "15m", "module": "test", "method_version": "t-v1", "direction": "LONG", "pattern": "p", "status": "confirmed",
         "entry_mode": "at_close", "entry_low": 100.0, "entry_high": 100.0, "sl": 98.0, "tp1": 102.0, "tp2": 104.0, "invalidation": 98.0,
         "horizon_bars": 5, "made_bar": T0, "made_price": 100.0}
    f.update(over)
    return f


def names(events):
    return [e["event"] for e in events]


@pytest.fixture
def jr(tmp_path):
    j = fj.Journal(tmp_path / "journal.sqlite")
    yield j
    j.close()


# ------------------------------------------------------------------ the store
def test_a_forecast_is_written_once_and_the_first_record_stands(jr):
    fid, new = jr.record(long_at_close())
    again, new2 = jr.record(long_at_close(sl=90.0, tp1=150.0, tp2=160.0, invalidation=90.0))   # same forecast "improved" afterwards
    assert new and not new2 and fid == again
    row = jr.forecasts()[0]
    assert (row["sl"], row["tp1"], row["tp2"]) == (98.0, 102.0, 104.0), "a later record must not replace the first"
    assert row["origin"] == "LIVE" and row["level_label"] == "HYPOTHETICAL ANALYSIS LEVEL"


def test_the_database_itself_refuses_edits_and_deletions(jr):
    fid, _ = jr.record(long_at_close())
    jr.add_outcomes(fid, [{"event": "SL", "bar": T0 + STEP, "bar_close": T0 + 2 * STEP, "price": 98.0}])
    raw = sqlite3.connect(str(jr.path))          # a second connection: the rule lives in the file, not in the code
    for sql in ("UPDATE forecasts SET sl = 1", "DELETE FROM forecasts", "UPDATE outcomes SET event = 'TP2'", "DELETE FROM outcomes"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            raw.execute(sql)
    raw.close()
    assert jr.info()["append_only"] is True
    assert jr.forecasts()[0]["result"] == "SL HIT"


def test_ids_and_the_whole_outcome_history_survive_a_reopen(tmp_path):
    j = fj.Journal(tmp_path / "j.sqlite")
    fid, _ = j.record(long_at_close())
    j.add_outcomes(fid, [{"event": "TP1", "bar": T0 + STEP, "bar_close": T0 + 2 * STEP, "price": 102.0}])
    j.close()
    j = fj.Journal(tmp_path / "j.sqlite")       # what a redeploy does: new process, same volume
    j.add_outcomes(fid, [{"event": "SL", "bar": T0 + 3 * STEP, "bar_close": T0 + 4 * STEP, "price": 98.0}])
    row = j.forecasts()[0]
    assert row["id"] == fid and names(row["outcomes"]) == ["TP1", "SL"] and row["result"] == "TP1 HIT, THEN SL"
    j.close()


@pytest.mark.parametrize("bad", [dict(tp2=None), dict(sl=None), dict(invalidation=None), dict(horizon_bars=0), dict(horizon_bars=None),
                                 dict(sl=101.0), dict(tp1=99.0), dict(tp2=101.0), dict(direction="BUY"), dict(timeframe="7m"),
                                 dict(entry_low=101.0, entry_high=100.0), dict(sl=float("nan")), dict(made_price=105.0)])
def test_an_incomplete_or_inconsistent_forecast_is_refused_not_recorded(jr, bad):
    with pytest.raises(fj.ForecastRefused):
        jr.record(long_at_close(**bad))
    assert jr.info()["forecasts"] == 0


def test_backup_is_a_complete_copy(jr, tmp_path):
    fid, _ = jr.record(long_at_close())
    copy = jr.backup(tmp_path / "backups" / "copy.sqlite")
    c = fj.Journal(copy)
    assert [r["id"] for r in c.forecasts()] == [fid] and c.info()["append_only"]
    c.close()


def test_the_journal_is_a_local_file_and_never_talks_to_signalmesh():
    src = (Path(fj.__file__)).read_text()
    for word in ("httpx", "requests", "urllib", "socket", "providers", "postgres", "sqlalchemy"):
        assert word not in src, f"journal.py mentions {word}"
    assert "sqlite3" in src


# ------------------------------------------------------------------ the scorer, rule by rule
def test_tp1_then_tp2():
    ev = fj.score(long_at_close(), [bar(0, 100, 100, 100, 100), bar(1, 100, 102.5, 99.5, 102), bar(2, 102, 104.2, 101.5, 104)])
    assert names(ev) == ["ENTRY", "TP1", "TP2"] and ev[1]["bar"] == T0 + STEP and ev[2]["bar"] == T0 + 2 * STEP


def test_a_bar_touching_stop_and_target_is_scored_as_the_stop():
    assert names(fj.score(long_at_close(), [bar(1, 100, 104.5, 97.5, 103)])) == ["ENTRY", "SL"]


def test_tp1_then_stop_keeps_both():
    assert names(fj.score(long_at_close(), [bar(1, 100, 102.2, 99.8, 102), bar(2, 102, 102.1, 97.9, 98)])) == ["ENTRY", "TP1", "SL"]


def test_the_forecast_bar_itself_and_earlier_bars_never_count():
    assert names(fj.score(long_at_close(), [bar(-1, 100, 110, 90, 100), bar(0, 100, 110, 90, 100)])) == ["ENTRY"]


def test_expiry_after_the_fixed_number_of_bars():
    ev = fj.score(long_at_close(), [bar(i, 100, 100.5, 99.5, 100) for i in range(1, 9)])
    assert names(ev) == ["ENTRY", "EXPIRED"] and ev[-1]["bar"] == T0 + 5 * STEP


def test_zone_entry_must_be_touched_and_invalidation_is_a_close():
    f = long_at_close(entry_mode="zone", entry_low=99.0, entry_high=99.5, invalidation=98.5, sl=98.0, made_price=100.0)
    assert names(fj.score(f, [bar(1, 100, 101, 99.8, 100.5)])) == []                                   # zone not reached: still waiting
    assert names(fj.score(f, [bar(1, 100, 100.2, 98.6, 99.9)])) == ["ENTRY"]                           # a wick into the zone enters
    assert names(fj.score(f, [bar(1, 100, 103, 99.4, 102.5)])) == ["ENTRY"], "a target in the entry bar does not count"
    assert names(fj.score(f, [bar(1, 100, 100, 97.5, 99)])) == ["ENTRY", "SL"], "the stop in the entry bar does"
    gap = [bar(1, 98.4, 98.45, 98.1, 98.2)]                                                             # gaps below the zone and closes beyond invalidation
    assert names(fj.score(f, gap)) == ["INVALIDATED"]


def test_short_is_the_mirror():
    f = long_at_close(direction="SHORT", sl=102.0, invalidation=102.0, tp1=98.0, tp2=96.0)
    assert names(fj.score(f, [bar(1, 100, 100.4, 97.9, 98), bar(2, 98, 98.5, 95.9, 96)])) == ["ENTRY", "TP1", "TP2"]
    assert names(fj.score(f, [bar(1, 100, 102.1, 95, 96)])) == ["ENTRY", "SL"]


def series_forecasts(bars, module=None):
    module = module or rec.FixtureDemoModule()
    return [fj.validate({**f, "symbol": "X", "timeframe": "15m", "module": module.name, "method_version": module.method_version})
            for f in module.forecasts("X", "15m", bars)]


def assert_no_lookahead(bars):
    """Scoring any prefix of the series gives exactly the first events of scoring the whole series."""
    forecasts = series_forecasts(bars)
    assert len(forecasts) >= 5
    seen = set()
    for f in forecasts:
        full = fj.score(f, bars)
        seen.update(names(full))
        for cut in range(0, len(bars) + 1, 7):
            part = fj.score(f, bars[:cut])
            assert part == full[:len(part)], f"{f['id']}: a prefix of {cut} bars disagrees with the full series"
            assert all(e["bar"] <= bars[cut - 1]["t"] for e in part if e["event"] != "ENTRY" or f["entry_mode"] == "zone") if cut else part in ([], full[:1])
            later = [e for e in full[len(part):] if cut and e["bar"] <= bars[cut - 1]["t"]]
            assert not later, f"{f['id']}: the full series dates an event inside a prefix that did not report it"
    return seen


@pytest.mark.parametrize("seed", [1, 7, 23, 99])
def test_scoring_never_looks_ahead_on_seeded_series(seed):
    seen = assert_no_lookahead(walk(seed=seed))
    assert {"ENTRY"} < seen


def test_the_demo_module_itself_never_looks_ahead():
    bars, m = walk(seed=5), rec.FixtureDemoModule()
    full = {f["made_bar"]: f for f in m.forecasts("X", "15m", bars)}
    for cut in range(20, len(bars), 11):
        for f in m.forecasts("X", "15m", bars[:cut]):
            assert full[f["made_bar"]] == f


def test_scoring_never_looks_ahead_on_recorded_gold_and_silver_history():
    files = sorted(HISTORY.glob("*.json")) if HISTORY.exists() else []
    if not files:
        pytest.skip("recorded history is kept out of this public repository — the check runs on the box (scripts/export_history.sh); set SMT_HISTORY_DIR to run it here")
    for p in files:
        d = json.loads(p.read_text())
        bars = [{"t": k["t"], "o": k["open"], "h": k["high"], "l": k["low"], "c": k["close"]} for k in d["candles"]]
        if len(bars) >= 200:
            assert_no_lookahead(bars[-600:])


def test_no_production_data_is_tracked_and_the_box_scripts_never_use_git():
    root = Path(__file__).resolve().parents[2]
    for script in ("export_history.sh", "journal_backup.sh", "export_history.py", "history_check.py"):
        text = (root / "scripts" / script).read_text()
        for word in ("git push", "git clone", "git commit", "git add", "git remote", "github.com"):
            assert word not in text, f"{script} must never touch git or GitHub: the box only pulls ({word})"
    ignore = (root / ".gitignore").read_text()
    for line in ("/history-export/", "/backups/", "/adapter/tests/fixtures/history/", "*.sqlite"):
        assert line in ignore
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        return
    bad = [f for f in tracked if f.startswith(("history-export/", "backups/", "adapter/tests/fixtures/history/")) or ".sqlite" in f]
    assert not bad, f"production data must never be committed: {bad}"


def test_the_on_box_history_check_passes_on_a_real_shaped_file():
    bars = walk(seed=11, n=500)
    doc = {"symbol": "GOLD", "tf": "15m", "candles": [{"t": b["t"], "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"]} for b in bars]}
    root = Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, str(root / "scripts" / "history_check.py")], input=json.dumps(doc), capture_output=True, text=True, cwd="/")
    assert r.returncode == 0 and r.stdout.startswith("OK  ") and " 0 disagreements" in r.stdout, r.stdout + r.stderr
    # the same script audits the daily-forecast module when it is given the 15m and the daily file together
    sys.path.insert(0, str(Path(__file__).parent))
    from test_forecast import market
    daily, m15 = market(days=30, seed=7, vol=0.5)
    conv = lambda sym, tf, bb: {"symbol": sym, "tf": tf, "candles": [{"t": b["t"], "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"]} for b in bb]}  # noqa: E731
    both = {"intraday": conv("GOLD", "15m", m15[-96 * 9:]), "daily": conv("GOLD", "1d", daily)}
    r = subprocess.run([sys.executable, str(root / "scripts" / "history_check.py")], input=json.dumps(both), capture_output=True, text=True, cwd="/")
    assert r.returncode == 0 and "daily-forecast no-lookahead" in r.stdout and " 0 disagreements, 0 refused" in r.stdout, r.stdout + r.stderr


# ------------------------------------------------------------------ the recorder
def test_recorder_records_every_forecast_and_scores_forward_only(jr):
    bars = walk(seed=3)
    now = bars[-1]["t"] + STEP
    cut = 250
    first = rec.run_once(jr, lambda s, tf: bars[:cut], lambda tf: ["GOLD", "SILVER"], [rec.FixtureDemoModule()], now=now)
    assert first["recorded"] > 0 and first["refused"] == 0 and not first["errors"]
    before = {r["id"]: r for r in jr.forecasts(limit=1000)}
    second = rec.run_once(jr, lambda s, tf: bars, lambda tf: ["GOLD", "SILVER"], [rec.FixtureDemoModule()], now=now)
    assert second["recorded"] > 0 and second["already_held"] == first["recorded"]
    after = {r["id"]: r for r in jr.forecasts(limit=1000)}
    for fid, old in before.items():
        new = after[fid]
        assert {k: old[k] for k in ("sl", "tp1", "tp2", "entry_low", "entry_high", "invalidation", "horizon_bars", "made_bar", "recorded_at", "origin")} == \
               {k: new[k] for k in ("sl", "tp1", "tp2", "entry_low", "entry_high", "invalidation", "horizon_bars", "made_bar", "recorded_at", "origin")}
        assert new["outcomes"][:len(old["outcomes"])] == old["outcomes"], "stored outcomes must never change, only grow"
    results = {r["result"] for r in after.values()}
    assert any("SL" in r for r in results), "losing forecasts are recorded and scored like any other"
    third = rec.run_once(jr, lambda s, tf: bars, lambda tf: ["GOLD", "SILVER"], [rec.FixtureDemoModule()], now=now)
    assert third["recorded"] == 0 and third["outcomes_added"] == 0, "a pass with no new closed bar changes nothing"


def test_live_and_backfill_are_told_apart_and_gold_and_silver_stay_separate(jr):
    bars = walk(seed=3)
    rec.run_once(jr, lambda s, tf: bars, lambda tf: ["GOLD", "SILVER"], [rec.FixtureDemoModule()], now=bars[-1]["t"] + STEP)
    stats = jr.stats()
    assert {g["symbol"] for g in stats} == {"GOLD", "SILVER"}
    for g in stats:
        assert g["recorded"] == g["open"] + g["never_entered"] + g["finished"]
        assert g["sample"].startswith("LUCK") or g["finished"] == 0 or g["finished"] >= fj.LUCK_BELOW
        assert (g["tp1_rate_pct"] is None) == (g["finished"] == 0)
    assert all(r["origin"] == ("LIVE" if r["lag_bars"] == 0 else "BACKFILL") for r in jr.forecasts(limit=1000))


def test_a_forecast_older_than_the_stored_series_is_left_unscored(jr):
    jr.record(long_at_close())
    late = [bar(i, 100, 110, 90, 100) for i in range(50, 60)]
    out = rec.run_once(jr, lambda s, tf: late, lambda tf: [], [], now=late[-1]["t"] + STEP)
    assert out["not_covered"] == 1 and out["outcomes_added"] == 0 and not jr.forecasts()[0]["finished"]


def test_a_bar_still_forming_is_never_read():
    bars = [bar(0, 1, 1, 1, 1), bar(1, 1, 1, 1, 1)]
    assert rec.closed_only(bars, "15m", now=T0 + STEP + 10) == bars[:1]


def test_sample_words():
    assert fj.sample_word(0) == "NO FINISHED FORECASTS"
    assert fj.sample_word(19).startswith("LUCK") and fj.sample_word(20).startswith("SMALL SAMPLE") and fj.sample_word(100).startswith("JUDGEABLE")


# ------------------------------------------------------------------ the route
def test_journal_route_without_a_store_says_so(client):
    d = client.get("/api/terminal/journal").json()
    assert d["state"] == "NOT_CONFIGURED" and d["rows"] == [] and d["stats"] == []
    assert "HYPOTHETICAL ANALYSIS LEVEL" in d["wall"] and len(d["rules"]) >= 10


def test_journal_route_reads_the_store_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("SMT_PROVIDER", "fixture")
    monkeypatch.setenv("SMT_ENV", "test")
    monkeypatch.setenv("SMT_AUTH", "open")
    monkeypatch.setenv("SMT_WEB_DIST", "/nonexistent")
    monkeypatch.setenv("SMT_JOURNAL_PATH", str(tmp_path / "j.sqlite"))
    from fastapi.testclient import TestClient

    from signalmesh_terminal import routes
    routes.reset_for_tests()
    from signalmesh_terminal.main import create_app
    c = TestClient(create_app())                 # no "with": the background recorder is not started
    try:
        d = c.get("/api/terminal/journal").json()
        assert d["state"] == "READY" and d["store"]["forecasts"] == 0 and d["store"]["append_only"] and d["recorder"]["running"] is False
        summary = routes.recorder().pass_once()  # one pass on the fixture series, as the background loop would
        assert summary["recorded"] > 0 and not summary["errors"]
        d = c.get("/api/terminal/journal?symbol=GOLD").json()
        assert d["rows"] and all(r["symbol"] == "GOLD" and r["module"] in ("fixture-demo", "daily-forecast") for r in d["rows"])
        n = d["store"]["forecasts"]
        for _ in range(3):
            c.get("/api/terminal/journal")
        assert c.get("/api/terminal/journal").json()["store"]["forecasts"] == n
        assert c.post("/api/terminal/journal", json={}).status_code == 405, "there is no way to write a forecast from outside"
    finally:
        routes.reset_for_tests()
