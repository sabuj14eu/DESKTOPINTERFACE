import type { MarketWatchRow } from '../api/types';
import { fmtAge, pct, px, toneOf } from '../util';

export default function MarketWatch({ rows, selected, onSelect, error, rule }: { rows: MarketWatchRow[]; selected: string; onSelect: (s: string) => void; error: string; rule: string }) {
  return (
    <div className="watch">
      <div className="section-title">Market watch</div>
      {error && <div className="note bad">{error}</div>}
      <table className="grid">
        <thead><tr><th>Symbol</th><th style={{ textAlign: 'right' }}>Last</th><th style={{ textAlign: 'right' }}>Chg</th><th>Signal</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol} className={'row' + (r.symbol === selected ? ' sel' : '')} onClick={() => onSelect(r.symbol)} title={r.error || r.source}>
              <td><b>{r.symbol}</b><div className="dim" style={{ fontSize: 10 }}>bias <span className={toneOf(r.bias)}>{r.bias ?? 'UNKNOWN'}</span></div></td>
              <td className="mono" style={{ textAlign: 'right' }}>{px(r.price, r.decimals)}
                <div className={toneOf(r.freshness.state)} style={{ fontSize: 10 }} title={r.freshness.detail}>{r.freshness.state}{r.age_min != null ? ` ${fmtAge(r.age_min)}` : ''}</div></td>
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
