import type { DecisionView, Health, MarketWatchRow } from '../api/types';
import { fmtAge, fmtTs, px, toneOf } from '../util';

interface Props {
  health: Health | null; healthErr: string; symbols: string[]; symbol: string; onSymbol: (s: string) => void;
  tf: string; onTf: (t: string) => void; row: MarketWatchRow | undefined; decision: DecisionView | null;
  portfolio: { accounts?: number; online?: number } | null; onLogout?: () => void;
}

export default function TopBar({ health, healthErr, symbols, symbol, onSymbol, tf, onTf, row, decision, portfolio, onLogout }: Props) {
  const up = health?.upstream;
  const dataState = healthErr ? 'ADAPTER DOWN' : !health ? '…' : !health.provider.configured ? 'NO API KEY' : up?.reachable ? (up.ok ? 'CONNECTED' : 'UPSTREAM NOT READY') : 'UPSTREAM DOWN';
  const fresh = row?.freshness.state ?? 'UNKNOWN';
  const session = decision?.session || '—';
  const exch = decision?.exchanges ?? [];
  return (
    <div className="topbar">
      <span className="brand">SIGNALMESH · TERMINAL</span>
      <select value={symbol} onChange={(e) => onSymbol(e.target.value)} aria-label="Symbol">
        {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <span className="mono price">{px(row?.price, row?.decimals ?? 2)}</span>
      <span className={`pill ${toneOf(fresh)}`} title={row?.freshness.detail || ''}>{fresh}{row?.age_min != null ? ` · ${fmtAge(row.age_min)}` : ''}</span>
      <span className="dim" title={row?.source}>last closed {row?.price_tf ?? '1m'} bar · {fmtTs(row?.price_ts)}</span>
      <span className="muted" title={exch.map((e) => `${e.name} ${e.state}${e.holiday_note ? ' · ' + e.holiday_note : ''}`).join('\n')}>session <b className="accent">{session}</b>{exch.length ? <span className="dim"> · exchanges open: {exch.filter((e) => e.state === 'ACTIVE').map((e) => e.name).join(', ') || 'none'}</span> : null}</span>
      <span style={{ flex: 1 }} />
      <span className="dim">TF</span>
      {(health?.timeframes ?? ['1m', '5m', '15m', '30m', '1h', '4h', '1d']).map((t) => (
        <button key={t} className={t === tf ? 'on' : ''} onClick={() => onTf(t)}>{t.toUpperCase()}</button>
      ))}
      <span className={`pill ${toneOf(dataState === 'CONNECTED' ? 'LIVE' : 'DOWN')}`} title={up?.error || health?.provider.url || ''}>DATA {dataState}</span>
      <span className={`pill ${portfolio?.online ? 'good' : 'muted'}`} title="MT5 accounts reporting heartbeats to SignalMesh">
        MT5 {portfolio ? `${portfolio.online ?? 0}/${portfolio.accounts ?? 0} online` : '—'}
      </span>
      <span className="pill warn" title={health?.execution.phase}>EXEC {health?.execution.can_place ? 'ARMED' : 'DISABLED'} · MANUAL</span>
      {onLogout && <button onClick={onLogout} title="forget the terminal token">lock</button>}
    </div>
  );
}
