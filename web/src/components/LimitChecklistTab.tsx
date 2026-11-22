import { api } from '../api/client';
import { fmtTs, px, usePoll } from '../util';

// LIMIT CHECKLIST (limit-checklist-v1) — Shyam's seven-step checklist for a pending limit order, read by the terminal on
// SignalMesh's stored CLOSED daily and 4h bars. A terminal study, display only: NOT a signal, not recorded, not SignalMesh
// engine output, and nothing here can be pressed. Every price is a HYPOTHETICAL ANALYSIS LEVEL.
export interface LcStep { n: number; name: string; status: string; text: string }
export interface LcLevel { zone_kind?: string; name: string; value: number; bar_utc?: string | null }
export interface LcPlan { price: number; price_basis: string; atr_4h: number | null; side: string; order_type: string; zone_low?: number; zone_high?: number; zone_levels?: LcLevel[];
  entry?: number; sl?: number; risk_per_unit?: number; entry_distance_r?: number | null; tp1?: number; tp2?: number; rr1?: number | null; rr2?: number | null; tp1_level?: LcLevel; tp2_level?: LcLevel }
export interface LimitChecklist {
  symbol: string; state: 'OK' | 'NOT_AVAILABLE' | 'SERIES_FAULT'; note: string; kind: string; method_version: string; methodology: Record<string, string>; recorded: boolean; source: string;
  daily_bars: number; h4_bars: number; side: 'SELL' | 'BUY' | null; verdict: string; verdict_why: string; steps: LcStep[]; plan: LcPlan | null;
  averages: { ema50: number; ema100: number; ema200: number; daily_close: number } | null; calculated_at: string; through_daily_utc: string | null; through_h4_utc: string | null;
  level_label: string; decimals: number; freshness?: { state: string }; market_status?: { open?: boolean; why?: string; reopens_in?: string } | null;
}

// a step's own colour: what was measured, never a call to trade
const tone = (s: string) => (s === 'PASS' ? 'good' : s === 'FAIL' ? 'bad' : s === 'WAIT' || s === 'MIXED' ? 'warn' : 'dim');

