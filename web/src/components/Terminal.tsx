import { useState } from 'react';
import { api } from '../api/client';
import type { AccountDetail, AccountView, Accounts, BrokerRow, SignalRef, TradeRow } from '../api/types';
import { fmtAge, fmtTs, money, orNA, px, sourceTone, sourceWord, toneOf, usePoll } from '../util';
import { EnvBadge, typeLabel } from './AccountSelector';
import JournalTab from './JournalTab';

export const TABS = ['Active Signals', 'Pending Setups', 'Open Positions', 'Pending Orders', 'Trade History', 'Performance', 'News & Events', 'Data Sources', 'Account Information', 'Forecast Journal', 'System Health'] as const;
export type Tab = typeof TABS[number];
// which side of the wall each tab is on: SignalMesh's recommendations, the broker's own records, or the terminal's own studies
const SIDE: Record<Tab, 'signal' | 'broker' | 'info' | 'study'> = { 'Active Signals': 'signal', 'Pending Setups': 'signal', 'Open Positions': 'broker', 'Pending Orders': 'broker',
  'Trade History': 'broker', Performance: 'info', 'News & Events': 'info', 'Data Sources': 'info', 'Account Information': 'broker', 'Forecast Journal': 'study', 'System Health': 'info' };

interface Props {
  symbol: string; pollMs: number; signals: SignalRef[]; signalsErr: string; tab: string; onTab: (t: Tab) => void; onSignal: (id: string) => void; onHide?: () => void;
  accounts: Accounts | null; account: AccountView | null; detail: AccountDetail | null; detailErr: string;
}

export default function Terminal({ symbol, pollMs, signals, signalsErr, tab: tabIn, onTab, onSignal, onHide, accounts, account, detail, detailErr }: Props) {
  const tab: Tab = (TABS as readonly string[]).includes(tabIn) ? (tabIn as Tab) : 'Active Signals';
  const d = detail && detail.account?.id === account?.id ? detail : null;
  const count: Partial<Record<Tab, number>> = { 'Active Signals': signals.filter((s) => s.bucket === 'ACTIVE').length, 'Pending Setups': signals.filter((s) => s.bucket === 'PENDING').length,
    'Open Positions': d?.positions.length, 'Pending Orders': d?.orders.length };
  return (
    <div className="bottom" data-testid="toolbox">
      <div className="tabbody">
        {tab === 'Active Signals' && <><Wall side="signal">SignalMesh recommendations — approved or executed by the engine within 12h. <b>Not broker orders.</b> Click a row for its origin and how far it really got.</Wall>
          <SignalTable rows={signals.filter((s) => s.bucket === 'ACTIVE')} err={signalsErr} onSignal={onSignal} empty="no ACTIVE signal (approved/executed within 12h) — the engine has nothing current" /></>}
        {tab === 'Pending Setups' && <PendingTab signals={signals} err={signalsErr} symbol={symbol} pollMs={pollMs} onSignal={onSignal} />}
        {tab === 'Open Positions' && <BrokerRows kind="position" account={account} detail={d} err={detailErr} />}
        {tab === 'Pending Orders' && <BrokerRows kind="order" account={account} detail={d} err={detailErr} />}
        {tab === 'Trade History' && <TradesTab pollMs={pollMs} signals={signals} signalsErr={signalsErr} onSignal={onSignal} />}
        {tab === 'Performance' && <PerformanceTab pollMs={pollMs} />}
        {tab === 'News & Events' && <NewsTab symbol={symbol} pollMs={pollMs} />}
        {tab === 'Data Sources' && <SourcesTab pollMs={pollMs} />}
        {tab === 'Account Information' && <AccountTab accounts={accounts} account={account} detail={d} err={detailErr} />}
        {tab === 'Forecast Journal' && <JournalTab pollMs={pollMs} />}
        {tab === 'System Health' && <SystemTab pollMs={pollMs} />}
      </div>
      <div className="tabs" role="tablist">
        {TABS.map((t) => <button key={t} role="tab" aria-selected={t === tab} className={(t === tab ? 'on ' : '') + SIDE[t]} onClick={() => onTab(t)}>{t}{count[t] != null ? <span className="cnt">{count[t]}</span> : null}</button>)}
        <span style={{ flex: 1 }} />
        {onHide && <button onClick={onHide} title="hide the Toolbox (Ctrl+T)" aria-label="Hide toolbox">▾ hide</button>}
      </div>
    </div>
  );
}

