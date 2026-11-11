import { useState } from 'react';
import type { DailyForecast, FcSettings, Ranking } from '../forecast';
import { fmtTs, px } from '../util';

// THE STUDY REPORT — the read-only table that sits on the chart beside a forecasting study, like the
// tables of a TradingView indicator. Everything in it comes from /forecast/*; nothing is typed in
// and nothing is sent anywhere. It never shows a number the adapter did not calculate.
interface Props { symbol: string; daily: DailyForecast | null; ranking: Ranking | null; showDaily: boolean; showRanking: boolean; err: string; s: FcSettings; onChange: (n: FcSettings) => void; onSymbol?: (s: string) => void }

const pct = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(0)}%`);
const stateTone = (s: string) => (s.startsWith('MOVING UP') ? 'good' : s.startsWith('MOVING DOWN') ? 'bad' : s.startsWith('DONE') ? 'dim' : s.startsWith('NEAR') ? 'warn' : s.startsWith('NOT') ? 'dim' : '');

export function ForecastMethod({ daily, ranking, onClose }: { daily: DailyForecast | null; ranking: Ranking | null; onClose: () => void }) {
  const m = { ...(ranking?.methodology ?? {}), ...(daily?.methodology ?? {}) };
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal about" onClick={(e) => e.stopPropagation()} data-testid="fc-method-panel">
        <div style={{ display: 'flex', alignItems: 'center' }}><h3 style={{ margin: 0 }}>Forecasting studies — how they are calculated</h3><span style={{ flex: 1 }} /><button onClick={onClose}>✕</button></div>
        <p className="warn" style={{ fontSize: 12 }}>Display-only studies calculated by this terminal from SignalMesh's stored CLOSED candles, ported from your TradingView scripts (Metal Hunter V15 daily forecast, MH15 PLUS rotation ladder). They are not SignalMesh engine output. They produce no BUY / SELL signal, change no SignalMesh decision, entry, stop-loss, take-profit or statistic, and place no order. Every entry, stop and target shown is a HYPOTHETICAL ANALYSIS LEVEL.</p>
        <h4>Method ({daily?.method_version ?? 'daily-forecast-v1'} · {ranking?.method_version ?? 'rotation-v1'})</h4>
        <div className="kv wide">{Object.entries(m).map(([k, v]) => <span key={k} style={{ display: 'contents' }}><span className="k">{k.replace(/_/g, ' ')}</span><span>{v}</span></span>)}</div>
        {!Object.keys(m).length && <div className="dim">switch a forecasting study on to load the method text</div>}
        <h4>Calculation on screen</h4>
        {daily && daily.state === 'OK' ? <div className="kv wide">
          <span className="k">instrument</span><span>{daily.symbol}</span>
          <span className="k">broker day started</span><span>{fmtTs(daily.day_start_utc)} — ends about {fmtTs(daily.day_end_utc)} (ESTIMATE)</span>
          <span className="k">through bar close</span><span>{fmtTs(daily.through_close_utc)} · {daily.bars_today} closed {daily.intraday_tf} bars today</span>
          <span className="k">ADR</span><span>{px(daily.adr, daily.decimals)} — mean range of the last {daily.adr_days} completed days</span>
          <span className="k">source</span><span>{daily.source}</span>
          <span className="k">calculated</span><span>{fmtTs(daily.calculated_at)}</span>
        </div> : <div className="dim">{daily ? `${daily.symbol}: ${daily.state.replace('_', ' ')} — ${daily.note}` : 'the daily forecast is off'}</div>}
      </div>
    </div>
  );
}

export default function StudyReport({ symbol, daily, ranking, showDaily, showRanking, err, s, onChange, onSymbol }: Props) {
  const [method, setMethod] = useState(false);
  if (!showDaily && !showRanking) return null;
  const d = daily && daily.symbol === symbol ? daily : null;
  const dec = d?.decimals ?? 2;
  return (
    <div className={'study-report' + (s.report ? '' : ' closed')} data-testid="study-report">
      <div className="sr-head">
        <b>FORECASTING STUDIES</b><span className="tag">TERMINAL STUDY · NOT SIGNALMESH</span><span style={{ flex: 1 }} />
        <button onClick={() => setMethod(true)} data-testid="fc-method" title="how it is calculated, from which closed bars, and when">ⓘ method</button>
        <button onClick={() => onChange({ ...s, report: !s.report })} data-testid="fc-report-toggle" title={s.report ? 'fold the report (the lines stay on the chart)' : 'open the report'}>{s.report ? '▾' : '▸'}</button>
      </div>
      {s.report && <div className="sr-body">
        {err && <div className="bad">{err}</div>}
        {showDaily && <section data-testid="fc-daily-report">
          <h5>DAILY FORECAST · {symbol} <span className="dim">· broker day · closed bars</span></h5>
          {!d ? <div className="dim">loading…</div> : d.state !== 'OK' ? <div className="warn" data-testid="fc-daily-state">NOT AVAILABLE — {d.note}</div> : <>
            <table className="grid sr"><tbody>
              <tr><td>FORECAST TOP</td><td className="mono" style={{ color: '#f87171' }} data-testid="fc-top"><b>{px(d.top, dec)}</b></td><td className="dim">{d.top_done ? 'reached — equals today\'s high' : `day low ${px(d.day_low, dec)} + ADR`}{d.top_snapped_to ? ` · snapped to ${d.top_snapped_to}` : ''}</td></tr>
              <tr><td>FORECAST BOTTOM</td><td className="mono" style={{ color: '#4ade80' }} data-testid="fc-bottom"><b>{px(d.bottom, dec)}</b></td><td className="dim">{d.bottom_done ? 'reached — equals today\'s low' : `day high ${px(d.day_high, dec)} − ADR`}{d.bottom_snapped_to ? ` · snapped to ${d.bottom_snapped_to}` : ''}</td></tr>
              <tr><td>ADR ({d.adr_days} days)</td><td className="mono">{px(d.adr, dec)}</td><td className="dim">used <b className={d.used_pct! >= 100 ? 'warn' : ''}>{pct(d.used_pct)}</b> · day move {d.move_pct! >= 0 ? '+' : ''}{d.move_pct!.toFixed(0)}% of ADR</td></tr>
              <tr><td>STATUS</td><td colSpan={2} className={d.top_done ? 'warn' : ''} data-testid="fc-status">{d.status}{d.completed_by ? ` · completed by a new ${d.completed_by.side === 'TOP' ? 'HIGH' : 'LOW'} at ${fmtTs(new Date(d.completed_by.bar * 1000).toISOString())}` : ''}</td></tr>
              <tr><td>ROOM LEFT</td><td colSpan={2} className="mono">{px(d.room_up, dec)} up · {px(d.room_down, dec)} down <span className="dim">from last closed {px(d.last, dec)}</span></td></tr>
              <tr><td>CONFIDENCE</td><td colSpan={2}><b>{d.journal?.some((g) => g.finished >= 20) ? d.journal.filter((g) => g.finished >= 20).map((g) => `${g.origin} TP1 ${g.tp1_rate_pct}% (${g.sample})`).join(' · ') : 'UNKNOWN'}</b> <span className="dim">— {d.journal?.length ? d.journal.map((g) => `${g.origin}: ${g.finished} finished of ${g.recorded} recorded`).join(' · ') + ' · under 20 is luck' : 'no scored forecasts in the journal yet'}</span></td></tr>
            </tbody></table>
            <div className="dim">levels are CALCULATED · through bar close {fmtTs(d.through_close_utc)} · day ends about {fmtTs(d.day_end_utc)} (ESTIMATE)</div>
            {d.scenarios.length ? d.scenarios.map((sc) => (
              <div className={`scen ${sc.side}`} key={sc.made_bar + sc.direction} data-testid="fc-scenario">
                <div><b className={sc.side === 'bullish' ? 'good' : 'bad'}>{sc.side.toUpperCase()} SCENARIO · {sc.direction}</b> · {sc.pattern} · <b>{sc.status}</b> <span className="tag hyp">{sc.level_label}</span></div>
                <table className="grid sr"><thead><tr><th>Entry</th><th>SL</th><th>TP1</th><th>TP2</th><th>R:R</th><th>Invalidation</th><th>Confidence</th></tr></thead>
                  <tbody><tr className="mono"><td>{px(sc.entry, dec)}</td><td className="bad">{px(sc.sl, dec)}</td><td>{px(sc.tp1, dec)}</td><td>{px(sc.tp2, dec)}</td><td>{sc.rr1 ?? '—'} / {sc.rr2 ?? '—'}</td><td>close beyond {px(sc.invalidation, dec)}</td><td>{sc.confidence}</td></tr></tbody></table>
                <div className="dim">made on the bar of {fmtTs(sc.made_bar_utc)} · horizon: {sc.horizon} · {sc.rule} · recorded in the Forecast Journal</div>
              </div>)) : <div className="dim" data-testid="fc-no-scenario">No scenario: the day's range has not reached ADR. Bullish scenario: NOT AVAILABLE · bearish scenario: NOT AVAILABLE — a scenario exists only once the range is full.</div>}
            <table className="grid sr" data-testid="fc-outlooks"><thead><tr><th>Outlook</th><th>Top</th><th>Bottom</th><th>Avg range</th><th>Used</th></tr></thead><tbody>
              <tr><td>daily</td><td className="mono">{px(d.top, dec)}</td><td className="mono">{px(d.bottom, dec)}</td><td className="mono">{px(d.adr, dec)}</td><td>{pct(d.used_pct)}</td></tr>
              {Object.entries(d.outlooks).map(([k, o]) => o.state === 'OK'
                ? <tr key={k}><td>{k}</td><td className="mono">{px(o.top, dec)}</td><td className="mono">{px(o.bottom, dec)}</td><td className="mono">{px(o.avg_range, dec)}</td><td>{pct(o.used_pct)}</td></tr>
                : <tr key={k}><td>{k}</td><td colSpan={4} className="dim"><b>UNKNOWN</b> — {o.note}</td></tr>)}
            </tbody></table>
            <div className="dim">longer outlooks: the same formula on closed weeks / months / quarters (terminal's extension, not in Pine) · CALCULATED levels, ESTIMATED horizons · confidence UNKNOWN</div>
          </>}
        </section>}
        {showRanking && <section data-testid="fc-ranking-report">
          <h5>ASSET RANKING · room left in today's range {ranking && <span className="dim">· sessions: {['asia', 'london', 'ny'].filter((k) => ranking.sessions[k as 'asia']).map((k) => k.toUpperCase()).join(' + ') || 'none open'}</span>}</h5>
          {!ranking ? <div className="dim">loading…</div> : <>
            <div className="go" data-testid="fc-go">GO TRADE: {ranking.go_trade}</div>
            <table className="grid sr" data-testid="fc-ranking"><thead><tr><th>#</th><th>Asset</th><th>ADR used</th><th>Day move</th><th>State</th><th>What to do</th><th>Score</th></tr></thead><tbody>
              {ranking.rows.map((r) => <tr key={r.symbol} className={'row' + (r.symbol === symbol ? ' sel' : '')} onClick={() => onSymbol?.(r.symbol)} style={{ cursor: onSymbol ? 'pointer' : undefined }} title={r.note || (r.session_ok === false ? 'outside its active session: score halved' : '')}>
                <td className="mono">{r.rank ?? '—'}</td><td><b>{r.symbol}</b>{r.symbol === ranking.go_symbol ? <span className="good"> ★</span> : null}</td><td className="mono">{pct(r.used_pct)}</td>
                <td className={`mono ${r.move_pct == null ? '' : r.move_pct >= 0 ? 'good' : 'bad'}`}>{r.move_pct == null ? '—' : `${r.move_pct >= 0 ? '+' : ''}${r.move_pct.toFixed(0)}%`}</td>
                <td className={stateTone(r.state)}>{r.state}</td><td>{r.action}</td><td className="mono">{r.score ?? '—'}{r.session_ok === false ? <span className="dim"> ½</span> : null}</td></tr>)}
            </tbody></table>
            <div className="dim">{ranking.note} Day move is in % of ADR. ½ = outside its session.</div>
          </>}
        </section>}
      </div>}
      {method && <ForecastMethod daily={d} ranking={ranking} onClose={() => setMethod(false)} />}
    </div>
  );
}
