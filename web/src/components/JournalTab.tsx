import { useState } from 'react';
import { api } from '../api/client';
import { fmtTs, usePoll } from '../util';

// FORECAST JOURNAL — the terminal's own append-only record of its display-only forecasts and what
// closed candles later did to them. Everything here is read from /journal; the page writes nothing.
export interface JournalOutcome { event: string; bar_utc: string; bar_close_utc: string; price: number | null }
export interface JournalRow {
  id: string; symbol: string; timeframe: string; module: string; method_version: string; direction: 'LONG' | 'SHORT'; pattern: string; status: string;
  entry_mode: 'at_close' | 'zone'; entry_low: number; entry_high: number; sl: number; tp1: number; tp2: number; invalidation: number; rr1: number | null; rr2: number | null;
  horizon_bars: number; made_bar_utc: string; made_bar_close_utc: string; expires_utc: string; origin: 'LIVE' | 'BACKFILL'; lag_bars: number; recorded_at: string;
  outcomes: JournalOutcome[]; result: string; finished: boolean; decided_at_utc: string | null;
}
export interface JournalStat {
  module: string; symbol: string; timeframe: string; origin: string; recorded: number; open: number; never_entered: number; finished: number;
  tp1: number; tp2: number; sl_before_tp1: number; expired_entered: number; tp1_rate_pct: number | null; tp2_rate_pct: number | null; sample: string; judgeable: boolean;
}
export interface JournalView {
  as_of: string; state: string; note?: string; wall: string; level_label: string; rules: string[]; journal_version: string; score_version: string;
  sample_rule: { luck_below: number; judge_from: number };
  store: { file: string; size_bytes: number; forecasts: number; outcomes: number; first_recorded_at: string | null; append_only: boolean; store: string } | null;
  recorder: { running: boolean; interval_s: number; passes: number; modules: string[]; last_pass: { at: string; recorded?: number; outcomes_added?: number; open?: number; not_covered?: number; errors: string[] } | null } | null;
  stats: JournalStat[]; rows: JournalRow[];
}

const num = (v: number) => (Math.abs(v) >= 1000 ? v.toFixed(2) : Math.abs(v) >= 10 ? v.toFixed(3) : v.toFixed(5));
const rate = (pct: number | null, hits: number, n: number) => (pct == null ? 'UNKNOWN' : `${pct}%  (${hits} of ${n})`);
const tone = (r: JournalRow) => (r.result.startsWith('TP') ? 'good' : r.result.startsWith('SL') ? 'bad' : r.finished ? 'dim' : 'warn');