function Wall({ side, children }: { side: 'signal' | 'broker'; children: React.ReactNode }) {
  return <div className={`wall ${side}`}><span className="tag">{side === 'signal' ? 'SIGNALMESH · RECOMMENDATION' : 'BROKER · ACTUAL'}</span> {children}</div>;
}

/** What SignalMesh's own status says about execution — never more than it says. */
export const execWord = (s: SignalRef) => (s.status === 'executed' || s.status === 'closed' ? `SignalMesh: ${s.status}` : s.status === 'rejected' || s.status === 'cancelled' ? s.status : 'NOT EXECUTED');

function SignalTable({ rows, err, empty, onSignal }: { rows: SignalRef[]; err: string; empty: string; onSignal: (id: string) => void }) {
  if (err) return <div className="note bad">{err}</div>;
  if (!rows.length) return <div className="note">{empty}</div>;
  return (
    <table className="grid" data-testid="signal-table">
      <thead><tr><th>Signal</th><th>Origin</th><th>Symbol</th><th>TF</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP1</th><th>TP2</th><th>R:R</th><th>Grade</th><th>Conf</th><th>Council</th><th>Signal status</th><th>Broker execution</th><th>Age</th><th>Created (UTC)</th></tr></thead>
      <tbody>{rows.map((s) => (
        <tr key={s.signal_id} className="row" onClick={() => onSignal(s.signal_id)} title="open the full signal information">
          <td className="mono accent">{s.signal_id}</td><td>{s.system || <span className="warn">UNKNOWN</span>}</td><td><b>{s.symbol}</b></td><td>{s.tf}</td>
          <td className={toneOf(s.direction)}><b>{s.direction}</b></td>
          <td className="mono">{s.entry ?? '—'}</td><td className="mono">{s.sl ?? '—'}</td><td className="mono">{s.tp1 ?? '—'}</td><td className="mono">{s.tp2 ?? '—'}</td>
          <td className="mono">{s.rr ?? '—'}</td><td>{s.grade || '—'}</td><td>{s.confidence ?? '—'}</td>
          <td>{s.council_total ? `${s.council_approve}/${s.council_total}` : '—'}</td>
          <td><span className={`pill ${toneOf(s.bucket)}`}>{s.status}{s.stale ? ' · EXPIRED' : ''}</span></td>
          <td><span className={`pill ${s.status === 'executed' || s.status === 'closed' ? 'warn' : 'muted'}`} title={s.status === 'executed' || s.status === 'closed' ? "SignalMesh's own status word — open the signal to see whether a broker trade is linked" : 'this is a recommendation; no order was recorded for it'}>{execWord(s)}</span></td>
          <td>{s.age_h != null ? `${s.age_h}h` : '—'}</td><td className="dim">{fmtTs(s.created_at)}</td>
        </tr>))}</tbody>
    </table>
  );
}

function PendingTab({ signals, err, symbol, pollMs, onSignal }: { signals: SignalRef[]; err: string; symbol: string; pollMs: number; onSignal: (id: string) => void }) {
  const { data } = usePoll(() => api.decision(symbol), pollMs, [symbol]);
  const lane = data?.lane;
  return (
    <>
      <Wall side="signal">Setups SignalMesh is still deciding on. <b>Not broker pending orders</b> — those are under Pending Orders.</Wall>
      <div className="note">
        <b>Desk lane candidate ({symbol}, engine {lane?.engine || '?'}):</b> {lane ? <>{lane.decision} · {lane.stage}{lane.reasons.length ? ` · ${lane.reasons.join(', ')}` : ''} — {lane.confirmation_text}
          {lane.entry != null && <> · entry <span className="mono">{px(lane.entry, data?.decimals)}</span> SL <span className="mono">{px(lane.sl, data?.decimals)}</span> TP1 <span className="mono">{px(lane.tp1, data?.decimals)}</span></>}</> : '…'}
        <span className="dim"> · PAPER research — never an executable plan</span>
      </div>
      <SignalTable rows={signals.filter((s) => s.bucket === 'PENDING')} err={err} onSignal={onSignal} empty="no PENDING signal candidate within 12h" />
    </>
  );
}

