// SENDER CARDS (sender-cards-v1) — SignalMesh's own signal-sender cards (its rule signal-senders-v1, GROUP S of its /sources page),
// printed line by line on the Performance tab in place of one pooled win rate (Shyam's yes, 2026-11-25).
// The terminal computes NOTHING here: no rate, no total, no rank, no colour for good or bad, and it never adds two lines together.
// A break-even is the PLANNED one and is printed with that word. null is UNKNOWN, never 0.
export interface SenderRow {
  label: string; sent: number; n: number; wins: number; losses: number; flat: number; win_rate: number | null; ci: [number, number] | null;
  avg_rr: number | null; planned_be: number | null; evidence: string; reading: string;
  filled?: number | null; no_fill?: number | null; running?: number | null; false_break?: number | null;
}
export interface SenderTable { title: string; kind: 'brain' | 'ea' | string; rows: SenderRow[] }
export interface SenderCard {
  id: string; name: string; state: string; technical?: string; born?: string; judged_by?: string; outcome_is?: string; record?: string; note?: string;
  sent: number; days: number; with_outcome: number; without_outcome: number; first?: string | null; last?: string | null; statuses?: [string, number][]; tables: SenderTable[];
}
export interface SenderCards {
  state: 'OK' | 'NOT_BUILT' | 'NOT_LOADED' | 'FAULT' | 'NOT_READ' | string; note: string; terminal_rule: string; cards: SenderCard[];
  rule?: string; as_of?: string; computed?: string | null; snap_state?: string | null; evidence_law?: string; reading?: string;
}

const unk = (v: number | null | undefined, suffix = '') => (v === null || v === undefined ? 'UNKNOWN' : `${v}${suffix}`);
const cnt = (v: number | null | undefined) => (v === null || v === undefined ? '—' : String(v));

function Table({ t, outcomeIs }: { t: SenderTable; outcomeIs?: string }) {
  const ea = t.kind === 'ea';
  return (
    <div style={{ marginTop: 6 }}>
      <div className="dim" style={{ fontSize: 11 }}><b>{t.title}</b>{ea ? <span> · a "win" on these lines is the EA's own word — {outcomeIs || 'see the card'}. <b>Not the money a position made.</b></span> : null}</div>
      <table className="grid" style={{ width: 'auto' }} data-testid="sender-table">
        <thead><tr><th>Line</th><th>Sent</th>{ea && <><th>Filled</th><th>No fill</th><th>Running</th><th>False break</th></>}
          <th title="rows with an outcome — the sample this line's rate is counted on">n</th><th>Wins</th><th>Losses</th><th>Flat</th>
          <th title={ea ? 'share of n whose price reached the first target — the EA\'s own record, not money' : 'share of n that won'}>Win %</th>
          <th title="SignalMesh's interval for the win rate (Wilson)">Interval</th>
          <th title="the average PLANNED reward ÷ risk of these rows — a plan, not a result">Planned R:R</th>
          <th title="the win rate at which the PLANNED reward ÷ risk earns nothing — a plan, never a measured break-even">Planned break-even</th>
          <th title="SignalMesh's Evidence Law word for this n">Evidence</th><th>SignalMesh's reading</th></tr></thead>
        <tbody>{t.rows.map((r) => (
          <tr key={r.label} data-testid="sender-row">
            <td><b>{r.label}</b></td><td className="mono">{r.sent}</td>
            {ea && <><td className="mono">{cnt(r.filled)}</td><td className="mono">{cnt(r.no_fill)}</td><td className="mono">{cnt(r.running)}</td><td className="mono">{cnt(r.false_break)}</td></>}
            <td className="mono"><b>{r.n}</b></td><td className="mono">{r.wins}</td><td className="mono">{r.losses}</td><td className="mono">{r.flat}</td>
            <td className="mono">{unk(r.win_rate, ' %')}</td>
            <td className="mono">{r.ci ? `${r.ci[0]} – ${r.ci[1]} %` : 'UNKNOWN'}</td>
            <td className="mono">{r.avg_rr === null || r.avg_rr === undefined ? 'UNKNOWN' : `1:${r.avg_rr}`}</td>
            <td className="mono">{r.planned_be === null || r.planned_be === undefined ? 'UNKNOWN' : `${r.planned_be} % planned`}</td>
            <td><b>{r.evidence}</b></td><td className="ov-wrap dim">{r.reading}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

export default function SenderCardsView({ s }: { s?: SenderCards }) {
  if (!s) return <div className="note" data-testid="sender-cards-state">Sender cards: NOT AVAILABLE — this terminal build's adapter sent none.</div>;
  if (s.state !== 'OK') return <div className="note warn" data-testid="sender-cards-state"><b>{s.state.replace('_', ' ')}</b> — {s.note}</div>;
  return (
    <div data-testid="sender-cards">
      <div className="dim" style={{ margin: '4px 0' }} title={s.terminal_rule}><b>By sender — SignalMesh's own cards ({s.rule || 'rule not stated'})</b> · {s.reading}
        {s.computed ? ` · counted ${s.computed} ago` : ''}{s.snap_state ? ` · ${s.snap_state}` : ''}. There is no rate per sender and no pooled rate: each line is its own sample.</div>
      {s.evidence_law ? <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>{s.evidence_law}</div> : null}
      {s.cards.map((c) => (
        <div className="card" key={c.id} data-testid="sender-card" style={{ marginBottom: 8 }}>
          <h4>{c.name} <span className="pill muted" style={{ float: 'right' }}>{c.state}</span></h4>
          <div className="dim" style={{ fontSize: 11 }}>sent {c.sent} on {c.days} day(s) · with an outcome {c.with_outcome} · without {c.without_outcome}
            {c.statuses?.length ? ` · ${c.statuses.map(([k, v]) => `${k} ${v}`).join(' · ')}` : ''}</div>
          {c.judged_by ? <div className="dim" style={{ fontSize: 11 }}>judged by: {c.judged_by}</div> : null}
          {c.outcome_is ? <div className="dim" style={{ fontSize: 11 }}>what an outcome is: {c.outcome_is}</div> : null}
          {c.note ? <div className="dim" style={{ fontSize: 11 }}>{c.note}</div> : null}
          {c.tables.length ? c.tables.map((t) => <Table key={t.title} t={t} outcomeIs={c.outcome_is} />) : <div className="muted" style={{ marginTop: 4 }}>{c.state === 'NEVER POSTED' ? 'no row has arrived from this sender' : 'no table on this card'}</div>}
        </div>))}
    </div>
  );
}
