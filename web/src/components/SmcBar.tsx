import { useState } from 'react';
import { SMC_DEFAULT, SMC_FEATURES, SMC_TFS, SMC_TF_LABEL, SMC_TF_MIN, smcAll, smcTfFor, type SmcData, type SmcFeature, type SmcSettings } from '../smc';
import { fmtTs } from '../util';

/** SMART MONEY CONCEPTS — one independent switch per study, each with its own analysis timeframe. */
export default function SmcBar({ s, onChange, chartTf, data, counts, error }: { s: SmcSettings; onChange: (n: SmcSettings) => void; chartTf: string; data: Record<string, SmcData | undefined>; counts: Record<SmcFeature, number>; error: string }) {
  const [method, setMethod] = useState(false);
  const base = chartTf === '1m' ? '5m' : chartTf;
  const any = SMC_FEATURES.some((f) => s.on[f.id]);
  const loaded = Object.values(data).filter(Boolean) as SmcData[];
  return (
    <div className="smc-bar" role="toolbar" aria-label="Smart Money Concepts" data-testid="smc-bar">
      <b className="smc-title" title="display-only chart studies computed by the terminal from stored closed candles — never an input to the SignalMesh engine">SMART MONEY CONCEPTS</b>
      {SMC_FEATURES.map((f) => { const tf = smcTfFor(s, f.id, chartTf); const st = data[tf]?.state; return (
        <span className={'smc-item' + (s.on[f.id] ? ' on' : '')} key={f.id}>
          <button className={s.on[f.id] ? 'on' : ''} data-testid={`smc-${f.id}`} aria-pressed={s.on[f.id]} onClick={() => onChange({ ...s, on: { ...s.on, [f.id]: !s.on[f.id] } })}
            title={`${f.name} — ${s.on[f.id] ? 'ON' : 'OFF'}${s.on[f.id] && st && st !== 'OK' ? ` · ${SMC_TF_LABEL[tf]}: ${st}` : ''}`}>{s.on[f.id] ? '●' : '○'} {f.short}{s.on[f.id] ? <span className="cnt">{counts[f.id]}</span> : null}</button>
          <select value={s.tf[f.id] !== 'chart' && SMC_TF_MIN[s.tf[f.id]] >= SMC_TF_MIN[base] ? s.tf[f.id] : 'chart'} aria-label={`${f.name} timeframe`} data-testid={`smc-tf-${f.id}`}
            onChange={(e) => onChange({ ...s, tf: { ...s.tf, [f.id]: e.target.value } })} title="analysis timeframe for this study (the chart's own, or a higher one)">
            <option value="chart">{SMC_TF_LABEL[base]}</option>
            {SMC_TFS.filter((t) => SMC_TF_MIN[t] > SMC_TF_MIN[base]).map((t) => <option key={t} value={t}>{SMC_TF_LABEL[t]}</option>)}
          </select>
        </span>); })}
      <span className="tool-group">
        <button onClick={() => onChange(smcAll(s, true))} data-testid="smc-show-all">show all</button>
        <button onClick={() => onChange(smcAll(s, false))} data-testid="smc-hide-all" disabled={!any}>hide all</button>
        <button onClick={() => onChange(SMC_DEFAULT)} data-testid="smc-reset" title="every study off, chart timeframe, both sides, no history, default opacity">reset</button>
      </span>
      <span className="tool-group">
        <select value={s.side} onChange={(e) => onChange({ ...s, side: e.target.value as SmcSettings['side'] })} aria-label="Bullish or bearish" data-testid="smc-side">
          <option value="both">bullish + bearish</option><option value="bull">bullish only</option><option value="bear">bearish only</option></select>
        <label title="also draw resolved structures: mitigated gaps, invalidated blocks, swept liquidity, older breaks"><input type="checkbox" checked={s.history} onChange={(e) => onChange({ ...s, history: e.target.checked })} data-testid="smc-history" /> history</label>
        <label title="zone opacity">opacity <input type="range" min={5} max={50} value={Math.round(s.opacity * 100)} onChange={(e) => onChange({ ...s, opacity: Number(e.target.value) / 100 })} style={{ width: 70 }} aria-label="Zone opacity" /></label>
        <button onClick={() => setMethod(true)} data-testid="smc-method" title="how every overlay is calculated, and when">ⓘ method</button>
      </span>
      {error && <span className="bad">{error}</span>}
      {method && <div className="modal-bg" onClick={() => setMethod(false)}>
        <div className="modal about" onClick={(e) => e.stopPropagation()} data-testid="smc-method-panel">
          <div style={{ display: 'flex', alignItems: 'center' }}><h3 style={{ margin: 0 }}>Smart Money Concepts — how it is calculated</h3><span style={{ flex: 1 }} /><button onClick={() => setMethod(false)}>✕</button></div>
          <p className="warn" style={{ fontSize: 12 }}>Display-only studies calculated by this terminal from SignalMesh's stored CLOSED candles. They do not come from the SignalMesh engine or the Pine sensor, and they change no recommendation, entry, stop-loss, take-profit, confidence score, order or statistic.</p>
          <p className="muted" style={{ fontSize: 12 }}>{loaded[0]?.rule ?? 'smc-v1'}</p>
          <h4>Method</h4>
          <div className="kv wide">{Object.entries(loaded[0]?.methodology ?? {}).map(([k, v]) => <span key={k} style={{ display: 'contents' }}><span className="k">{k.replace('_', ' ')}</span><span>{v}</span></span>)}</div>
          {!loaded.length && <div className="dim">switch a study on to load the method text and the calculation times</div>}
          <h4>Calculations on screen</h4>
          <table className="grid"><thead><tr><th>Timeframe</th><th>State</th><th>Closed bars used</th><th>Through bar close (UTC)</th><th>Calculated (UTC)</th><th>Trend ext / int</th><th>Source</th></tr></thead>
            <tbody>{loaded.map((d) => <tr key={d.tf}><td><b>{SMC_TF_LABEL[d.tf]}</b></td><td className={d.state === 'OK' ? 'good' : 'warn'}>{d.state}</td><td>{d.bars_used}</td>
              <td>{d.through_close ? fmtTs(new Date(d.through_close * 1000).toISOString()) : '—'}</td><td>{fmtTs(d.calculated_at)}</td><td>{d.trend.external ?? '—'} / {d.trend.internal ?? '—'}</td><td className="dim" style={{ whiteSpace: 'normal' }}>{d.source}{d.note ? ` · ${d.note}` : ''}</td></tr>)}</tbody></table>
        </div>
      </div>}
    </div>
  );
}
