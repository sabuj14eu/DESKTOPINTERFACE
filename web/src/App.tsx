import { useEffect, useMemo, useRef, useState } from 'react';
import { api, getToken, setToken } from './api/client';
import ChartPanel from './components/ChartPanel';
import MarketWatch from './components/MarketWatch';
import SignalDetail from './components/SignalDetail';
import Splitter from './components/Splitter';
import StatusBar from './components/StatusBar';
import Terminal from './components/Terminal';
import TicketModal from './components/TicketModal';
import TokenGate from './components/TokenGate';
import TopBar from './components/TopBar';
import TradingPanel from './components/TradingPanel';
import { useMedia, usePoll } from './util';
import { DEFAULT, useWorkspace } from './workspace';

type MobileView = 'quotes' | 'chart' | 'signal' | 'trade' | 'account';
const MOBILE_NAV: [MobileView, string, string][] = [['quotes', '≣', 'Quotes'], ['chart', '📈', 'Chart'], ['signal', '◎', 'Signal'], ['trade', '⇅', 'Trade'], ['account', '▣', 'Account']];

export default function App() {
  const [authTick, setAuthTick] = useState(0);
  const health = usePoll(() => api.health(), 30000, [authTick]);
  const pollMs = Math.max(5, health.data?.adapter.poll_s ?? 15) * 1000;
  const instruments = usePoll(() => api.instruments(), pollMs * 20, [authTick]);
  const [symbol, setSymbol] = useState<string>(() => { try { return localStorage.getItem('smt_symbol') || ''; } catch { return ''; } });
  const [tf, setTf] = useState<string>(() => { try { return localStorage.getItem('smt_tf') || '15m'; } catch { return '15m'; } });
  useEffect(() => { if (!symbol && (instruments.data?.watch[0] || health.data?.default_symbol)) setSymbol(instruments.data?.watch[0] || health.data!.default_symbol); }, [health.data, instruments.data, symbol]);
  useEffect(() => { try { if (symbol) localStorage.setItem('smt_symbol', symbol); localStorage.setItem('smt_tf', tf); } catch { /* ignore */ } }, [symbol, tf]);

  const { ws, patch, toggle, resize, setChart, reset } = useWorkspace();
  const mobile = useMedia('(max-width: 860px)');
  const [mview, setMview] = useState<MobileView>('chart');
  const [signalId, setSignalId] = useState('');
  const work = useRef<HTMLDivElement>(null);
  const shell = useRef<HTMLDivElement>(null);

  const needsToken = health.data?.adapter.auth === 'token';
  const watch = usePoll(() => api.marketWatch(), pollMs, [authTick]);
  const unauthorized = needsToken && [watch.error].some((e) => e.includes('access token'));
  const loginRequired = health.data?.adapter.auth === 'signalmesh' && [watch.error, health.error].some((e) => e.includes('login required'));
  const sym = symbol || health.data?.default_symbol || 'GOLD';
  const candles = usePoll(() => api.candles(sym, tf, ws.bars), pollMs, [sym, tf, ws.bars, authTick]);
  const decision = usePoll(() => api.decision(sym), pollMs, [sym, authTick]);
  // THE FORMING BAR — display only, polled every 2 s; closed candles stay on their own slower poll
  const live = usePoll(() => (ws.chart.live ? api.live(sym, tf) : Promise.resolve(null)), 2000, [sym, tf, ws.chart.live, authTick]);
  const coverage = usePoll(() => api.coverage(sym), pollMs * 8, [sym, authTick]);
  const signals = usePoll(() => api.signals('all'), pollMs * 2, [authTick]);
  const [ticket, setTicket] = useState(false);

  // BROKER ACCOUNTS: only connected ones are selectable; exactly one is selected, and every
  // broker figure on screen is read for that one account id. Switching clears the old figures
  // at once (usePoll drops the previous account's answer).
  const accounts = usePoll(() => api.accounts(), pollMs * 2, [authTick]);
  const account = useMemo(() => { const l = accounts.data?.accounts ?? []; return l.find((a) => a.id === ws.account) ?? l[0] ?? null; }, [accounts.data, ws.account]);
  const accountId = account?.id ?? '';
  const acctDetail = usePoll(() => (accountId ? api.account(accountId) : Promise.resolve(null)), pollMs * 2, [accountId, authTick]);

  // the symbol list is DISCOVERED from SignalMesh (DEFAULT_SYMBOLS + signalled symbols), never typed here
  const symbols = useMemo(() => {
    const d = instruments.data;
    if (d) return d.instruments.filter((i) => i.available).map((i) => i.symbol).concat(d.instruments.filter((i) => !i.available).map((i) => i.symbol));
    return (watch.data?.rows ?? []).map((r) => r.symbol);
  }, [instruments.data, watch.data]);

  // keyboard: F full-screen chart, Esc leaves it, Ctrl+M / Ctrl+D / Ctrl+T toggle the panels (MT5 habits)
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ['INPUT', 'SELECT', 'TEXTAREA'].includes(t.tagName)) return;
      if (e.key === 'Escape' && ws.full) patch({ full: false });
      else if ((e.key === 'f' || e.key === 'F') && !e.ctrlKey && !e.metaKey && !e.altKey) patch({ full: !ws.full });
      else if (e.ctrlKey && !e.shiftKey && ['m', 'd', 't'].includes(e.key.toLowerCase())) { e.preventDefault(); toggle(e.key.toLowerCase() === 'm' ? 'left' : e.key.toLowerCase() === 'd' ? 'right' : 'bottom'); }
    };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [ws.full, patch, toggle]);

  if (needsToken && (!getToken() || unauthorized)) {
    return <TokenGate onDone={() => setAuthTick((n) => n + 1)} />;
  }
  if (loginRequired) {
    const url = health.data?.adapter.login_url || '/login?next=/terminal/';
    return <div className="gate"><div style={{ textAlign: 'center' }}><div className="brand accent" style={{ fontWeight: 800 }}>SIGNALMESH · TERMINAL</div>
      <p className="muted">Please log in to SignalMesh first — the terminal uses the same login.</p><a href={url}><button className="on">Go to SignalMesh login</button></a></div></div>;
  }
  const row = watch.data?.rows.find((r) => r.symbol === sym);
  const errOf = (e: string) => (e ? (e.length > 180 ? e.slice(0, 180) + '…' : e) : '');
  const isFixture = health.data?.provider.is_fixture;
  const adapterDown = health.error && !health.data;
  const full = ws.full && !mobile;
  const showLeft = !full && ws.left.open, showRight = !full && ws.right.open, showBottom = !full && ws.bottom.open;
  const pick = (s: string) => { setSymbol(s); if (mobile) setMview('chart'); };

  const banner = (
    <div className="banner">
      {isFixture && <div className="fixture-banner">FIXTURE DATA — recorded shapes and synthetic bars. NOT A MARKET. Development only.</div>}
      {adapterDown && <div className="err-banner">terminal adapter unreachable — {errOf(health.error)}</div>}
    </div>);
  const topbar = (
    <TopBar health={health.data} healthErr={health.error} symbols={symbols.length ? symbols : [sym]} symbol={sym} onSymbol={setSymbol} tf={tf} onTf={setTf}
      row={row} decision={decision.data && decision.data.symbol === sym ? decision.data : null} coverage={coverage.data} live={live.data && live.data.symbol === sym ? live.data : null}
      accounts={accounts.data} accountsErr={errOf(accounts.error)} account={account} onAccount={(id) => patch({ account: id })}
      ws={ws} onToggle={toggle} onFull={() => patch({ full: !ws.full })} onReset={reset} mobile={mobile}
      onLogout={needsToken ? () => { setToken(''); setAuthTick((n) => n + 1); } : undefined} />);
  const watchEl = <MarketWatch rows={watch.data?.rows ?? []} instruments={instruments.data?.instruments ?? []} selected={sym} onSelect={pick} error={errOf(watch.error)} rule={(watch.data?.instrument_rule ? watch.data.instrument_rule + ' ' : '') + (watch.data?.price_rule ?? '')} />;
  const chartEl = (
    <ChartPanel series={candles.data} seriesErr={errOf(candles.error)} decision={decision.data} signals={signals.data?.rows ?? []} symbol={sym} tf={tf} coverage={coverage.data} live={live.data && live.data.symbol === sym && live.data.tf === tf ? live.data : null}
      opts={ws.chart} onOpts={setChart} bars={ws.bars} onBars={(n) => patch({ bars: n })} indicators={ws.indicators} onIndicators={(ids) => patch({ indicators: ids })} smc={ws.smc} onSmc={(n) => patch({ smc: n })}
      full={full} onFull={() => patch({ full: !ws.full })} onSignal={setSignalId} compact={mobile} />);
  const panelEl = <TradingPanel d={decision.data} err={errOf(decision.error)} health={health.data} onTicket={() => setTicket(true)} onSignal={setSignalId} />;
  const toolbox = (tab: string, onHide?: () => void) => (
    <Terminal symbol={sym} pollMs={pollMs} signals={signals.data?.rows ?? []} signalsErr={errOf(signals.error)} tab={tab} onTab={(t) => patch({ tab: t })} onSignal={setSignalId} onHide={onHide}
      accounts={accounts.data} account={account} detail={acctDetail.data} detailErr={errOf(acctDetail.error)} />);
  const overlays = <>
    {signalId && <SignalDetail id={signalId} onClose={() => setSignalId('')} onShow={pick} />}
    {ticket && <TicketModal symbol={sym} onClose={() => setTicket(false)} />}
  </>;

  if (mobile) {
    // PHONE: one view at a time with a bottom navigation bar, like the MT5 / TradingView apps
    return (
      <div className="terminal mobile" data-view={mview}>
        {banner}{topbar}
        <div className="mview">
          {mview === 'quotes' && watchEl}
          {mview === 'chart' && chartEl}
          {mview === 'signal' && panelEl}
          {mview === 'trade' && toolbox(ws.tab === 'Account Information' ? 'Active Signals' : ws.tab)}
          {mview === 'account' && toolbox('Account Information')}
        </div>
        <nav className="mnav" aria-label="Views">{MOBILE_NAV.map(([v, icon, label]) => (
          <button key={v} className={v === mview ? 'on' : ''} onClick={() => setMview(v)} data-testid={`nav-${v}`}><span className="ico">{icon}</span>{label}</button>))}</nav>
        {overlays}
      </div>
    );
  }

  return (
    <div className={'terminal' + (full ? ' full' : '')} ref={shell} data-full={full ? '1' : '0'}>
      {banner}{topbar}
      <div className="work" ref={work}>
        {showLeft && <><aside className="watch-wrap" style={{ width: ws.left.w }} data-testid="panel-left">{watchEl}</aside>
          <Splitter dir="x" label="Market Watch width" onDrag={(x) => resize('left', x - (work.current?.getBoundingClientRect().left ?? 0))} onReset={() => resize('left', DEFAULT.left.w)} /></>}
        {chartEl}
        {showRight && <><Splitter dir="x" label="Decision panel width" onDrag={(x) => resize('right', (work.current?.getBoundingClientRect().right ?? window.innerWidth) - x)} onReset={() => resize('right', DEFAULT.right.w)} />
          <aside className="panel-wrap" style={{ width: ws.right.w }} data-testid="panel-right">{panelEl}</aside></>}
      </div>
      {showBottom && <><Splitter dir="y" label="Toolbox height" onDrag={(y) => resize('bottom', (shell.current?.getBoundingClientRect().bottom ?? window.innerHeight) - 24 - y)} onReset={() => resize('bottom', DEFAULT.bottom.h)} />
        <div className="bottom-wrap" style={{ height: ws.bottom.h }} data-testid="panel-bottom">{toolbox(ws.tab, () => toggle('bottom'))}</div></>}
      <StatusBar account={account} health={health.data} healthErr={health.error} counts={acctDetail.data?.account?.id === accountId && acctDetail.data.counts ? acctDetail.data.counts : null} />
      {overlays}
    </div>
  );
}
