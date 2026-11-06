import type { Coverage, DecisionView, Health, MarketWatchRow } from '../api/types';
import { fmtAge, fmtHM, px, sourceTone, sourceWord, toneOf } from '../util';

interface Props {
  health: Health | null; healthErr: string; symbols: string[]; symbol: string; onSymbol: (s: string) => void;
  tf: string; onTf: (t: string) => void; row: MarketWatchRow | undefined; decision: DecisionView | null; coverage: Coverage | null;
  portfolio: { accounts?: number; online?: number } | null; onLogout?: () => void;
}

export default function TopBar({ health, healthErr, symbols, symbol, onSymbol, tf, onTf, row, decision, coverage, portfolio, onLogout }: Props) {
  const cov = (t: string) => coverage?.symbol === symbol ? coverage.timeframes.find((r) => r.tf === t) : undefined;
  const up = health?.upstream;
  const dataState = healthErr ? 'ADAPTER DOWN' : !health ? '…' : !health.provider.configured ? 'NO API KEY' : up?.reachable ? (up.ok ? 'CONNECTED' : 'UPSTREAM NOT READY') : 'UPSTREAM DOWN';
  // THE HEADER PRICE IS THE SELECTED SYMBOL'S OWN: decision.price.last_closed_1m is fetched per
  // symbol, cleared when the symbol changes, and guarded against late answers. The market-watch
  // row (`row`) is a different request and is used only as a fallback while the decision loads.
  const own = decision && decision.symbol === symbol ? decision.price.last_closed_1m : null;
  const price = own ? own.price : null;
  const dec = decision?.decimals ?? row?.decimals ?? 2;
  const fresh = own ? own.freshness.state : 'UNKNOWN';
  const session = decision?.session || '—';
  const exch = decision?.exchanges ?? [];
  const since = own?.since_close_min;
  const chg = decision?.session_change_pct ?? null;
  return (
    <div className="topbar">
      <span className="brand">SIGNALMESH · TERMINAL</span>
      <select value={symbol} onChange={(e) => onSymbol(e.target.value)} aria-label="Symbol">
        {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <span className="pricebox" title={`price-contract-v1 · ${symbol} · last CLOSED 1m bar · ${own?.source || 'loading'}`} data-symbol={symbol}>
        <span className="mono price" data-testid="header-price">{own ? px(price, dec) : '…'}</span>
        <span className="pricemeta">
          <span className="dim">{own ? <>LAST CLOSE 1m · bar {fmtHM(own.bar_open_ts)}–{fmtHM(own.bar_close_ts)} UTC · closed {since != null ? fmtAge(Math.max(since, 0)) + ' ago' : '—'}{chg != null ? <> · session <b className={chg >= 0 ? 'good' : 'bad'}>{chg > 0 ? '+' : ''}{chg.toFixed(2)}%</b></> : null}</> : `loading ${symbol}…`}</span>
          <span className="dim">bid/ask: n/a (SignalMesh stores no quotes; prices are closed bars)</span>
        </span>
      </span>
      <span className={`pill ${toneOf(fresh)}`} title={own?.freshness.detail || ''}>{fresh}</span>
      <span className={`pill ${sourceTone(own?.source_kind)}`} title={own?.source_warning || own?.source}>{sourceWord(own?.source_kind)}</span>
      <span className="muted" title={exch.map((e) => `${e.name} ${e.state}${e.holiday_note ? ' · ' + e.holiday_note : ''}`).join('\n')}>session <b className="accent">{session}</b>{exch.length ? <span className="dim"> · open: {exch.filter((e) => e.state === 'ACTIVE').map((e) => e.name).join(', ') || 'none'}</span> : null}</span>
      <span style={{ flex: 1 }} />
      <span className="dim">TF</span>
      {(health?.timeframes ?? ['1m', '5m', '15m', '30m', '1h', '4h', '1d']).map((t) => {
        const c = cov(t); const missing = c ? !c.stored : false;
        return <button key={t} className={(t === tf ? 'on' : '') + (missing ? ' tf-missing' : '')} onClick={() => onTf(t)}
          title={missing ? `SignalMesh stores no ${t} candles for ${symbol} (the MT5 reporter does not push this timeframe)` : c ? `${c.state} · newest bar ${c.last_ts ?? '—'}` : ''}>{t.toUpperCase()}</button>;
      })}
      <span className={`pill ${toneOf(dataState === 'CONNECTED' ? 'LIVE' : 'DOWN')}`} title={up?.error || health?.provider.url || ''}>DATA {dataState}</span>
      <span className={`pill ${portfolio?.online ? 'good' : 'muted'}`} title="MT5 accounts reporting heartbeats to SignalMesh">
        MT5 {portfolio ? `${portfolio.online ?? 0}/${portfolio.accounts ?? 0} online` : '—'}
      </span>
      <span className="pill warn" title={health?.execution.phase}>EXEC {health?.execution.can_place ? 'ARMED' : 'DISABLED'} · MANUAL</span>
      {onLogout && <button onClick={onLogout} title="forget the terminal token">lock</button>}
    </div>
  );
}
