import type { ElliottCount, PatternData, PatternId, Pt } from '../patterns';
import { fmtTs, px } from '../util';

// THE PATTERN STUDY TABLES — read-only, beside the chart, like an indicator's table. Every value comes
// from /studies (pattern-studies-v1); nothing is typed in and nothing is sent anywhere. The page records
// nothing: Wolfe and Elliott forecasts are recorded by the adapter's own recorder, whoever is looking.
const ts = (t?: number | null) => (t == null ? '—' : fmtTs(new Date(t * 1000).toISOString()));
const hyp = <span className="tag hyp">HYPOTHETICAL ANALYSIS LEVEL</span>;

export function PatternMethod({ data, onClose }: { data: PatternData | null; onClose: () => void }) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal about" onClick={(e) => e.stopPropagation()} data-testid="st-method-panel">
        <div style={{ display: 'flex', alignItems: 'center' }}><h3 style={{ margin: 0 }}>Pattern studies — how they are calculated</h3><span style={{ flex: 1 }} /><button onClick={onClose}>✕</button></div>
        <p className="warn" style={{ fontSize: 12 }}>Display-only studies calculated by this terminal from SignalMesh's stored CLOSED candles of the chart's timeframe. They are not SignalMesh engine output. They produce no BUY / SELL signal, change no SignalMesh decision, entry, stop-loss, take-profit or statistic, and place no order. A CONFIRMED Wolfe wave and a VALID Elliott stage are recorded in the terminal's own Forecast Journal (append-only, scored from closed bars); a developing Wolfe, an unknown or alternative Elliott count, Fibonacci extension, anchored VWAP and the volume profile are context only and kept nowhere. Every entry, stop and target shown is a HYPOTHETICAL ANALYSIS LEVEL. Volume is MT5 tick volume (activity), not traded volume.</p>
        <h4>Method ({data?.method_version ?? 'pattern-studies-v1'})</h4>
        {data ? <div className="kv wide">{Object.entries(data.methodology).map(([k, v]) => <span key={k} style={{ display: 'contents' }}><span className="k">{k.replace(/_/g, ' ')}</span><span>{v}</span></span>)}</div>
          : <div className="dim">switch a pattern study on to load the method text</div>}
        {data && <><h4>Calculation on screen</h4><div className="kv wide">
          <span className="k">instrument</span><span>{data.symbol} · {data.tf}</span>
          <span className="k">closed bars used</span><span>{data.bars_used} · through bar close {fmtTs(data.through_close_utc)}</span>
          <span className="k">source</span><span>{data.source}</span>
          <span className="k">recorded</span><span>{data.recorded_note}</span>
          <span className="k">calculated</span><span>{fmtTs(data.calculated_at)}</span>
        </div></>}
      </div>
    </div>
  );
}

