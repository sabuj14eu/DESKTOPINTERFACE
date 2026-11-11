import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { SignalDetail as Detail, Sourced } from '../api/types';
import { fmtTs, toneOf } from '../util';

const ORIGIN: [string, string][] = [
  ['signal_id', 'Signal ID'], ['originating_engine', 'Originating engine'], ['engine_detail', 'Engine detail'], ['strategy_name', 'Strategy name'],
  ['strategy_version', 'Strategy version'], ['symbol', 'Symbol'], ['timeframe', 'Timeframe'], ['direction', 'BUY or SELL'], ['created_at', 'Created (UTC)'],
  ['entry', 'Entry price'], ['sl', 'SL'], ['tp1', 'TP1'], ['tp2', 'TP2'], ['risk_reward', 'Risk / reward'], ['confidence', 'Confidence'], ['grade', 'Grade'],
];
const STATE_TONE: Record<string, string> = { DONE: 'good', REPORTED: 'warn', NOT_DONE: 'muted', NOT_RECORDED: 'muted', REJECTED: 'bad', UNKNOWN: 'warn' };
const STATE_WORD: Record<string, string> = { DONE: 'YES', REPORTED: 'REPORTED BY SIGNALMESH', NOT_DONE: 'NOT YET', NOT_RECORDED: 'NOT RECORDED', REJECTED: 'REJECTED', UNKNOWN: 'UNKNOWN' };

function Val({ v, time }: { v: Sourced | undefined; time?: boolean }) {
  if (!v) return <span className="warn">UNKNOWN</span>;
  const unknown = v.value === 'UNKNOWN';
  return <><span className={unknown ? 'warn' : (typeof v.value === 'string' && ['BUY', 'SELL'].includes(v.value) ? toneOf(v.value) : '')} style={{ fontWeight: unknown ? 700 : 600 }}>{time && !unknown ? fmtTs(String(v.value)) : String(v.value)}</span>
    {v.source && <span className="src" title="the SignalMesh field this value was read from">{v.source}</span>}</>;
}

/** Everything SignalMesh says about one signal: where it came from and how far it really got. */
export default function SignalDetail({ id, onClose, onShow }: { id: string; onClose: () => void; onShow: (symbol: string) => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { setD(null); setErr(''); let live = true; api.signal(id).then((x) => { if (live) setD(x); }).catch((e) => { if (live) setErr(String(e.message || e)); }); return () => { live = false; }; }, [id]);
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onClose(); } }; window.addEventListener('keydown', k, true); return () => window.removeEventListener('keydown', k, true); }, [onClose]);
  return (
    <div className="drawer-bg" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} data-testid="signal-detail" aria-label="Signal information">
        <div className="drawer-head"><b>Signal information</b> <span className="mono">{id}</span><span style={{ flex: 1 }} />
          {d && <button onClick={() => { onShow(d.signal.symbol); onClose(); }} title="show this symbol on the chart">show on chart</button>}<button onClick={onClose} aria-label="Close">✕</button></div>
        {err && <div className="note bad">{err}</div>}
        {!d && !err && <div className="note">loading…</div>}
        {d && <div className="drawer-body">
          <div className={`headline ${d.is_broker_execution ? 'good' : d.signal.status === 'rejected' ? 'bad' : 'warn'}`} data-testid="signal-headline">
            <div className="kind">{d.is_broker_execution ? 'BROKER EXECUTION (linked journal row)' : 'SIGNALMESH SIGNAL — A RECOMMENDATION'}</div>{d.headline}</div>

          <h4>Lifecycle — how far this signal really got</h4>
          <ol className="stages">{d.lifecycle.map((s) => (
            <li key={s.key} className={STATE_TONE[s.state]} data-stage={s.key} data-state={s.state}>
              <span className="dot" /><div><b>{s.label}</b> <span className={`pill ${STATE_TONE[s.state]}`}>{STATE_WORD[s.state]}</span>
                <div className="muted">{s.detail}{s.at ? ` · ${fmtTs(s.at)}` : ''}</div>{s.source && <div className="src">{s.source}</div>}</div>
            </li>))}</ol>

          <h4>Origin</h4>
          <div className="kv wide" data-testid="signal-origin">{ORIGIN.map(([k, label]) => <span key={k} style={{ display: 'contents' }}><span className="k">{label}</span><span data-field={k}><Val v={d.origin[k]} time={k === 'created_at'} /></span></span>)}</div>

          <h4>Validation</h4>
          <div className="kv wide">
            <span className="k">Structure validation</span><span><Val v={d.validation.structure} />{Object.keys(d.validation.structure.sensor_words).length > 0 && <div className="muted">sensor: {Object.entries(d.validation.structure.sensor_words).map(([k, v]) => `${k} ${String(v)}`).join(' · ')}</div>}</span>
            <span className="k">News validation</span><span><Val v={d.validation.news} /></span>
            <span className="k">Brain council</span><span><Val v={d.validation.council} /></span>
            <span className="k">Brain reason</span><span><Val v={d.validation.brain_reason} /></span>
          </div>

          <h4>Invalidation conditions</h4>
          <ul className="plain">{d.invalidation.map((s, i) => <li key={i} className="warn">{s}</li>)}</ul>

          <h4>Execution</h4>
          <div className="kv wide">
            <span className="k">Execution status</span><span className={d.is_broker_execution ? 'good' : 'warn'} style={{ fontWeight: 700 }}>{d.execution.status}</span>
            <span className="k">Broker source</span><span><Val v={d.execution.broker_source} /></span>
            <span className="k">Account identifier</span><span><Val v={d.execution.account} /></span>
            <span className="k">Actual execution price</span><span><Val v={d.execution.execution_price} /></span>
            <span className="k">Exit price</span><span><Val v={d.execution.exit_price} /></span>
            <span className="k">Lots</span><span><Val v={d.execution.lots} /></span>
            <span className="k">Realised P/L</span><span><Val v={d.execution.profit} /></span>
          </div>
          {d.execution.link_note && <div className="note" style={{ paddingLeft: 0 }}>{d.execution.link_note}.</div>}
          <div className="note dim" style={{ paddingLeft: 0 }}>{d.execution.link_rule}.</div>
          <div className="note" style={{ paddingLeft: 0 }}>Execution adapters (disabled in this phase): {d.execution.adapters.map((a) => <span key={a.mode} className="pill muted" style={{ marginRight: 4 }} title={a.note}>{a.mode} · {a.state}</span>)}</div>

          {Object.keys(d.sensor_payload).length > 0 && <><h4>Sensor's own words (raw_payload)</h4>
            <div className="words">{Object.entries(d.sensor_payload).map(([k, v]) => <span key={k}><span className="dim">{k}</span> <b>{String(v)}</b></span>)}</div></>}
          <div className="note dim" style={{ paddingLeft: 0, marginTop: 10 }}>{d.rule}. Fields SignalMesh sent for this signal: {d.fields_seen.signal.join(', ') || 'none'}{d.fields_seen.raw_payload.length ? ` · raw_payload: ${d.fields_seen.raw_payload.join(', ')}` : ' · no raw_payload'}.</div>
        </div>}
      </aside>
    </div>
  );
}
