import type { AccountView, Accounts, Coverage, DecisionView, Health, LiveBars, MarketWatchRow } from '../api/types';
import { fmtAge, fmtHM, px, sourceTone, sourceWord, tfLabel, toneOf } from '../util';
import type { Workspace } from '../workspace';
import AccountSelector from './AccountSelector';
import VersionBadge from './VersionBadge';

interface Props {
  health: Health | null; healthErr: string; symbols: string[]; symbol: string; onSymbol: (s: string) => void;
  tf: string; onTf: (t: string) => void; row: MarketWatchRow | undefined; decision: DecisionView | null; coverage: Coverage | null; live?: LiveBars | null;
  accounts: Accounts | null; accountsErr: string; account: AccountView | null; onAccount: (id: string) => void;
  ws: Workspace; onToggle: (side: 'left' | 'right' | 'bottom') => void; onFull: () => void; onReset: () => void; mobile: boolean; onLogout?: () => void;
}

export default function TopBar({ health, healthErr, symbols, symbol, onSymbol, tf, onTf, row, decision, coverage, live, accounts, accountsErr, account, onAccount, ws, onToggle, onFull, onReset, mobile, onLogout }: Props) {
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
  const on = (side: 'left' | 'right' | 'bottom') => !ws.full && ws[side].open;
  return (
    <div className="topbar">
      <div className="bar-row">
        <VersionBadge build={health?.build} compact={mobile} />
        <select value={symbol} onChange={(e) => onSymbol(e.target.value)} aria-label="Symbol">
          {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        {live && live.state === 'LIVE' && live.bars.length > 0 && (() => { const b = live.bars[live.bars.length - 1]; const px0 = live.bid ?? b.close; return (
          <span className="livebox" data-testid="live-price" title={`${live.rule}`}>
            <span className={`mono liveprice ${b.close >= b.open ? 'good' : 'bad'}`}>{px(px0, dec)}</span>
            <span className="pricemeta"><span className="livetag">● LIVE</span><span className="dim hide-s">{live.bid != null && live.ask != null ? `bid ${px(live.bid, dec)} · ask ${px(live.ask, dec)}` : 'forming bar close'} · bridge · display only</span></span>
          </span>); })()}
        <span className="pricebox" title={`price-contract-v1 · ${symbol} · last CLOSED 1m bar · ${own?.source || 'loading'}`} data-symbol={symbol}>
          <span className="mono price" data-testid="header-price">{own ? px(price, dec) : '…'}</span>
          <span className="pricemeta">
            <span className="dim">{own ? <>LAST CLOSE 1m · bar {fmtHM(own.bar_open_ts)}–{fmtHM(own.bar_close_ts)} UTC · closed {since != null ? fmtAge(Math.max(since, 0)) + ' ago' : '—'}{chg != null ? <> · session <b className={chg >= 0 ? 'good' : 'bad'}>{chg > 0 ? '+' : ''}{chg.toFixed(2)}%</b></> : null}</> : `loading ${symbol}…`}</span>
            <span className="dim hide-s">{live?.state === 'LIVE' ? 'the engine decides on closed bars; the live price is display only' : live?.state === 'FROM_1M' ? 'no live quote: forming bar built from closed 1m bars' : 'bid/ask: n/a (SignalMesh stores no quotes; prices are closed bars)'}</span>
          </span>
        </span>
        <span className={`pill ${toneOf(fresh)}`} title={own?.freshness.detail || ''}>{fresh}</span>
        <span className={`pill ${sourceTone(own?.source_kind)} hide-s`} title={own?.source_warning || own?.source}>{sourceWord(own?.source_kind)}</span>
        <span className="muted hide-s" title={exch.map((e) => `${e.name} ${e.state}${e.holiday_note ? ' · ' + e.holiday_note : ''}`).join('\n')}>session <b className="accent">{session}</b>{exch.length ? <span className="dim"> · open: {exch.filter((e) => e.state === 'ACTIVE').map((e) => e.name).join(', ') || 'none'}</span> : null}</span>
        <span style={{ flex: 1 }} />
        <AccountSelector data={accounts} error={accountsErr} selected={account} onSelect={onAccount} />
        {onLogout && <button onClick={onLogout} title="forget the terminal token">lock</button>}
      </div>
      <div className="bar-row tools">
        <span className="tf-group" role="group" aria-label="Timeframe">
          {(health?.timeframes ?? ['1m', '5m', '15m', '30m', '1h', '4h', '1d']).map((t) => {
            const c = cov(t); const missing = c ? !c.stored : false;
            return <button key={t} className={(t === tf ? 'on' : '') + (missing ? ' tf-missing' : '')} onClick={() => onTf(t)}
              title={missing ? `SignalMesh stores no ${tfLabel(t)} candles for ${symbol} (the MT5 reporter does not push this timeframe)` : c ? `${c.state} · newest bar ${c.last_ts ?? '—'}` : ''}>{tfLabel(t)}</button>;
          })}
        </span>
        {!mobile && <>
          <span className={`pill ${toneOf(dataState === 'CONNECTED' ? 'LIVE' : 'DOWN')}`} title={up?.error || health?.provider.url || ''}>DATA {dataState}</span>
          <span className="pill warn" title={`${health?.execution.phase ?? ''} — no order can be sent from this terminal`}>EXEC {health?.execution.can_place ? 'ARMED' : 'DISABLED'}</span>
          <span style={{ flex: 1 }} />
          <span className="tool-group" role="group" aria-label="Workspace">
            <button className={on('left') ? 'on' : ''} onClick={() => onToggle('left')} data-testid="toggle-left" title="show / hide Market Watch (Ctrl+M)">◧ Market Watch</button>
            <button className={on('right') ? 'on' : ''} onClick={() => onToggle('right')} data-testid="toggle-right" title="show / hide the SignalMesh decision panel (Ctrl+D)">◨ Decision</button>
            <button className={on('bottom') ? 'on' : ''} onClick={() => onToggle('bottom')} data-testid="toggle-bottom" title="show / hide the Toolbox (Ctrl+T)">⬓ Toolbox</button>
            <button className={ws.full ? 'on' : ''} onClick={onFull} data-testid="toggle-full" title="full-screen chart (F) · Esc to leave">⤢ Full screen</button>
            <button onClick={onReset} data-testid="reset-layout" title="restore the default layout: all panels shown at their original sizes">↺ Reset layout</button>
          </span>
        </>}
      </div>
    </div>
  );
}
