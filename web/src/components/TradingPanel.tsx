import type { DecisionView, Health, SideState } from '../api/types';
import { fmtAge, fmtHM, fmtTs, px, toneOf } from '../util';

function SideCard({ s, d }: { s: SideState | undefined; d: DecisionView }) {
  if (!s) return null;
  const tone = s.state === 'READY' ? 'good' : s.state === 'INVALID' ? 'bad' : 'warn';
  const mine = s.state === 'READY';
  return (
    <div className="side" style={{ borderColor: s.side === 'BUY' ? 'rgba(38,166,154,.5)' : 'rgba(239,83,80,.5)' }}>
      <div className="side-head"><b className={s.side === 'BUY' ? 'good' : 'bad'}>{s.side}</b><span className={`pill ${tone}`}>{s.state}</span></div>
      {mine && d.order_type && <div className="mono" style={{ fontSize: 11 }}>{d.order_type} · entry {px(d.entry, d.decimals)} · SL {px(d.sl, d.decimals)}</div>}
      <div className="muted" style={{ fontSize: 11 }}>{s.reason || '—'}</div>
      {s.lane && <div className="dim" style={{ fontSize: 10 }}>{s.lane}</div>}
    </div>
  );
}

export default function TradingPanel({ d, err, health, onTicket, onSignal }: { d: DecisionView | null; err: string; health: Health | null; onTicket: () => void; onSignal?: (id: string) => void }) {
  if (err && !d) return <div className="panel"><div className="section-title">Trading panel</div><div className="note bad">{err}</div></div>;
  if (!d) return <div className="panel"><div className="section-title">Trading panel</div><div className="note">loading decision…</div></div>;
  const dec = d.decimals;
  const fr = d.freshness;
  const modes = health?.execution.modes ?? [];
  const ns = d.news_state as { state?: string; reason?: string; next_high?: { title?: string; in_min?: number } | null };
  const cur = d.levels.length > 0;
  const lv = (k: string) => d.levels.find((l) => l.key === k)?.value ?? null;
  const ref = d.price.engine_reference;
  return (
    <div className="panel">
      <div className="section-title">SignalMesh decision · {d.symbol}</div>
      {err && <div className="note bad">stale panel — {err}</div>}

      <div className="card" style={{ borderColor: d.summary === 'READY' ? 'var(--good)' : d.summary === 'INVALIDATED' ? 'var(--bad)' : 'var(--warn)' }}>
        <h4>Final decision</h4>
        <div className={`big ${toneOf(d.summary)}`}>{d.summary}</div>
        <div className="muted">engine: <b>{d.engine_status}</b>{d.lifecycle ? ` · ${d.lifecycle}` : ''}</div>
        <div style={{ marginTop: 4 }}>{d.reason || '—'}</div>
        <div className="dim" style={{ fontSize: 10, marginTop: 4 }} title="price-contract-v1: engine_reference">measured on 15m bar {fmtHM(ref?.bar_open_ts)}–{fmtHM(ref?.bar_close_ts)} UTC · close {px(ref?.price, dec)} · engine {fmtTs(d.provenance.engine_as_of)}</div>
      </div>

      <div className="sides" title={d.side_rule}>
        <SideCard s={d.sides.BUY} d={d} />
        <SideCard s={d.sides.SELL} d={d} />
      </div>

      <div className="card">
        <h4>Bias · setup</h4>
        <div className="kv">
          <span className="k">Market bias</span><span className={toneOf(d.bias)}>{d.bias ?? 'UNKNOWN'}{d.regime ? ` · ${d.regime}` : ''}</span>
          <span className="k">Validation</span><span>{d.lane.validity || d.lane.stage}{d.lane.reasons.length ? ` · ${d.lane.reasons.join(', ')}` : ''}</span>
          <span className="k">Structure</span><span className={toneOf(d.structure)}>{d.structure ?? 'UNKNOWN'}</span>
          <span className="k">Grade / score</span><span>{d.grade ?? '—'} / {d.score ?? '—'}{d.signal?.confidence != null ? ` · conf ${d.signal.confidence}` : ''}</span>
        </div>
      </div>

      <div className="card" style={{ opacity: cur ? 1 : 0.85 }}>
        <h4>Current levels {cur ? <span className="good">({d.levels[0].origin})</span> : <span className="dim">(none)</span>}</h4>
        {cur ? (
          <div className="levels">
            <div><span className="lab">ENTRY</span><span className="val accent">{px(lv('entry'), dec)}</span></div>
            <div><span className="lab">SL</span><span className="val bad">{px(lv('sl'), dec)}</span></div>
            <div><span className="lab">TP1</span><span className="val" style={{ color: 'var(--violet)' }}>{px(lv('tp1'), dec)}</span></div>
            <div><span className="lab">TP2</span><span className="val" style={{ color: 'var(--violet)' }}>{px(lv('tp2'), dec)}</span></div>
            <div><span className="lab">R:R 1 / 2</span><span className="val">{d.rr1 ?? d.signal?.rr ?? '—'} / {d.rr2 ?? '—'}</span></div>
            <div><span className="lab">ATR · dist</span><span className="val">{px(d.atr, dec)} · {d.distance_atr != null ? `${d.distance_atr} ATR` : '—'}</span></div>
          </div>
        ) : (
          <div className="muted">no actionable levels — the engine has no current plan for {d.symbol}.
            {d.expired_plan && <div className="dim" style={{ marginTop: 4, fontSize: 11 }}>last plan <a className="mono" onClick={() => onSignal?.(d.expired_plan!.signal.signal_id)} title="open the full signal information">{d.expired_plan.signal.signal_id}</a> ({d.expired_plan.signal.direction} {d.expired_plan.signal.status}) expired {d.expired_plan.signal.age_h}h ago → see <b>Trade History</b>. ATR {px(d.atr, dec)}.</div>}
          </div>
        )}
        {cur && d.signal && <div className="dim" style={{ marginTop: 6, fontSize: 11 }}>from <a className="mono" onClick={() => onSignal?.(d.signal!.signal_id)} title="open the full signal information">{d.signal.signal_id}</a> · {d.signal.system} · {d.signal.direction} · {d.signal.status} · {d.signal.age_h != null ? `${d.signal.age_h}h old` : ''}{d.signal.council_total ? ` · council ${d.signal.council_approve}/${d.signal.council_total}` : ''}</div>}
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
        <div className="dim" style={{ marginTop: 6, fontSize: 11 }}>No order can be sent from this terminal in this phase. The levels above are a SignalMesh recommendation, not a broker order.</div>
      </div>
    </div>
  );
}
