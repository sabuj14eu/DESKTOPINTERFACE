import { useState } from 'react';
import type { DecisionView, Health, LaneCard, SideState, VerdictBoard } from '../api/types';
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

// "own history: n=132 · +0.047R · CANNOT SEPARATE ? · v1 POSITIVE ✓" — every number and word is the platform's (its lane-history
// rule, named in the payload, and evidence-verdict-v1 / v2); nothing is computed here. A missing word reads NOT AVAILABLE, never a guess.
// Platform 5.206: the history cells are computed off the page and are empty for up to a minute after a restart. A cell in one of
// these states is NOT LOADED YET — that is not "no history", and it is never printed as n=0.
const notLoaded = (state?: string | null) => state === 'COMPUTING' || state === 'COLD' || state === 'FAILED';
const rr = (v: number | null | undefined, dp = 3) => (v == null ? 'NOT AVAILABLE' : `${v >= 0 ? '+' : ''}${v.toFixed(dp)}R`);
export function ownHistoryLine(l: LaneCard) {
  const h = l.own_history!; const v2 = l.verdict_v2, v1 = l.verdict_v1;
  // platform 5.214 — the same history counted by PLANS is the line to read; the bar count is an upper bound and is labelled so.
  // Without the plan count (an older platform) the line reads as it always did.
  const label = l.own_history_plans_line ? 'by bars (an upper bound)' : 'own history';
  if (notLoaded(h.state)) return <>{label}: <b className="warn">NOT LOADED YET</b>{h.level ? <span className="dim"> · {h.level}</span> : null}</>;
  // which cell answered, in the platform's own sentence — whenever it was borrowed from all symbols OR is small (under 20), so a
  // single stock's small cell (never pooled, lane-history-v2) explains itself
  const where = h.level && (h.backed_off || (h.n ?? 0) < 20) ? <span className="dim"> · {h.level}</span> : null;
  if (!h.n) return <>{label}: <b>UNKNOWN (n=0)</b>{where}</>;
  return <>{label}: n={h.n} · {rr(h.expectancy_r)} · <b className={toneWord(v2?.tone)}>{v2?.verdict ? `${v2.verdict} ${v2.icon ?? ''}` : 'v2 NOT AVAILABLE'}</b> · v1 <span className={toneWord(v1?.tone)}>{v1?.verdict ? `${v1.verdict} ${v1.icon ?? ''}` : 'NOT AVAILABLE'}</span>
    {where}</>;
}
const toneWord = (t?: string) => (t === 'good' ? 'good' : t === 'bad' ? 'bad' : 'dim');