function AccountLine({ a }: { a: AccountView }) {
  return <><EnvBadge a={a} /> <b>{typeLabel(a)}</b> <span className="mono">{a.login_masked ?? ''}</span>{a.server ? ` · ${a.server}` : ''}</>;
}

function BrokerRows({ kind, account, detail, err }: { kind: 'position' | 'order'; account: AccountView | null; detail: AccountDetail | null; err: string }) {
  const what = kind === 'position' ? 'open positions' : 'pending orders';
  if (!account) return <><Wall side="broker">Actual {what} on the selected broker account.</Wall><div className="note">No broker account is connected, so there are no broker {what} to show. SignalMesh signals are under Active Signals.</div></>;
  const rows: BrokerRow[] = detail ? (kind === 'position' ? detail.positions : detail.orders) : [];
  const src = kind === 'position' ? detail?.positions_source : detail?.orders_source;
  return (
    <>
      <Wall side="broker">Actual {what} on <AccountLine a={account} />. <b>Not SignalMesh signals.</b> <span className="dim">source: {src ?? '…'}</span></Wall>
      {err && <div className="note bad">{err}</div>}
      <table className="grid" data-testid={`broker-${kind}s`}>
        <thead><tr><th>Ticket</th><th>Symbol</th><th>Dir</th>{kind === 'order' && <th>Type</th>}<th>Lots</th><th>{kind === 'position' ? 'Open price' : 'Order price'}</th><th>SL</th><th>TP</th>{kind === 'position' && <th>Floating P/L</th>}<th>{kind === 'position' ? 'Opened (UTC)' : 'Placed (UTC)'}</th><th>Linked signal</th></tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={String(r.ticket ?? i)}><td className="mono">{r.ticket ?? '—'}</td><td><b>{r.symbol}</b></td><td className={toneOf(r.direction)}><b>{r.direction ?? '—'}</b></td>{kind === 'order' && <td>{r.order_type ?? '—'}</td>}
            <td className="mono">{r.lots ?? '—'}</td><td className="mono">{r.entry ?? '—'}</td><td className="mono">{r.sl ?? '—'}</td><td className="mono">{r.tp ?? '—'}</td>
            {kind === 'position' && <td className={`mono ${r.profit == null ? 'dim' : r.profit >= 0 ? 'good' : 'bad'}`}>{r.profit ?? '—'}</td>}
            <td className="dim">{fmtTs(r.time)}</td><td className="mono">{r.signal_id ?? <span className="dim" title="the broker row names no signal">none stated</span>}</td></tr>))}
          {detail && !rows.length && <tr><td colSpan={11} className="dim">no {what} on this account</td></tr>}
          {!detail && !err && <tr><td colSpan={11} className="dim">loading…</td></tr>}
        </tbody>
      </table>
    </>
  );
}