function Count({ c, dec, title }: { c: ElliottCount; dec: number; title: string }) {
  return (
    <div className={`scen ${c.dir === 1 ? 'bullish' : 'bearish'}`}>
      <div><b className={c.dir === 1 ? 'good' : 'bad'}>{title} · {c.direction}</b> · {c.text} {hyp}</div>
      {c.count_status && <table className="grid sr" data-testid="st-elliott-status"><tbody>
        <tr><td>PIVOTS</td><td>{c.pivots_status}</td></tr>
        <tr><td>COUNT</td><td className={c.wave === 6 ? 'good' : 'warn'}><b>{c.count_status}</b></td></tr>
        <tr><td>TRADE SETUP</td><td className={c.setup && c.setup !== 'NONE' ? 'good' : 'warn'}><b>{c.setup_status}</b></td></tr>
      </tbody></table>}
      <table className="grid sr"><thead><tr><th>Invalidation</th><th>Target 1</th><th>Target 2</th><th>Ratios</th></tr></thead><tbody><tr className="mono">
        <td className="bad">{px(c.invalidation, dec)}</td><td>{px(c.target_1, dec)} <span className="dim">{c.target_1_name}</span></td><td>{px(c.target_2, dec)} <span className="dim">{c.target_2_name}</span></td>
        <td>{Object.entries(c.ratios).map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`).join(' · ')}</td></tr></tbody></table>
      <div className="dim">pivots: {c.points.map((p) => `${p.name}=${px(p.price, dec)}`).join('  ')} · {c.rules_met}</div>
    </div>
  );
}
function Record({ d, module }: { d: PatternData; module: string }) {
  const g = (d.journal ?? []).filter((x) => x.module === module);
  const tfOk = (d.journal_timeframes ?? []).includes(d.tf);
  if (!tfOk) return <div className="dim" data-testid={`st-record-${module}`}>RECORD: not recorded on {d.tf} — the journal records this study on {(d.journal_timeframes ?? []).join(', ')}</div>;
  return <div className="dim" data-testid={`st-record-${module}`}>RECORD (Forecast Journal, {d.symbol} {d.tf}): <b>{g.some((x) => x.finished >= 20) ? g.filter((x) => x.finished >= 20).map((x) => `${x.origin} TP1 ${x.tp1_rate_pct}% · avg ${x.r_avg ?? '—'} R (${x.sample})`).join(' · ') : 'CONFIDENCE UNKNOWN'}</b> — {g.length ? g.map((x) => `${x.origin}: ${x.finished} finished of ${x.recorded} recorded${x.r_avg != null ? `, avg ${x.r_avg} R over ${x.r_n}` : ''}`).join(' · ') + ' · under 20 is luck' : 'no forecast of this study recorded here yet'}</div>;
}
const pts = (q: Pt[], dec: number) => q.map((p) => `${p.name}: ${px(p.price, dec)}`).join('   ');

export default function PatternReport({ data, on, symbol, tf }: { data: PatternData | null; on: (id: PatternId) => boolean; symbol: string; tf: string }) {
  const d = data && data.symbol === symbol && data.tf === tf ? data : null;
  if (!d) return <section data-testid="st-report"><h5>PATTERN STUDIES · {symbol}</h5><div className="dim">loading…</div></section>;
  if (d.state !== 'OK') return <section data-testid="st-report"><h5>PATTERN STUDIES · {symbol} · {tf}</h5><div className="warn" data-testid="st-state">NOT AVAILABLE — {d.note}</div></section>;
  const dec = d.decimals; const { fib, avwap, wolfe, elliott, vp } = d;
  const wp = wolfe?.pattern ?? null;
  return (
    <section data-testid="st-report">
      {d.freshness && d.freshness.state !== 'LIVE' && <div className="scen bearish" data-testid="st-stale"><b className="bad">DATA {d.freshness.state}</b> — the newest closed bar ended {fmtTs(d.through_close_utc)}{d.freshness.age_min != null ? ` (${Math.round(d.freshness.age_min)} min old, limit ${d.freshness.limit_min ?? '—'})` : ''}. Everything below is calculated from that bar: it is the last known picture, not a live market. No new setup is made or recorded until a new bar closes.</div>}
      <div className="dim">pattern studies · {symbol} {tf} · {d.bars_used} closed bars through {fmtTs(d.through_close_utc)} · Wolfe and Elliott are recorded in the Forecast Journal; the others are context only</div>
      {on('st-fib') && fib && <div data-testid="st-fib-report">
        <h5>FIBONACCI EXTENSION <span className="dim">· last three confirmed swings</span></h5>
        {fib.state !== 'OK' ? <div className="dim" data-testid="st-fib-state">NONE — {fib.note}</div> : <>
          <div><b className={fib.direction === 'UP' ? 'good' : 'bad'}>{fib.direction === 'UP' ? 'UPWARD targets' : 'DOWNWARD targets'}</b> · <b className={fib.status === 'INVALIDATED' ? 'bad' : ''}>{fib.status}</b> · A {px(fib.a!.price, dec)} → B {px(fib.b!.price, dec)} → C {px(fib.c!.price, dec)} · C retraced {fib.retrace_pct}% of A-B {hyp}</div>
          <table className="grid sr" data-testid="st-fib-levels"><thead><tr><th>Ratio</th><th>Level</th><th>State</th></tr></thead><tbody>
            {fib.levels!.map((l) => <tr key={l.ratio} className="mono"><td>{l.ratio}</td><td>{px(l.price, dec)}</td><td className={l.reached ? 'good' : fib.next_level?.ratio === l.ratio ? 'warn' : 'dim'}>{l.reached ? 'reached' : fib.next_level?.ratio === l.ratio ? 'next target' : 'open'}</td></tr>)}
          </tbody></table>
          <div className="dim">{fib.rule} at {px(fib.invalidation, dec)}{fib.invalidated_bar ? ` — happened on the bar of ${ts(fib.invalidated_bar)}` : ''} · C confirmed {ts(fib.confirmed_at)}</div>
        </>}
      </div>}
      {on('st-avwap') && avwap && <div data-testid="st-avwap-report">
        <h5>ANCHORED VWAP <span className="dim">· tick-volume weighted</span></h5>
        {avwap.state !== 'OK' ? <div className="dim" data-testid="st-avwap-state">{avwap.state.replace('_', ' ')} — {avwap.note}</div> : <>
          <table className="grid sr" data-testid="st-avwap-table"><thead><tr><th>Anchor</th><th>VWAP now</th><th>Band ±1σ</th><th>Price is</th><th>Anchored at</th></tr></thead><tbody>
            {avwap.anchors.map((a) => <tr key={a.id}><td>{a.name}</td><td className="mono"><b>{px(a.value, dec)}</b></td><td className="mono">{px(a.lower, dec)} – {px(a.upper, dec)}</td>
              <td className={a.side === 'ABOVE' ? 'good' : a.side === 'BELOW' ? 'bad' : ''}>{a.side} by {px(Math.abs(a.distance), dec)}{a.distance_atr != null ? ` (${Math.abs(a.distance_atr)} ATR)` : ''}</td><td className="dim">{ts(a.anchor_time)} · {a.bars} bars</td></tr>)}
          </tbody></table>
          <div className="dim">{avwap.reading} · {avwap.volume_kind}</div>
        </>}
      </div>}
      {on('st-wolfe') && wolfe && <div data-testid="st-wolfe-report">
        <h5>WOLFE WAVE <span className="dim">· 5 alternating pivots in a wedge</span></h5>
        {wp ? <div className={`scen ${wp.side === 'LONG' ? 'bullish' : 'bearish'}`} data-testid="st-wolfe-pattern">
          <div><b className={wp.side === 'LONG' ? 'good' : 'bad'}>{wp.direction} · {wp.side}</b> · CONFIRMED 5 points · <b>{wp.status}</b> {hyp}</div>
          <table className="grid sr"><thead><tr><th>Entry</th><th>SL</th><th>TP1</th><th>TP2 (EPA side)</th><th>R:R</th><th>Expires</th></tr></thead><tbody><tr className="mono">
            <td>{px(wp.entry, dec)}</td><td className="bad">{px(wp.sl, dec)}</td><td>{px(wp.tp1, dec)}</td><td>{px(wp.tp2, dec)}</td><td>{wp.rr1 ?? '—'} / {wp.rr2 ?? '—'}</td><td>{ts(wp.expires_time)} (ESTIMATE)</td></tr></tbody></table>
          <div className="dim">{pts(wp.points, dec)} · point-5 zone {px(wp.zone_5[0], dec)} – {px(wp.zone_5[1], dec)} · EPA {px(wp.epa, dec)} · made on the bar of {ts(wp.made_bar)}</div>
        </div> : wolfe.developing ? <div className="scen" style={{ borderColor: '#c084fc' }} data-testid="st-wolfe-developing">
          <div><b>{wolfe.developing.direction}</b> · <b className="warn">{wolfe.developing.status}</b></div>
          <div className="dim">{pts(wolfe.developing.points, dec)} · line 1-3 is now at {px(wolfe.developing.line_13_now, dec)} · waiting for {wolfe.developing.waiting_for}: {px(wolfe.developing.point_5_limit, dec)}. No entry, stop or target until point 5 is confirmed.</div>
        </div> : <div className="dim" data-testid="st-wolfe-state">NONE — {wolfe.note}</div>}
        <Record d={d} module="wolfe-wave" />
        {wolfe.last_finished && <div className="dim">last finished: {wolfe.last_finished.direction} made {ts(wolfe.last_finished.made_bar)} → {wolfe.last_finished.status} on {ts(wolfe.last_finished.status_bar)} · {wolfe.log.length} pattern(s) in the loaded bars</div>}
      </div>}
      {on('st-elliott') && elliott && <div data-testid="st-elliott-report">
        <h5>ELLIOTT WAVE <span className="dim">· impulse count on confirmed pivots</span></h5>
        {elliott.count ? <>
          <Count c={elliott.count} dec={dec} title="MAIN COUNT" />
          {elliott.abc.length ? <div className="dim">correction so far: {pts(elliott.abc, dec)}</div> : null}
          {elliott.alternative ? <Count c={elliott.alternative} dec={dec} title="ALTERNATIVE" /> : <div className="dim">alternative count: NONE — {elliott.note}</div>}
        </> : <div className="warn" data-testid="st-elliott-state">UNKNOWN — {elliott.note}</div>}
        <Record d={d} module="elliott-wave" />
      </div>}
      {on('st-vp') && vp && <div data-testid="st-vp-report">
        <h5>VOLUME PROFILE <span className="dim">· TICK-VOLUME ACTIVITY, not traded volume</span></h5>
        {vp.state !== 'OK' ? <div className="dim" data-testid="st-vp-state">NOT AVAILABLE — {vp.note}</div> : <>
          <table className="grid sr" data-testid="st-vp-table"><tbody>
            <tr><td>POC (busiest price)</td><td className="mono" style={{ color: '#fb923c' }}><b>{px(vp.poc, dec)}</b></td><td className="dim">{vp.bars} bars · {ts(vp.from_time)} → {ts(vp.to_time)}</td></tr>
            <tr><td>VALUE AREA HIGH</td><td className="mono">{px(vp.vah, dec)}</td><td className="dim" rowSpan={2}>{vp.value_area_pct}% of the activity is between them</td></tr>
            <tr><td>VALUE AREA LOW</td><td className="mono">{px(vp.val, dec)}</td></tr>
            <tr><td>PRICE IS</td><td colSpan={2}><b>{vp.position}</b> <span className="dim">— {vp.reading}</span></td></tr>
            <tr><td>HIGH ACTIVITY NODES</td><td colSpan={2} className="mono">{vp.hvn?.length ? vp.hvn.map((v) => px(v, dec)).join(' · ') : '—'}</td></tr>
            <tr><td>LOW ACTIVITY NODES</td><td colSpan={2} className="mono">{vp.lvn?.length ? vp.lvn.map((v) => px(v, dec)).join(' · ') : '—'}</td></tr>
          </tbody></table>
        </>}
      </div>}
    </section>
  );
}