export function LimitChecklistView({ d }: { d: LimitChecklist }) {
  const dec = d.decimals; const p = d.plan;
  const closed = d.market_status?.open === false;
  return (
    <div data-testid="limit-checklist" data-symbol={d.symbol}>
      <div className="wall study"><span className="tag">TERMINAL STUDY · NOT A SIGNAL</span> A checklist for a pending limit order, read on closed daily and 4h bars. It shows; it does not tell you to trade. Nothing is recorded and no order is placed.</div>
      <div className="ov-body">
        <div className="card ov-plain">
          <b>In plain words.</b> This runs your seven steps on {d.symbol}, one line per step, and shows the prices the steps themselves give. <b>PASS</b> means the step holds on the stored bars.
          <b> WAIT</b> means not yet. <b>FAIL</b> means the checklist says skip. It was not tested against results, so it is a checklist made visible, <b>not a signal</b>.
          <div className="dim" style={{ marginTop: 3 }}><b>R</b> = the distance from the entry to the stop; "1:2" means the target is two of those away. <b>EMA</b> = an average of closes that follows price; the 50, 100 and 200-day ones are used here.
            <b> ATR</b> = the usual size of one bar. Every price below is a {d.level_label}.</div>
        </div>
        {d.state !== 'OK' ? <div className="ov-neutral" data-testid="lc-state"><b>{d.state === 'SERIES_FAULT' ? 'SERIES FAULT' : 'NOT AVAILABLE'}</b> — {d.note}.</div> : <>
          {closed ? <div className="ov-neutral" data-testid="lc-closed"><b>MARKET CLOSED</b> — {d.market_status?.why}{d.market_status?.reopens_in ? ` · reopens in ${d.market_status.reopens_in}` : ''}. This is the last stored picture; a pending order cannot fill until the market opens.</div> : null}
          <div className="card" data-testid="lc-verdict">
            <h4>{d.symbol} · {d.side ? `checklist for a pending ${d.side} LIMIT` : 'no side'}</h4>
            <div className="ov-word" data-testid="lc-word">{d.verdict}</div>
            <div className="muted">{d.verdict_why}</div>
            <div className="dim" style={{ marginTop: 3, fontSize: 11 }}>closed bars read: {d.daily_bars} daily through {fmtTs(d.through_daily_utc)} · {d.h4_bars} 4h through {fmtTs(d.through_h4_utc)}</div>
          </div>
          <table className="grid" data-testid="lc-steps">
            <thead><tr><th>Step</th><th>Reads</th><th>What the stored bars say</th></tr></thead>
            <tbody>{d.steps.map((s) => <tr key={s.n}><td><b>{s.n} · {s.name}</b></td><td><b className={tone(s.status)}>{s.status}</b></td><td className="ov-wrap" style={{ maxWidth: 900 }}>{s.text}</td></tr>)}</tbody>
          </table>
          {p && p.entry != null ? <div className="card" data-testid="lc-plan" style={{ marginTop: 8 }}>
            <h4>The levels the checklist gives — {d.level_label}s, not an order</h4>
            <div>
              {[['Price now', p.price], ['Entry (limit)', p.entry], ['Stop', p.sl], ['TP1', p.tp1], ['TP2', p.tp2]].map(([k, v]) => <span className="stat" key={String(k)}><span className="k">{k}</span><span className={`v ${v == null ? 'na' : ''}`}>{v == null ? 'NOT AVAILABLE' : px(v as number, dec)}</span></span>)}
              <span className="stat"><span className="k">TP1 / TP2 reward</span><span className="v">{p.rr1 != null ? `1:${p.rr1}` : '—'} / {p.rr2 != null ? `1:${p.rr2}` : '—'}</span></span>
              <span className="stat"><span className="k">Entry from price</span><span className="v">{p.entry_distance_r != null ? `${p.entry_distance_r}R` : '—'}</span></span>
            </div>
            <div className="muted">Zone {px(p.zone_low, dec)} – {px(p.zone_high, dec)}: {(p.zone_levels ?? []).map((l) => `${l.zone_kind} (${l.name} ${px(l.value, dec)})`).join(' + ')}</div>
            <div className="dim" style={{ fontSize: 11 }}>{p.price_basis} · 4h ATR {px(p.atr_4h, dec)} · risk per unit {px(p.risk_per_unit, dec)}{p.tp1_level ? ` · TP1 before ${p.tp1_level.name} ${px(p.tp1_level.value, dec)}` : ''}{p.tp2_level ? ` · TP2 before ${p.tp2_level.name} ${px(p.tp2_level.value, dec)}` : ''}</div>
          </div> : null}
          {d.averages ? <div className="dim" style={{ fontSize: 11, marginTop: 4 }}>daily close {px(d.averages.daily_close, dec)} · EMA50 {px(d.averages.ema50, dec)} · EMA100 {px(d.averages.ema100, dec)} · EMA200 {px(d.averages.ema200, dec)} — the same averages can be drawn on the chart: indicators menu, on the D1 timeframe.</div> : null}
        </>}
        <details style={{ marginTop: 6 }}><summary className="dim" style={{ cursor: 'pointer' }}>how each step is read</summary>
          <div className="kv wide" style={{ marginTop: 4 }}>{Object.entries(d.methodology).map(([k, v]) => <span key={k} style={{ display: 'contents' }}><span className="k">{k.replace(/_/g, ' ')}</span><span>{v}</span></span>)}</div></details>
        <div className="dim ov-foot">{d.method_version} · {d.kind} · {d.source} · calculated {fmtTs(d.calculated_at)} · not recorded · not an instruction to trade.</div>
      </div>
    </div>
  );
}

export default function LimitChecklistTab({ symbol, pollMs }: { symbol: string; pollMs: number }) {
  const { data, error } = usePoll(() => api.limitChecklist(symbol), Math.max(pollMs * 4, 60_000), [symbol]);
  if (error) return <div className="note bad" data-testid="lc-error">The limit checklist could not be read: {error}</div>;
  if (!data || data.symbol !== symbol) return <div className="note">loading the limit checklist…</div>;
  return <LimitChecklistView d={data} />;
}