function AccountTab({ accounts, account, detail, err }: { accounts: Accounts | null; account: AccountView | null; detail: AccountDetail | null; err: string }) {
  const off = accounts?.disconnected ?? [];
  if (!account) return (
    <div style={{ padding: '4px 10px' }}>
      <Wall side="broker">Broker-reported account values.</Wall>
      <div className="note"><b>No broker account is connected.</b> {accounts?.note}</div>
      {off.length > 0 && <OfflineTable rows={off} />}
    </div>);
  const a = account; const src = (k: string) => a.field_sources[k] || 'the reporter did not send this field';
  const cell = (label: string, key: keyof AccountView, text: string, tone = '') => (
    <span className="stat" key={label} title={src(String(key))} data-field={String(key)}><span className="k">{label}</span><span className={`v ${a[key] == null ? 'na' : tone}`}>{text}</span></span>);
  const pl = a.floating_pnl;
  return (
    <div style={{ padding: '4px 10px' }} data-testid="account-info">
      <Wall side="broker">Values reported by the broker for <AccountLine a={a} />. <b>Not SignalMesh calculations.</b></Wall>
      {a.combined && <div className="note bad" style={{ fontWeight: 700 }}>{a.notes[0]}</div>}
      <div className="kv wide" style={{ margin: '6px 0' }}>
        <span className="k">Broker</span><span>{orNA(a.broker)}</span>
        <span className="k">Account type</span><span><EnvBadge a={a} /> {typeLabel(a)}</span>
        <span className="k">Account identifier</span><span className="mono">{orNA(a.login_masked)} <span className="dim">(masked)</span></span>
        <span className="k">Server</span><span>{orNA(a.server)}</span>
        <span className="k">Connection status</span><span className={a.connection === 'ONLINE' ? 'good' : 'bad'}>● {a.connection}{a.combined ? ` (${a.online_in_total}/${a.accounts_in_total} online)` : ''}</span>
        <span className="k">Connection heartbeat</span><span>{a.last_heartbeat ? fmtTs(a.last_heartbeat) : 'NOT AVAILABLE'}</span>
        <span className="k">Last successful account update</span><span>{a.last_update ? fmtTs(a.last_update) : 'NOT AVAILABLE'}<span className="dim"> · terminal read SignalMesh at {fmtTs(detail?.read_at ?? accounts?.read_at)}</span></span>
      </div>
      <div>
        {cell('Balance', 'balance', money(a.balance, a.currency))}{cell('Equity', 'equity', money(a.equity, a.currency))}
        {cell('Floating P/L', 'floating_pnl', money(pl, a.currency), pl == null ? '' : pl >= 0 ? 'good' : 'bad')}
        {cell('Used margin', 'used_margin', money(a.used_margin, a.currency))}{cell('Free margin', 'free_margin', money(a.free_margin, a.currency))}
        {cell('Margin level', 'margin_level', a.margin_level == null ? 'NOT AVAILABLE' : `${a.margin_level.toFixed(2)} %`)}
        <span className="stat"><span className="k">Open positions</span><span className="v">{detail ? detail.positions.length : '…'}</span></span>
        <span className="stat"><span className="k">Pending orders</span><span className="v">{detail ? detail.orders.length : '…'}</span></span>
        <span className="stat" title={detail?.closed_source}><span className="k">Closed trades</span><span className="v">{detail ? detail.closed.length : '…'}</span></span>
      </div>
      {err && <div className="note bad">{err}</div>}
      <div className="note" style={{ paddingLeft: 0 }}>Source: {a.source}. NOT AVAILABLE means the MT5 reporter does not provide that field through SignalMesh — it is never filled with a calculation.</div>
      {a.notes.slice(a.combined ? 1 : 0).map((n, i) => <div key={i} className="note dim" style={{ paddingLeft: 0 }}>{n}</div>)}
      {detail && <div className="note dim" style={{ paddingLeft: 0 }}>positions: {detail.positions_source} · orders: {detail.orders_source} · closed: {detail.closed_source}</div>}
      {accounts && <div className="note dim" style={{ paddingLeft: 0 }}>{accounts.note} · {accounts.rule}</div>}
      {off.length > 0 && <OfflineTable rows={off} />}
    </div>
  );
}