// THE PLATFORM'S VERDICT BOARD (verdict-board-v1), shown as the platform sends it. It compares two WORDS on the same numbers;
// it does not say which rule performs better. PAPER research evidence — never a signal, never an input to a decision.
export function VerdictBoardCard({ vb, symbol }: { vb: VerdictBoard | undefined; symbol: string }) {
  const [open, setOpen] = useState(false);
  const state = vb?.state ?? 'NOT_AVAILABLE';
  const s = vb?.summary;
  return (
    <div className="card" data-testid="verdict-board">
      <h4 style={{ cursor: 'pointer' }} onClick={() => setOpen((v) => !v)} data-testid="verdict-board-toggle" title="open / fold">
        {open ? '▾' : '▸'} Evidence verdict — V1 beside V2 <span className="pill muted" style={{ float: 'right' }} title="the platform's own research evidence — a hypothesis generator, never a signal, never an executable plan">PAPER</span></h4>
      {state === 'NOT_AVAILABLE' && <div className="warn" data-testid="verdict-board-state">{vb?.note || 'NOT AVAILABLE on this platform build'}</div>}
      {state === 'FAULT' && <div className="bad" data-testid="verdict-board-state">FAULT — the platform could not build its verdict board: {vb!.fault}</div>}
      {/* platform 5.206 — the platform's own sentence about its history cells, word for word, above everything it counts. When the
          cells are not loaded every row reads UNKNOWN for THAT reason, so "under the floor" is never shown without this beside it */}
      {state === 'OK' && vb!.cells_note ? <div className={vb!.cells_ready === false ? 'warn' : 'dim'} data-testid="verdict-board-cells-note" style={{ fontSize: 11, fontWeight: vb!.cells_ready === false ? 700 : 400 }}>{vb!.cells_note}</div> : null}
      {/* platform 5.214 — the board counted by PLANS, and the platform's own sentence on why the bar count is an upper bound: read first */}
      {state === 'OK' && vb!.plans ? <div data-testid="verdict-board-plans" style={{ fontSize: 11 }}><b>BY PLANS</b> ({vb!.plans.rule} on {vb!.plans.cells_rule}): {vb!.plans.positive ?? 0}✓ · {vb!.plans.negative ?? 0}✗ · {vb!.plans.cannot_separate ?? 0} cannot separate · {vb!.plans.unknown ?? 0} unknown<div className="dim" style={{ fontSize: 10.5 }}>{vb!.plans.note}</div></div> : null}
      {state === 'OK' && s && <div className="dim" data-testid="verdict-board-summary" style={{ fontSize: 11 }}>
        {vb!.plans ? 'BY BARS (an upper bound) — ' : ''}{symbol}: {s.cells} cells · {s.measured} measured · {s.under_floor} under the floor · {s.backed_off} answered from all symbols · V2 withdraws {s.ticks_withdrawn} tick(s) and {s.crosses_withdrawn} cross(es) · V1 {s.v1_positive}✓ {s.v1_negative}✗ · V2 {s.v2_positive}✓ {s.v2_negative}✗ {s.v2_cannot_separate}?</div>}
      {state === 'OK' && open && <>
        {/* the panel is narrow, so each cell is two lines: what was measured, then the two words and what V2 changes */}
        <div className="vboard" data-testid="verdict-board-rows">
          {vb!.rows.map((r) => <div key={r.engine + r.key} className={'vrow' + (r.current ? ' sel' : '')} title={`${r.level}${r.v2?.why ? ` · v2: ${r.v2.why}` : ''}${r.v1?.why ? ` · v1: ${r.v1.why}` : ''}`}>
            <div className="vrow-a"><b>{r.label}</b> <span className="dim">{r.tf}</span> · {r.key}{r.current ? <span className="good"> ◀ this lane's setup now</span> : null}</div>
            {r.plans_line ? <div className="vrow-p" data-testid="vrow-plans"><b className={toneWord(r.plans?.verdict?.tone)}>{r.plans_line}</b></div> : null}
            <div className="vrow-b mono">{r.plans_line ? <span className="dim">by bars:</span> : null}<span title="resolved paper fills">n={r.n ?? 'NOT AVAILABLE'}</span><span title="expectancy">{r.n ? rr(r.expectancy_r) : '—'}</span>
              <span title="90% interval of the mean">{r.lo_r != null && r.hi_r != null ? `90%: ${rr(r.lo_r)} … ${rr(r.hi_r)}` : '90%: —'}</span></div>
            <div className="vrow-c"><span>V2 <b className={toneWord(r.v2?.tone)}>{r.v2?.verdict ? `${r.v2.verdict} ${r.v2.icon ?? ''}` : 'NOT AVAILABLE'}</b></span>
              <span>V1 <span className={toneWord(r.v1?.tone)}>{r.v1?.verdict ? `${r.v1.verdict} ${r.v1.icon ?? ''}` : 'NOT AVAILABLE'}</span></span>
              <span className={r.change.includes('WITHDRAWN') || r.change === 'DIFFERENT WORD' || notLoaded(r.cells_state) ? 'warn' : 'dim'} title={r.change_why}>{r.change || 'NOT AVAILABLE'}{notLoaded(r.cells_state) ? ` — history cells ${r.cells_state}: NOT LOADED YET` : ''}</span></div>
            {r.backed_off ? <div className="dim" style={{ fontSize: 10 }}>answered from all symbols — {symbol}'s own cell holds n={r.symbol_n}</div> : null}
          </div>)}
        </div>
        {vb!.rules && <div className="dim" style={{ fontSize: 10, marginTop: 4 }}>{Object.entries(vb!.rules).map(([k, v]) => `${k}: ${v}`).join(' · ')}</div>}
        <div className="warn" style={{ fontSize: 10.5, marginTop: 4 }} data-testid="verdict-board-not"><b>What this is NOT:</b> {vb!.is_not}</div>
        <div className="dim" style={{ fontSize: 10.5 }} data-testid="verdict-board-authority">{vb!.authority}</div>
        <div className="dim" style={{ fontSize: 10 }}>{vb!.rule} — shown as SignalMesh sends it; the terminal calculates none of it.</div>
      </>}
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

      <div className="card" data-testid="brain-plan" title={d.brain_plan.rule}>
        <h4>Latest brain plan <span className={`pill ${d.brain_plan.state === 'LIVE' ? 'good' : d.brain_plan.state === 'STALE' ? 'warn' : 'muted'}`} style={{ float: 'right' }}>{d.brain_plan.state.replace('_', ' ')}</span></h4>
        {d.brain_plan.signal ? (() => { const b = d.brain_plan.signal!; const stale = d.brain_plan.state === 'STALE'; return <>
          <div className={stale ? 'muted' : toneOf(b.direction)} style={{ fontSize: 15, fontWeight: 800 }}>{b.direction || 'UNKNOWN'}{b.grade ? ` · grade ${b.grade}` : ''}</div>
          <div className="plan4" style={{ opacity: stale ? 0.55 : 1 }}>
            <div><span className="lab">ENTRY</span><span className="mono">{px(b.entry, dec)}</span></div><div><span className="lab">SL</span><span className="mono bad">{px(b.sl, dec)}</span></div>
            <div><span className="lab">TP1</span><span className="mono">{px(b.tp1, dec)}</span></div><div><span className="lab">TP2</span><span className="mono">{px(b.tp2, dec)}</span></div>
          </div>
          <div className="dim" style={{ fontSize: 10.5, marginTop: 4 }}><a className="mono" onClick={() => onSignal?.(b.signal_id)} title="open the full signal information">{b.signal_id}</a> · {b.system || 'UNKNOWN'} mirror · tf {b.tf || 'UNKNOWN'} · {b.age_h ?? '—'}h old (lifecycle 12h) · status {b.status}</div>
          {d.brain_plan.note && <div className="warn" style={{ fontSize: 11, marginTop: 3 }}>{d.brain_plan.note}</div>}
          <div className="dim" style={{ fontSize: 10, marginTop: 3 }}>A SignalMesh recommendation — not a broker order.</div></>; })()
          : <div className="muted">{d.brain_plan.note}</div>}
      </div>

      <div className="card" data-testid="desk-lanes">
        <h4>Desk lanes <span className="pill muted" style={{ float: 'right' }} title="the platform's own research lanes — frozen engines, paper only, never an executable plan">PAPER</span></h4>
        {d.lanes.length ? d.lanes.map((l) => { const has = l.entry != null; return (
          <div className="lane" key={l.label + l.engine} title={`${l.engine} · ${l.verdict}`}>
            <div className="lane-head"><b>{l.label}</b><span className="dim"> {l.tf}</span><span style={{ flex: 1 }} />
              <b className={has ? toneOf(l.decision) : 'warn'}>{has ? (l.order_type || l.decision) : l.decision}</b></div>
            {has ? <div className="plan4">
              <div><span className="lab">ENTRY</span><span className="mono">{px(l.entry, dec)}</span></div><div><span className="lab">SL</span><span className="mono bad">{px(l.sl, dec)}</span></div>
              <div><span className="lab">TP1</span><span className="mono">{px(l.tp1, dec)}</span></div><div><span className="lab">TP2</span><span className="mono">{px(l.tp2, dec)}</span></div>
            </div> : <div className="dim" style={{ fontSize: 11 }}>{l.reasons.length ? `blocked by: ${l.reasons.join(', ')}` : 'no plan'}
              {l.stale_context?.word ? <span className="break-word" data-testid="lane-break-word" title={`${l.stale_context.note ?? ''}${l.stale_context.gate ? ` · gate: ${l.stale_context.gate}` : ''} · ${l.stale_context.rule ?? 'stale-context-v1'} — the platform's word beside DATA_STALE; the lane is still WAIT`}> · {l.stale_context.word}</span> : null}</div>}
            {l.own_history_plans_line ? <div className="lane-hist" data-testid="lane-plans" title={`${l.own_history_plans?.rule ?? ''} on ${l.own_history_plans?.cells_rule ?? ''} — one result per plan; SignalMesh's own sentence, nothing is calculated here`}>
              own history <b className={toneWord(l.own_history_plans?.verdict?.tone)}>{l.own_history_plans_line}</b></div> : null}
            {l.own_history ? <div className="lane-hist" data-testid="lane-own-history" title={`${l.own_history.rule ?? 'rule NOT AVAILABLE'} · ${l.own_history.level ?? ''} · ${l.own_history.population ?? ''} · ${l.measured_detail || ''} · ${l.own_history.authority ?? 'PAPER'}`}>
              {ownHistoryLine(l)}</div> : null}
          </div>); }) : <div className="muted">the desk returned no lanes for {d.symbol}</div>}
        <div className="dim" style={{ fontSize: 10, marginTop: 4 }}>Research snapshots from SignalMesh's desk — plan levels only; full reasoning is on the SignalMesh /desk page.</div>
      </div>

      <VerdictBoardCard vb={d.verdict_board} symbol={d.symbol} />

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