export default function JournalTab({ pollMs }: { pollMs: number }) {
  const { data, error } = usePoll(() => api.journal(), pollMs * 2);
  const [open, setOpen] = useState('');
  if (error) return <div className="note bad">{error}</div>;
  if (!data) return <div className="note">loading…</div>;
  const s = data.store, r = data.recorder;
  return (
    <div data-testid="journal">
      <div className="wall study"><span className="tag">TERMINAL STUDY · NOT SIGNALMESH</span> {data.wall.replace(/^TERMINAL STUDIES — /, '')}</div>
      <div style={{ padding: '4px 10px' }}>
        {data.state !== 'READY' && <div className="note warn" data-testid="journal-state">{data.state.replace('_', ' ')} — {data.note}</div>}
        {s && <div data-testid="journal-store">
          {[['Forecasts recorded', s.forecasts], ['Outcome marks', s.outcomes], ['Append-only', s.append_only ? 'YES — the database refuses edits' : 'NO — CHECK'], ['First record', s.first_recorded_at ? fmtTs(s.first_recorded_at) : '—'],
            ['Recorder', r ? (r.running ? `running · every ${r.interval_s}s` : 'not running') : '—'], ['Modules recording', r && r.modules.length ? r.modules.join(', ') : 'none yet'], ['Last pass', r?.last_pass ? fmtTs(r.last_pass.at) : '—']]
            .map(([k, v]) => <span className="stat" key={String(k)}><span className="k">{k}</span><span className={`v ${k === 'Append-only' ? (s.append_only ? 'good' : 'bad') : ''}`}>{String(v)}</span></span>)}
        </div>}
        {r?.last_pass?.errors?.length ? <div className="note bad">recorder: {r.last_pass.errors.slice(0, 3).join(' · ')}</div> : null}
        {s && s.forecasts === 0 && <div className="note" data-testid="journal-empty">0 forecasts. No forecasting study is recording yet — the record starts with the first study and cannot be filled in by hand. Hit rates and confidence read UNKNOWN until there is a record.</div>}

        <div className="dim" style={{ margin: '6px 0 3px' }}><b>Hit rates</b> — per module, symbol and timeframe, never pooled. Rate = reached the target ÷ entered and finished. Under {data.sample_rule.luck_below} finished is <b>LUCK</b>; about {data.sample_rule.judge_from} to judge.</div>
        <table className="grid" data-testid="journal-stats">
          <thead><tr><th>Module</th><th>Symbol</th><th>TF</th><th>Record</th><th>Recorded</th><th>Open</th><th>Never entered</th><th>Finished (n)</th><th>TP1 hit</th><th>TP2 hit</th><th>SL before TP1</th><th>Sample</th></tr></thead>
          <tbody>
            {data.stats.map((g) => <tr key={`${g.module}|${g.symbol}|${g.timeframe}|${g.origin}`}>
              <td>{g.module}</td><td><b>{g.symbol}</b></td><td>{g.timeframe}</td><td className={g.origin === 'LIVE' ? '' : 'dim'}>{g.origin}</td><td className="mono">{g.recorded}</td><td className="mono">{g.open}</td><td className="mono">{g.never_entered}</td>
              <td className="mono"><b>{g.finished}</b></td><td className="mono">{rate(g.tp1_rate_pct, g.tp1, g.finished)}</td><td className="mono">{rate(g.tp2_rate_pct, g.tp2, g.finished)}</td><td className="mono">{g.sl_before_tp1}</td>
              <td className={g.judgeable ? 'good' : 'warn'}>{g.sample}</td></tr>)}
            {!data.stats.length && <tr><td colSpan={12} className="dim">no forecasts recorded — hit rate UNKNOWN</td></tr>}
          </tbody>
        </table>

        <div className="dim" style={{ margin: '8px 0 3px' }}><b>The record</b> — newest first, losses included. Every level is a <b>{data.level_label}</b>. Click a row for its outcome history.</div>
        <table className="grid" data-testid="journal-rows">
          <thead><tr><th>Forecast bar (UTC)</th><th>Module</th><th>Symbol</th><th>TF</th><th>Dir</th><th>Pattern</th><th>Entry</th><th>SL</th><th>TP1</th><th>TP2</th><th>R:R</th><th>Invalidation</th><th>Horizon</th><th>Record</th><th>Result</th><th>Decided (bar close)</th></tr></thead>
          <tbody>
            {data.rows.map((f) => [
              <tr key={f.id} className="row" onClick={() => setOpen(open === f.id ? '' : f.id)} style={{ cursor: 'pointer' }}>
                <td className="mono">{fmtTs(f.made_bar_utc)}</td><td>{f.module}</td><td><b>{f.symbol}</b></td><td>{f.timeframe}</td><td className={f.direction === 'LONG' ? 'good' : 'bad'}>{f.direction}</td><td>{f.pattern}</td>
                <td className="mono">{f.entry_mode === 'at_close' ? `${num(f.entry_low)} (bar close)` : `${num(f.entry_low)} – ${num(f.entry_high)}`}</td><td className="mono">{num(f.sl)}</td><td className="mono">{num(f.tp1)}</td><td className="mono">{num(f.tp2)}</td>
                <td className="mono">{f.rr1 ?? '—'} / {f.rr2 ?? '—'}</td><td className="mono">{num(f.invalidation)}</td><td className="mono">{f.horizon_bars} bars</td><td className={f.origin === 'LIVE' ? '' : 'dim'}>{f.origin}</td>
                <td className={tone(f)}><b>{f.result}</b></td><td className="mono">{f.decided_at_utc ? fmtTs(f.decided_at_utc) : '—'}</td></tr>,
              open === f.id && <tr key={f.id + ':d'} data-testid="journal-detail"><td colSpan={16} className="dim">
                <span className="mono">{f.id}</span> · method {f.method_version} · status when recorded: {f.status} · recorded {fmtTs(f.recorded_at)}{f.origin === 'BACKFILL' ? ` (${f.lag_bars} bars after its own bar — BACKFILL, calculated from stored closed bars)` : ' (at its own bar — LIVE)'} · horizon ends about {fmtTs(f.expires_utc)} (ESTIMATE)
                <br />{f.outcomes.length ? f.outcomes.map((o) => `${o.event} — bar ${fmtTs(o.bar_utc)}, closed ${fmtTs(o.bar_close_utc)}${o.price != null ? ` @ ${num(o.price)}` : ''}`).join('  →  ') : 'no outcome mark yet'}</td></tr>])}
            {!data.rows.length && <tr><td colSpan={16} className="dim">nothing recorded yet</td></tr>}
          </tbody>
        </table>

        <details style={{ marginTop: 8 }} data-testid="journal-method"><summary><b>How forecasts are recorded and scored</b> ({data.journal_version} · {data.score_version})</summary>
          <ol style={{ margin: '4px 0 4px 18px', padding: 0 }}>{data.rules.map((t) => <li key={t} className="dim">{t}</li>)}</ol>
          <div className="dim">Store: {s ? `${s.store} (${s.file}, ${Math.round(s.size_bytes / 1024)} KB)` : 'not configured'}. Backed up to the box's <span className="mono">backups/</span> folder before every deployment.</div>
        </details>
        <div className="dim" style={{ marginTop: 6 }}>as of {fmtTs(data.as_of)} · terminal study, not SignalMesh engine output · no order is placed and no SignalMesh decision, level or statistic is changed</div>
      </div>
    </div>
  );
}