function OfflineTable({ rows }: { rows: AccountView[] }) {
  return <><div className="note" style={{ paddingLeft: 0 }}><b>Known accounts that are not connected</b> (last reported values; not selectable):</div>
    <table className="grid" style={{ width: 'auto' }}><thead><tr><th>Type</th><th>Account</th><th>Server</th><th>Status</th><th>Last heartbeat</th><th>Last balance</th><th>Last equity</th></tr></thead>
      <tbody>{rows.map((a) => <tr key={a.id}><td><EnvBadge a={a} /> {typeLabel(a)}</td><td className="mono">{orNA(a.login_masked)}</td><td>{orNA(a.server)}</td><td className="bad">{a.connection}</td><td className="dim">{a.last_heartbeat ? fmtTs(a.last_heartbeat) : 'NOT AVAILABLE'}</td><td className="mono">{money(a.balance, a.currency)}</td><td className="mono">{money(a.equity, a.currency)}</td></tr>)}</tbody></table></>;
}

function TradesTab({ pollMs, signals, signalsErr, onSignal }: { pollMs: number; signals: SignalRef[]; signalsErr: string; onSignal: (id: string) => void }) {
  const [status, setStatus] = useState('all');
  const [view, setView] = useState<'trades' | 'plans'>('trades');
  const { data, error } = usePoll(() => api.trades(status), pollMs, [status]);
  const rows: TradeRow[] = data?.rows ?? [];
  const history = signals.filter((s) => s.bucket === 'EXPIRED' || s.bucket === 'REJECTED' || s.bucket === 'OTHER');
  const switcher = <span><button className={view === 'trades' ? 'on' : ''} onClick={() => setView('trades')} style={{ marginRight: 4 }}>broker trades</button><button className={view === 'plans' ? 'on' : ''} onClick={() => setView('plans')} style={{ marginRight: 10 }}>expired & rejected signals ({history.length})</button></span>;
  if (view === 'plans') {
    return (
      <>
        <Wall side="signal">Signals past the engine's 12h lifecycle or rejected by the brain — history. <b>Never executed trades.</b></Wall>
        <div className="note">{switcher}</div>
        <SignalTable rows={history} err={signalsErr} onSignal={onSignal} empty="no expired or rejected signals" />
      </>
    );
  }
  return (
    <>
      <Wall side="broker">Trades the MT5 reporter recorded on the broker side. <b>Not SignalMesh signals.</b> <span className="dim">{data?.scope}</span></Wall>
      <div className="note">{switcher}
        {['all', 'open', 'closed'].map((s) => <button key={s} className={s === status ? 'on' : ''} onClick={() => setStatus(s)} style={{ marginRight: 4 }}>{s}</button>)} <span className="dim">{data?.source}</span></div>
      {error && <div className="note bad">{error}</div>}
      <table className="grid">
        <thead><tr><th>#</th><th>Account</th><th>Symbol</th><th>Dir</th><th>Lots</th><th>Entry</th><th>Exit</th><th>SL</th><th>TP</th><th>Status</th><th>P/L</th><th>Session</th><th>Open (UTC)</th><th>Close (UTC)</th><th>Linked signal</th></tr></thead>
        <tbody>{rows.map((t) => (
          <tr key={t.id}><td className="dim">{t.id}</td><td className="mono dim" title="present only when the journal row carries an account">{t.account_masked ?? 'not stated'}</td><td><b>{t.symbol}</b></td><td className={toneOf(t.direction)}>{t.direction}</td><td className="mono">{t.lots}</td>
            <td className="mono">{t.entry ?? '—'}</td><td className="mono">{t.exit ?? '—'}</td><td className="mono">{t.sl ?? '—'}</td><td className="mono">{t.tp ?? '—'}</td>
            <td><span className={`pill ${t.status === 'open' ? 'good' : t.status === 'pending' ? 'warn' : 'muted'}`}>{t.status}</span></td>
            <td className={`mono ${t.profit == null ? 'dim' : t.profit >= 0 ? 'good' : 'bad'}`}>{t.profit ?? '—'}</td><td>{t.session}</td>
            <td className="dim">{fmtTs(t.open_time)}</td><td className="dim">{fmtTs(t.close_time)}</td>
            <td className="mono">{t.signal_id ? <a onClick={() => onSignal(t.signal_id!)}>{t.signal_id}</a> : <span className="dim" title="the journal row names no signal">none stated</span>}</td></tr>))}
          {!rows.length && !error && <tr><td colSpan={15} className="dim">no trades reported</td></tr>}
        </tbody>
      </table>
    </>
  );
}

