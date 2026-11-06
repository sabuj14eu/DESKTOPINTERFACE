import type { DecisionView, Health } from '../api/types';
import { fmtAge, fmtTs, px, toneOf } from '../util';

export default function TradingPanel({ d, err, health, onTicket }: { d: DecisionView | null; err: string; health: Health | null; onTicket: () => void }) {
  if (err && !d) return <div className="panel"><div className="section-title">Trading panel</div><div className="note bad">{err}</div></div>;
  if (!d) return <div className="panel"><div className="section-title">Trading panel</div><div className="note">loading decision…</div></div>;
  const dec = d.decimals;
  const buy = d.order_type?.startsWith('BUY') ?? false;
  const sell = d.order_type?.startsWith('SELL') ?? false;
  const fr = d.freshness;
  const modes = health?.execution.modes ?? [];
  const ns = d.news_state as { state?: string; reason?: string; next_high?: { title?: string; in_min?: number } | null };
  return (
    <div className="panel">
      <div className="section-title">SignalMesh decision · {d.symbol}</div>
      {err && <div className="note bad">stale panel — {err}</div>}

      <div className="card" style={{ borderColor: d.summary === 'READY' ? 'var(--good)' : d.summary === 'INVALIDATED' ? 'var(--bad)' : 'var(--warn)' }}>
        <h4>Final decision</h4>
        <div className={`big ${toneOf(d.summary)}`}>{d.summary}</div>
        <div className="muted">engine: <b>{d.engine_status}</b>{d.lifecycle ? ` · ${d.lifecycle}` : ''}</div>
        <div style={{ marginTop: 4 }}>{d.reason || '—'}</div>
      </div>

      <div className="card">
        <h4>Bias · setup</h4>
        <div className="kv">
          <span className="k">Market bias</span><span className={toneOf(d.bias)}>{d.bias ?? 'UNKNOWN'}{d.regime ? ` · ${d.regime}` : ''}</span>
          <span className="k">BUY</span><span className={buy ? 'good' : 'dim'}>{buy ? `${d.order_type} · READY` : d.lane.decision === 'BUY' ? `lane ${d.lane.stage}` : 'no BUY setup'}</span>
          <span className="k">SELL</span><span className={sell ? 'bad' : 'dim'}>{sell ? `${d.order_type} · READY` : d.lane.decision === 'SELL' ? `lane ${d.lane.stage}` : 'no SELL setup'}</span>
          <span className="k">Validation</span><span>{d.lane.validity || d.lane.stage}{d.lane.reasons.length ? ` · ${d.lane.reasons.join(', ')}` : ''}</span>
          <span className="k">Structure</span><span className={toneOf(d.structure)}>{d.structure ?? 'UNKNOWN'}</span>
          <span className="k">Grade / score</span><span>{d.grade ?? '—'} / {d.score ?? '—'}{d.signal?.confidence != null ? ` · conf ${d.signal.confidence}` : ''}</span>
        </div>
      </div>

      <div className="card">
        <h4>Levels {d.levels[0]?.stale ? <span className="warn">(expired plan — history)</span> : null}</h4>
        <div className="levels">
          <div><span className="lab">ENTRY</span><span className="val accent">{px(d.entry ?? d.levels.find((l) => l.key === 'entry')?.value, dec)}</span></div>
          <div><span className="lab">SL</span><span className="val bad">{px(d.sl ?? d.levels.find((l) => l.key === 'sl')?.value, dec)}</span></div>
          <div><span className="lab">TP1</span><span className="val" style={{ color: 'var(--violet)' }}>{px(d.tp1 ?? d.levels.find((l) => l.key === 'tp1')?.value, dec)}</span></div>
          <div><span className="lab">TP2</span><span className="val" style={{ color: 'var(--violet)' }}>{px(d.tp2 ?? d.levels.find((l) => l.key === 'tp2')?.value, dec)}</span></div>
          <div><span className="lab">R:R 1 / 2</span><span className="val">{d.rr1 ?? d.signal?.rr ?? '—'} / {d.rr2 ?? '—'}</span></div>
          <div><span className="lab">ATR · dist</span><span className="val">{px(d.atr, dec)} · {d.distance_atr != null ? `${d.distance_atr} ATR` : '—'}</span></div>
        </div>
        {d.signal && <div className="dim" style={{ marginTop: 6, fontSize: 11 }}>from <span className="mono">{d.signal.signal_id}</span> · {d.signal.system} · {d.signal.direction} · {d.signal.status} · {d.signal.age_h != null ? `${d.signal.age_h}h old` : ''}{d.signal.council_total ? ` · council ${d.signal.council_approve}/${d.signal.council_total}` : ''}</div>}
        {!d.signal && <div className="dim" style={{ marginTop: 6 }}>no signal for {d.symbol} — nothing is invented</div>}
      </div>

      <div className="card">
        <h4>News · macro</h4>
        <div className="kv">
          <span className="k">News risk</span><span className={toneOf(d.news_risk)}>{d.news_risk}{ns?.state ? ` · calendar ${ns.state}` : ''}</span>
          {ns?.reason && <><span className="k">Why</span><span className="muted">{ns.reason}</span></>}
          {d.news_events.map((e, i) => <><span className="k" key={'k' + i}>in {e.in_min}m</span><span key={'v' + i} className={toneOf(e.impact)}>{e.title} ({e.impact})</span></>)}
          {Object.entries(d.macro).map(([k, v]) => <><span className="k" key={'mk' + k}>{k}</span><span key={'mv' + k} className={toneOf(v.trend)}>{v.trend ?? 'UNKNOWN'} · {v.state}</span></>)}
        </div>
      </div>

      <div className="card">
        <h4>Freshness (engine)</h4>
        <div className="kv">
          {Object.entries(fr).map(([k, f]) => <><span className="k" key={'fk' + k}>{k}</span><span key={'fv' + k} className={toneOf(f.state)} title={f.detail}>{f.state}{f.age_min != null ? ` · ${fmtAge(f.age_min)}` : ''}{f.limit_min != null ? ` / ${fmtAge(f.limit_min)}` : ''}</span></>)}
          <span className="k">Engine as-of</span><span className="dim">{fmtTs(d.provenance.engine_as_of)}</span>
        </div>
      </div>

      <div className="card">
        <h4>Invalidation</h4>
        {d.invalidation.length ? <ul className="plain">{d.invalidation.map((s, i) => <li key={i} className="warn">{s}</li>)}</ul> : <div className="dim">none stated by the engine</div>}
        {d.why.length > 0 && <div className="dim" style={{ marginTop: 6 }}>why: {d.why.join(' · ')}</div>}
        {d.gates.length > 0 && <div style={{ marginTop: 6 }}>{d.gates.map((g) => <span key={g.gate} className={`pill ${g.ok ? 'good' : 'bad'}`} style={{ marginRight: 4, marginBottom: 3 }} title={g.detail}>{g.gate}</span>)}</div>}
      </div>

      <div className="card">
        <h4>Execution (Phase 6 — disabled)</h4>
        <button className="on" onClick={onTicket} disabled={d.summary !== 'READY'} title={d.summary !== 'READY' ? 'a ticket exists only when the engine says READY' : 'show the pending order to place by hand'}>Manual order ticket</button>
        {modes.filter((m) => m.mode !== 'MANUAL').map((m) => <button key={m.mode} disabled title={m.note} style={{ marginLeft: 4 }}>{m.mode}: {m.state}</button>)}
        <div className="dim" style={{ marginTop: 6, fontSize: 11 }}>No order can be sent from this terminal in this phase. Approval, duplicate protection, reconciliation and risk checks come before Phase 6 execution.</div>
      </div>
    </div>
  );
}
