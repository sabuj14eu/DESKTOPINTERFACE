import { useEffect, useMemo, useState } from 'react';
import { api, getToken, setToken } from './api/client';
import ChartPanel from './components/ChartPanel';
import MarketWatch from './components/MarketWatch';
import Terminal from './components/Terminal';
import TicketModal from './components/TicketModal';
import TokenGate from './components/TokenGate';
import TopBar from './components/TopBar';
import TradingPanel from './components/TradingPanel';
import { usePoll } from './util';

export default function App() {
  const [authTick, setAuthTick] = useState(0);
  const health = usePoll(() => api.health(), 30000, [authTick]);
  const pollMs = Math.max(5, health.data?.adapter.poll_s ?? 15) * 1000;
  const [symbol, setSymbol] = useState<string>(() => { try { return localStorage.getItem('smt_symbol') || ''; } catch { return ''; } });
  const [tf, setTf] = useState<string>(() => { try { return localStorage.getItem('smt_tf') || '15m'; } catch { return '15m'; } });
  useEffect(() => { if (!symbol && health.data?.default_symbol) setSymbol(health.data.default_symbol); }, [health.data, symbol]);
  useEffect(() => { try { if (symbol) localStorage.setItem('smt_symbol', symbol); localStorage.setItem('smt_tf', tf); } catch { /* ignore */ } }, [symbol, tf]);

  const needsToken = health.data?.adapter.auth === 'token';
  const watch = usePoll(() => api.marketWatch(), pollMs, [authTick]);
  const unauthorized = [watch.error].some((e) => e.includes('access token'));
  const sym = symbol || health.data?.default_symbol || 'GOLD';
  const candles = usePoll(() => api.candles(sym, tf, 400), pollMs, [sym, tf, authTick]);
  const decision = usePoll(() => api.decision(sym), pollMs, [sym, authTick]);
  const signals = usePoll(() => api.signals('all'), pollMs * 2, [authTick]);
  const [ticket, setTicket] = useState(false);

  const symbols = useMemo(() => {
    const base = health.data?.symbols ?? [];
    const extra = (signals.data?.rows ?? []).map((s) => s.symbol).filter((s) => s && !base.includes(s));
    return [...base, ...Array.from(new Set(extra)).sort()];
  }, [health.data, signals.data]);

  if (needsToken && (!getToken() || unauthorized)) {
    return <TokenGate onDone={() => setAuthTick((n) => n + 1)} />;
  }
  const row = watch.data?.rows.find((r) => r.symbol === sym);
  const errOf = (e: string) => (e ? (e.length > 180 ? e.slice(0, 180) + '…' : e) : '');
  const isFixture = health.data?.provider.is_fixture;
  const adapterDown = health.error && !health.data;
  return (
    <div className="terminal">
      <div className="banner">
        {isFixture && <div className="fixture-banner">FIXTURE DATA — recorded shapes and synthetic bars. NOT A MARKET. Development only.</div>}
        {adapterDown && <div className="err-banner">terminal adapter unreachable — {errOf(health.error)}</div>}
      </div>
      <TopBar health={health.data} healthErr={health.error} symbols={symbols.length ? symbols : [sym]} symbol={sym} onSymbol={setSymbol} tf={tf} onTf={setTf}
        row={row} decision={decision.data} portfolio={watch.data?.portfolio ?? null} onLogout={needsToken ? () => { setToken(''); setAuthTick((n) => n + 1); } : undefined} />
      <MarketWatch rows={watch.data?.rows ?? []} selected={sym} onSelect={setSymbol} error={errOf(watch.error)} rule={watch.data?.price_rule ?? ''} />
      <ChartPanel series={candles.data} seriesErr={errOf(candles.error)} decision={decision.data} signals={signals.data?.rows ?? []} symbol={sym} tf={tf} />
      <TradingPanel d={decision.data} err={errOf(decision.error)} health={health.data} onTicket={() => setTicket(true)} />
      <Terminal symbol={sym} pollMs={pollMs} signals={signals.data?.rows ?? []} signalsErr={errOf(signals.error)} />
      {ticket && <TicketModal symbol={sym} onClose={() => setTicket(false)} />}
    </div>
  );
}