function PerformanceTab({ pollMs }: { pollMs: number }) {
  const { data, error } = usePoll(() => api.performance(), pollMs * 4);
  if (error) return <div className="note bad">{error}</div>;
  if (!data) return <div className="note">loading…</div>;
  const s = data.stats as Record<string, number | boolean | Record<string, number> | null>;
  const p = data.portfolio as Record<string, number>;
  const num = (k: string) => { const v = s[k]; return typeof v === 'number' ? v : null; };
  const bucket = (k: string) => (s[k] && typeof s[k] === 'object' ? (s[k] as Record<string, number>) : {});
  return (
    <div style={{ padding: '4px 10px' }}>
      <div>
        {[['Closed trades', num('count')], ['Win rate %', num('win_rate')], ['Profit factor', num('profit_factor')], ['Expectancy', num('expectancy')], ['Avg R:R', num('avg_rr')],
          ['Total P/L', num('total_profit')], ['Today', num('today_profit')], ['Week', num('weekly_profit')], ['Month', num('monthly_profit')], ['Max DD %', num('max_drawdown')], ['Current DD %', num('current_dd')], ['Consec. losses', num('consecutive_losses')]]
          .map(([k, v]) => <span className="stat" key={String(k)}><span className="k">{k}</span><span className={`v ${typeof v === 'number' && String(k).match(/P\/L|Today|Week|Month|Expectancy/) ? (v >= 0 ? 'good' : 'bad') : ''}`}>{v ?? '—'}</span></span>)}
      </div>
      <div className={s.low_sample ? 'warn' : 'dim'} style={{ marginBottom: 6 }}>{s.low_sample ? `LOW SAMPLE (n < ${s.min_sample}) — ` : ''}{data.evidence_law}</div>
      <div className="dim" style={{ marginBottom: 4 }}>SignalMesh analytics over closed trades ({String(p.accounts ?? '—')} account(s) reporting). Broker balance, equity and margin are per account under <b>Account Information</b>.</div>
      <div style={{ display: 'flex', gap: 30, flexWrap: 'wrap', marginTop: 6 }}>
        {(['by_symbol', 'by_session', 'by_weekday', 'monthly_returns'] as const).map((k) => (
          <table className="grid" key={k} style={{ width: 'auto' }}><thead><tr><th>{k.replace('_', ' ')}</th><th>P/L</th></tr></thead>
            <tbody>{Object.entries(bucket(k)).map(([n, v]) => <tr key={n}><td>{n}</td><td className={`mono ${v >= 0 ? 'good' : 'bad'}`}>{v}</td></tr>)}</tbody></table>))}
      </div>
      <div className="dim" style={{ marginTop: 6 }}>as of {fmtTs(data.as_of)} · SignalMesh analytics.full_report, verbatim</div>
    </div>
  );
}

