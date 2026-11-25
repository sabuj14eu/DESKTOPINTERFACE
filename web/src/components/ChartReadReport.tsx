import { useState } from 'react';
import type { ChartReadData, CrSide } from '../chartread';
import { fmtTs } from '../util';

// THE CHART READ TABLE — read-only. Every value comes from /chart-read; every row names where it comes from.
const tone = (t: string) => (t === 'good' ? 'good' : t === 'bad' ? 'bad' : t === 'warn' ? 'warn' : t === 'dim' ? 'dim' : '');
const stTone: Record<string, string> = { CONFIRMED: 'good', FAILED: 'bad', WAITING: 'warn', 'NOT APPLICABLE': 'dim' };

function Side({ name, s }: { name: 'SELL' | 'BUY'; s: CrSide }) {
  return (
    <div className={`scen ${name === 'BUY' ? 'bullish' : 'bearish'}`} data-testid={`cr-cond-${name.toLowerCase()}`}>
      <div><b className={name === 'BUY' ? 'good' : 'bad'}>{name} conditions {s.confirmed}/{s.of}</b> · weight {s.weight}/{s.weight_of} · structural (BOS, CHoCH, rejection) {s.structural}/3</div>
      <table className="grid sr"><tbody>
        {s.conditions.map((c) => <tr key={c.name}><td>{c.name.toUpperCase()} <span className="dim">×{c.weight}</span></td><td className={stTone[c.status]}><b>{c.status}</b></td>
          <td className="dim">{c.reason}{c.bar_utc ? ` · bar ${fmtTs(c.bar_utc)}` : ''}</td></tr>)}
      </tbody></table>
    </div>
  );
}

export function ChartReadMethod({ data, onClose }: { data: ChartReadData | null; onClose: () => void }) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal about" onClick={(e) => e.stopPropagation()} data-testid="cr-method-panel">
        <div style={{ display: 'flex', alignItems: 'center' }}><h3 style={{ margin: 0 }}>Chart read — what it is and how it is made</h3><span style={{ flex: 1 }} /><button onClick={onClose}>✕</button></div>
        <p className="warn" style={{ fontSize: 12 }}>A read of CLOSED bars for you: one table and chart labels. It is not a signal and not SignalMesh engine output. It produces no BUY / SELL, changes no SignalMesh decision, is not recorded, and places no order. The condition count says which conditions are met on closed bars; it is not an instruction to trade.</p>
        {data ? <div className="kv wide">{Object.entries(data.methodology).map(([k, v]) => <span key={k} style={{ display: 'contents' }}><span className="k">{k.replace(/_/g, ' ')}</span><span>{v}</span></span>)}
          <span className="k">TradingView</span><span>{data.note_tradingview}</span>
          <span className="k">closed bars used</span><span>{data.bars_used} {data.tf} bars through {fmtTs(data.through_close_utc)} · {data.source}</span></div>
          : <div className="dim">switch Chart read on to load the method text</div>}
      </div>
    </div>
  );
}

export default function ChartReadReport({ data, symbol, tf }: { data: ChartReadData | null; symbol: string; tf: string }) {
  const [detail, setDetail] = useState(false);
  const d = data && data.symbol === symbol && data.tf === tf ? data : null;
  if (!d) return <section data-testid="cr-report"><h5>CHART READ · {symbol}</h5><div className="dim">loading…</div></section>;
  if (d.state !== 'OK') return <section data-testid="cr-report"><h5>CHART READ · {symbol} · {tf}</h5><div className="warn" data-testid="cr-state">NOT AVAILABLE — {d.note}</div></section>;
  return (
    <section data-testid="cr-report">
      <h5>CHART READ · {symbol} {tf} <span className="dim">· closed bars through {fmtTs(d.through_close_utc)} · a read, not a signal</span></h5>
      {d.freshness && d.freshness.state !== 'LIVE' && <div className="scen bearish" data-testid="cr-stale"><b className="bad">DATA {d.freshness.state}</b> — the newest closed bar ended {fmtTs(d.through_close_utc)}. This is the last known picture, not a live market; nothing here is a current condition.</div>}
      <table className="grid sr" data-testid="cr-table"><tbody>
        {d.rows.map((r) => <tr key={r.key} title={`${r.note} · source: ${r.source}`}><td>{r.label}</td><td className={tone(r.tone)}><b>{r.value}</b></td></tr>)}
      </tbody></table>
      <div><button onClick={() => setDetail((v) => !v)} data-testid="cr-detail-toggle">{detail ? '▾' : '▸'} why — every condition with its reason</button></div>
      {detail && d.conditions && <><Side name="SELL" s={d.conditions.SELL} /><Side name="BUY" s={d.conditions.BUY} /></>}
      <div className="dim" style={{ fontSize: 10 }}>Hover a row for how it was read and which study it comes from (smc-v1, daily-forecast-v1, the SignalMesh engine, or chart-read-v1). {d.note_tradingview}. Not recorded; not an instruction to trade.</div>
    </section>
  );
}
