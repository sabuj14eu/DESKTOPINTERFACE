import { useState } from 'react';
import { api } from '../api/client';
import type { SignalRef, TradeRow } from '../api/types';
import { fmtAge, fmtTs, px, toneOf, usePoll } from '../util';

const TABS = ['Active Signals', 'Pending Setups', 'Trade History', 'Performance', 'News & Events', 'Data Sources', 'System Health'] as const;
type Tab = typeof TABS[number];

export default function Terminal({ symbol, pollMs, signals, signalsErr }: { symbol: string; pollMs: number; signals: SignalRef[]; signalsErr: string }) {
  const [tab, setTab] = useState<Tab>('Active Signals');
  return (
    <div className="bottom">
      <div className="tabs">{TABS.map((t) => <button key={t} className={t === tab ? 'on' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>
      <div className="tabbody">
        {tab === 'Active Signals' && <SignalTable rows={signals.filter((s) => s.bucket === 'ACTIVE')} err={signalsErr} empty="no ACTIVE signal (approved/executed within 12h) — the engine has nothing current" />}
        {tab === 'Pending Setups' && <PendingTab signals={signals} err={signalsErr} symbol={symbol} pollMs={pollMs} />}
        {tab === 'Trade History' && <TradesTab pollMs={pollMs} />}
        {tab === 'Performance' && <PerformanceTab pollMs={pollMs} />}
        {tab === 'News & Events' && <NewsTab symbol={symbol} pollMs={pollMs} />}
        {tab === 'Data Sources' && <SourcesTab pollMs={pollMs} />}
        {tab === 'System Health' && <SystemTab pollMs={pollMs} />}
      </div>
    </div>
  );
}

function SignalTable({ rows, err, empty }: { rows: SignalRef[]; err: string; empty: string }) {
  if (err) return <div className="note bad">{err}</div>;
  if (!rows.length) return <div className="note">{empty}</div>;
  return (
    <table className="grid">
      <thead><tr><th>Signal</th><th>Sys</th><th>Symbol</th><th>TF</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP1</th><th>TP2</th><th>R:R</th><th>Grade</th><th>Conf</th><th>Council</th><th>Status</th><th>Age</th><th>Created (UTC)</th></tr></thead>
      <tbody>{rows.map((s) => (
        <tr key={s.signal_id}>
          <td className="mono">{s.signal_id}</td><td>{s.system}</td><td><b>{s.symbol}</b></td><td>{s.tf}</td>
          <td className={toneOf(s.direction)}><b>{s.direction}</b></td>
          <td className="mono">{s.entry ?? '—'}</td><td className="mono">{s.sl ?? '—'}</td><td className="mono">{s.tp1 ?? '—'}</td><td className="mono">{s.tp2 ?? '—'}</td>
          <td className="mono">{s.rr ?? '—'}</td><td>{s.grade || '—'}</td><td>{s.confidence ?? '—'}</td>
          <td>{s.council_total ? `${s.council_approve}/${s.council_total}` : '—'}</td>
          <td><span className={`pill ${toneOf(s.bucket)}`}>{s.status}{s.stale ? ' · EXPIRED' : ''}</span></td>
          <td>{s.age_h != null ? `${s.age_h}h` : '—'}</td><td className="dim">{fmtTs(s.created_at)}</td>
        </tr>))}</tbody>
    </table>
  );
}

function PendingTab({ signals, err, symbol, pollMs }: { signals: SignalRef[]; err: string; symbol: string; pollMs: number }) {
  const { data } = usePoll(() => api.decision(symbol), pollMs, [symbol]);
  const lane = data?.lane;
  return (
    <>
      <div className="note">
        <b>Desk lane candidate ({symbol}, engine {lane?.engine || '?'}):</b> {lane ? <>{lane.decision} · {lane.stage}{lane.reasons.length ? ` · ${lane.reasons.join(', ')}` : ''} — {lane.confirmation_text}
          {lane.entry != null && <> · entry <span className="mono">{px(lane.entry, data?.decimals)}</span> SL <span className="mono">{px(lane.sl, data?.decimals)}</span> TP1 <span className="mono">{px(lane.tp1, data?.decimals)}</span></>}</> : '…'}
        <span className="dim"> · PAPER research — never an executable plan</span>
      </div>
      <SignalTable rows={signals.filter((s) => s.bucket === 'PENDING')} err={err} empty="no PENDING signal candidate within 12h" />
    </>
  );
}

function TradesTab({ pollMs }: { pollMs: number }) {
  const [status, setStatus] = useState('all');
  const { data, error } = usePoll(() => api.trades(status), pollMs, [status]);
  const rows: TradeRow[] = data?.rows ?? [];
  return (
    <>
      <div className="note">{['all', 'open', 'closed'].map((s) => <button key={s} className={s === status ? 'on' : ''} onClick={() => setStatus(s)} style={{ marginRight: 4 }}>{s}</button>)} <span className="dim">{data?.source}</span></div>
      {error && <div className="note bad">{error}</div>}
      <table className="grid">
        <thead><tr><th>#</th><th>Symbol</th><th>Dir</th><th>Lots</th><th>Entry</th><th>Exit</th><th>SL</th><th>TP</th><th>Status</th><th>P/L</th><th>Session</th><th>Open (UTC)</th><th>Close (UTC)</th></tr></thead>
        <tbody>{rows.map((t) => (
          <tr key={t.id}><td className="dim">{t.id}</td><td><b>{t.symbol}</b></td><td className={toneOf(t.direction)}>{t.direction}</td><td className="mono">{t.lots}</td>
            <td className="mono">{t.entry ?? '—'}</td><td className="mono">{t.exit ?? '—'}</td><td className="mono">{t.sl ?? '—'}</td><td className="mono">{t.tp ?? '—'}</td>
            <td><span className={`pill ${t.status === 'open' ? 'good' : t.status === 'pending' ? 'warn' : 'muted'}`}>{t.status}</span></td>
            <td className={`mono ${t.profit == null ? 'dim' : t.profit >= 0 ? 'good' : 'bad'}`}>{t.profit ?? '—'}</td><td>{t.session}</td>
            <td className="dim">{fmtTs(t.open_time)}</td><td className="dim">{fmtTs(t.close_time)}</td></tr>))}
          {!rows.length && !error && <tr><td colSpan={13} className="dim">no trades reported</td></tr>}
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
      <div>
        {[['Balance', p.balance], ['Equity', p.equity], ['Free margin', p.free_margin], ['Floating P/L', p.floating_pnl], ['Accounts', p.accounts], ['Online', p.online]]
          .map(([k, v]) => <span className="stat" key={String(k)}><span className="k">{k}</span><span className="v">{v ?? '—'}</span></span>)}
      </div>
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
      <div className="note"><b>Provider:</b> {prov.name}{prov.is_fixture ? <b className="warn"> · FIXTURE — NOT A MARKET</b> : ''} · <b>price source:</b> {String(data.price_source)}</div>
      <table className="grid"><thead><tr><th>Symbol</th><th>TF</th><th>State</th><th>Age</th><th>Limit</th><th>Newest bar</th><th>Last ts (UTC)</th><th>Source</th></tr></thead>
        <tbody>{feeds.map((f, i) => <tr key={i}><td><b>{String(f.symbol)}</b></td><td>{String(f.tf)}</td><td className={toneOf(String(f.state))}>{String(f.state)}</td><td>{fmtAge(f.age_min as number)}</td><td>{fmtAge(f.limit_min as number)}</td><td>{String(f.newest_bar ?? '—')}</td><td className="dim">{fmtTs(f.last_ts as string)}</td><td className="dim">{String(f.source ?? f.error ?? '—')}</td></tr>)}</tbody></table>
      {ev?.symbols && <table className="grid" style={{ marginTop: 6 }}><thead><tr><th>Symbol</th><th>Pine alert</th><th>EA18</th><th>v7 analysis</th><th>Parity</th><th>Primary</th></tr></thead>
        <tbody>{Object.entries(ev.symbols).map(([s, v]) => <tr key={s}><td><b>{s}</b></td><td>{String(v.pine_alert?.state)}</td><td>{String(v.ea18?.state)}</td><td>{String(v.v7_analysis?.state)}</td><td>{String(v.parity?.word)}</td><td>{String((v as Record<string, unknown>).primary)}</td></tr>)}</tbody></table>}
      {ev?.error && <div className="note bad">{ev.error}</div>}
    </div>
  );
}

function SystemTab({ pollMs }: { pollMs: number }) {
  const { data, error } = usePoll(() => api.system(), pollMs);
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
      <span className="k">MT5 accounts</span><span>{p.error ? <span className="bad">{String(p.error)}</span> : `${String(p.online)}/${String(p.accounts)} online (heartbeat truth) · equity ${String(p.equity)}`}</span>
      <span className="k">Macro engine</span><span>{me.error ? <span className="bad">{String(me.error)}</span> : `${String(me.snap_state ?? '—')} · ready ${String(me.snap_ready ?? '—')}`}</span>
      <span className="k">As of</span><span className="dim">{fmtTs(String(data.as_of))}</span>
    </div>
  );
}