function NewsTab({ symbol, pollMs }: { symbol: string; pollMs: number }) {
  const { data, error } = usePoll(() => api.news(symbol), pollMs * 2, [symbol]);
  if (error) return <div className="note bad">{error}</div>;
  if (!data) return <div className="note">loading…</div>;
  const st = data.state as { calendar?: Record<string, unknown>; rows?: Array<Record<string, unknown>>; error?: string };
  const ev = (data.events_next_12h as Array<{ title: string; impact: string; in_min: number }>) ?? [];
  const facts = data.facts as { feed?: { state?: string; note?: string }; facts?: Array<Record<string, unknown>>; covered?: boolean; error?: string };
  const macro = data.macro as { calendar?: Record<string, unknown>; usd_rows?: Array<Record<string, unknown>>; coverage?: unknown; error?: string };
  const cal = st?.calendar ?? {};
  return (
    <div style={{ padding: '4px 10px' }}>
      <div className="note" style={{ padding: '4px 0' }}><b>Calendar (news-state-v1):</b> last post {fmtTs(cal.last_post_at as string)} · age {fmtAge(cal.age_min as number)} / max {fmtAge(cal.max_age_min as number)} · events 24h ahead {String(cal.events_24h_ahead ?? '—')} (high {String(cal.high_24h_ahead ?? '—')}) · source {String(cal.source ?? '—')}{st?.error ? <span className="bad"> · {st.error}</span> : null}</div>
      <table className="grid"><thead><tr><th>Symbol</th><th>State</th><th>Reason</th><th>Next high</th><th>Expires</th></tr></thead>
        <tbody>{(st?.rows ?? []).map((r) => {
          const nh = r.next_high as { title?: string; in_min?: number } | null;
          return <tr key={String(r.symbol)}><td><b>{String(r.symbol)}</b></td><td><span className={`pill ${toneOf(String(r.state))}`}>{String(r.state)}</span></td><td className="muted">{String(r.reason ?? '')}</td><td>{nh ? `${nh.title} in ${nh.in_min}m` : '—'}</td><td className="dim">{fmtTs(r.expires_at as string)}</td></tr>;
        })}</tbody></table>
      <div className="note" style={{ padding: '6px 0 2px' }}><b>Events next 12h for {symbol}:</b> {ev.length ? ev.map((e, i) => <span key={i} className={toneOf(e.impact)} style={{ marginRight: 10 }}>{e.title} · {e.impact} · in {e.in_min}m</span>) : <span className="dim">none mapped</span>}</div>
      <div className="note" style={{ padding: '2px 0' }}><b>Geopolitical facts feed:</b> {facts?.error ? <span className="bad">{facts.error}</span> : <>{facts?.feed?.state ?? 'UNKNOWN'} · {facts?.feed?.note ?? ''} · {(facts?.facts ?? []).length} fact(s){facts?.covered === false ? ' · NOT COVERED for this asset' : ''}</>}</div>
      <div className="note" style={{ padding: '2px 0' }}><b>Macro scorecard:</b> {macro?.error ? <span className="bad">{macro.error}</span> : <>{(macro?.usd_rows ?? []).length} USD rows{(() => { const c = macro?.coverage as { indicators?: number; released_pct?: number; missed?: number; note?: string } | undefined; return c ? ` · ${c.indicators ?? '—'} indicators · released ${c.released_pct ?? '—'}% · missed ${c.missed ?? '—'}` : ''; })()}</>}</div>
    </div>
  );
}

function SourcesTab({ pollMs }: { pollMs: number }) {
  const { data, error } = usePoll(() => api.sources(), pollMs * 2);
  if (error) return <div className="note bad">{error}</div>;
  if (!data) return <div className="note">loading…</div>;
  const feeds = data.feeds as Array<Record<string, unknown>>;
  const ev = data.evidence as { symbols?: Record<string, Record<string, Record<string, unknown>>>; error?: string; alerts?: Record<string, unknown> };
  const prov = data.provider as { name: string; is_fixture: boolean };
  return (
    <div>
      <div className="note"><b>Provider:</b> {prov.name}{prov.is_fixture ? <b className="warn"> · FIXTURE — NOT A MARKET</b> : ''} · <b>verdict:</b> <b className={String(data.verdict).startsWith('ALL MT5') ? 'good' : 'bad'}>{String(data.verdict)}</b>
        <div className="dim">{String(data.source_rule)}</div></div>
      <table className="grid"><thead><tr><th>Symbol</th><th>TF</th><th>State</th><th>Since open</th><th>Limit</th><th>Newest bar</th><th>Last ts (UTC)</th><th>Per-candle source (authority)</th><th>Kind</th><th>Platform label</th></tr></thead>
        <tbody>{feeds.map((f, i) => <tr key={i}><td><b>{String(f.symbol)}</b></td><td>{String(f.tf)}</td><td className={toneOf(String(f.state))}>{String(f.state)}</td><td>{fmtAge(f.age_min as number)}</td><td>{fmtAge(f.limit_min as number)}</td><td>{String(f.newest_bar ?? '—')}</td><td className="dim">{fmtTs(f.last_ts as string)}</td><td className="mono">{String(f.source || f.error || '—')}</td><td className={sourceTone(String(f.source_kind))} title={String(f.source_warning ?? '')}>{sourceWord(String(f.source_kind))}</td><td className="dim">{String(f.platform_label ?? '—')}</td></tr>)}</tbody></table>
      {ev?.symbols && <table className="grid" style={{ marginTop: 6 }}><thead><tr><th>Symbol</th><th>Pine alert</th><th>EA18</th><th>v7 analysis</th><th>Parity</th><th>Primary</th></tr></thead>
        <tbody>{Object.entries(ev.symbols).map(([s, v]) => <tr key={s}><td><b>{s}</b></td><td>{String(v.pine_alert?.state)}</td><td>{String(v.ea18?.state)}</td><td>{String(v.v7_analysis?.state)}</td><td>{String(v.parity?.word)}</td><td>{String((v as Record<string, unknown>).primary)}</td></tr>)}</tbody></table>}
      {ev?.error && <div className="note bad">{ev.error}</div>}
    </div>
  );
}

