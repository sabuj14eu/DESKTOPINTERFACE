import type { MarketWatchRow } from '../api/types';
import { fmtAge, pct, px, sourceTone, sourceWord, toneOf } from '../util';

export default function MarketWatch({ rows, selected, onSelect, error, rule }: { rows: MarketWatchRow[]; selected: string; onSelect: (s: string) => void; error: string; rule: string }) {
  return (
    <div className="watch">
      <div className="section-title">Market watch · last closed 1m bar</div>
      {error && <div className="note bad">{error}</div>}
      <table className="grid">
        <thead><tr><th>Symbol</th><th style={{ textAlign: 'right' }}>Close 1m</th><th style={{ textAlign: 'right' }}>Chg</th><th>BUY/SELL</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol} className={'row' + (r.symbol === selected ? ' sel' : '')} onClick={() => onSelect(r.symbol)} title={r.error || r.source_warning || r.source}>
              <td><b>{r.symbol}</b><div className="dim" style={{ fontSize: 10 }}>bias <span className={toneOf(r.bias)}>{r.bias ?? 'UNKNOWN'}</span></div>
                <div className={sourceTone(r.source_kind)} style={{ fontSize: 9, fontWeight: 700 }}>{sourceWord(r.source_kind)}</div></td>
              <td className="mono" style={{ textAlign: 'right' }}>{px(r.price, r.decimals)}
                <div className={toneOf(r.freshness.state)} style={{ fontSize: 10 }} title={r.freshness.detail}>{r.freshness.state}{r.since_close_min != null ? ` · closed ${fmtAge(Math.max(r.since_close_min, 0))} ago` : ''}</div></td>
              <td className={`mono ${r.change_pct == null ? 'dim' : r.change_pct >= 0 ? 'good' : 'bad'}`} style={{ textAlign: 'right' }} title={r.change_basis}>{pct(r.change_pct)}</td>
              <td>
                <span className={`pill ${toneOf(r.summary)}`}>{r.summary}</span>
                {r.direction && <div className={toneOf(r.direction)} style={{ fontSize: 10, fontWeight: 700 }}>{r.direction}</div>}
                {r.error && <div className="bad" style={{ fontSize: 10 }}>ERR</div>}
              </td>
            </tr>
          ))}
          {!rows.length && !error && <tr><td colSpan={4} className="dim">loading…</td></tr>}
        </tbody>
      </table>
      <div className="note">{rule}</div>
    </div>
  );
}