function SystemTab({ pollMs }: { pollMs: number }) {
  const { data, error } = usePoll(() => api.system(), pollMs);
  const ex2 = usePoll(() => api.executionModes(), pollMs * 20);
  if (error) return <div className="note bad">{error}</div>;
  if (!data) return <div className="note">loading…</div>;
  const a = data.adapter as Record<string, unknown>;
  const up = data.upstream as Record<string, unknown>;
  const ex = data.execution as Record<string, unknown>;
  const p = data.portfolio as Record<string, unknown>;
  const me = data.macro_engine as Record<string, unknown>;
  return (
    <div style={{ padding: '4px 10px' }} className="kv">
      <span className="k">Adapter</span><span>v{String(a.version)} · env {String(a.env)} · provider {String(a.provider)}{a.is_fixture ? <b className="warn"> FIXTURE</b> : ''} · poll {String(a.poll_s)}s · cache {JSON.stringify(a.cache)}</span>
      <span className="k">SignalMesh</span><span className={up.reachable && up.ok ? 'good' : 'bad'}>{up.reachable ? `reachable · http ${String(up.http)} · schema ${String(up.schema ?? '—')} · ok ${String(up.ok)}` : `UNREACHABLE · ${String(up.error ?? up.state ?? '')}`} <span className="dim">({String(a.signalmesh_url ?? '—')})</span></span>
      <span className="k">Execution</span><span className="warn">{String(ex.phase)} · enabled {String(ex.enabled)} · can place {String(ex.can_place)}</span>
      <span className="k">MT5 accounts</span><span>{p.error ? <span className="bad">{String(p.error)}</span> : `${String(p.online)}/${String(p.accounts)} online (heartbeat truth)`}</span>
      <span className="k">Macro engine</span><span>{me.error ? <span className="bad">{String(me.error)}</span> : `${String(me.snap_state ?? '—')} · ready ${String(me.snap_ready ?? '—')}`}</span>
      <span className="k">Execution adapters</span><span>{(ex2.data?.modes ?? []).map((m) => <span key={m.mode} className={`pill ${m.state === 'AVAILABLE' ? 'good' : 'muted'}`} style={{ marginRight: 4 }} title={m.note}>{m.mode} · {m.state}{m.account_types?.length ? ` · ${m.account_types.join(' / ')}` : ''}</span>)}
        <div className="dim">{ex2.data?.architecture}</div>
        <div className="dim">gates before any order: {(ex2.data?.gates ?? []).map((g) => `${g.gate} — ${g.state}`).join(' · ')}</div></span>
      <span className="k">As of</span><span className="dim">{fmtTs(String(data.as_of))}</span>
    </div>
  );
}
