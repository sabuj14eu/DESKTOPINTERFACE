import { useEffect, useRef, useState } from 'react';
import { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineStyle, createChart, createSeriesMarkers,
  type IChartApi, type IPriceLine, type ISeriesApi, type ISeriesMarkersPluginApi, type MouseEventParams, type SeriesMarker, type Time, type UTCTimestamp } from 'lightweight-charts';
import type { CandleSeries, DecisionView, SignalRef } from '../api/types';
import { fmtAge, fmtHM, fmtTs, px, sourceTone, sourceWord, toneOf } from '../util';

interface Props { series: CandleSeries | null; seriesErr: string; decision: DecisionView | null; signals: SignalRef[]; symbol: string; tf: string }

const COLORS = { entry: '#38bdf8', sl: '#f43f5e', tp: '#a78bfa', stale: '#64748b', ladder: '#2b3a55', up: '#26a69a', down: '#ef5350' };
const TF_SEC: Record<string, number> = { '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400 };
const snap = (t: number, tf: string) => { const s = TF_SEC[tf] ?? 900; return Math.floor(t / s) * s; };

type Hover = { time: number; open: number; high: number; low: number; close: number; volume: number } | null;

export default function ChartPanel({ series, seriesErr, decision, signals, symbol, tf }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volume = useRef<ISeriesApi<'Histogram'> | null>(null);
  const lines = useRef<IPriceLine[]>([]);
  const markers = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const lastKey = useRef('');
  const dataRef = useRef<CandleSeries | null>(null);
  const [hover, setHover] = useState<Hover>(null);
  const [showExpired, setShowExpired] = useState(false);
  const [showLadder, setShowLadder] = useState(true);
  const [showMarkers, setShowMarkers] = useState(true);

  useEffect(() => {
    if (!host.current) return;
    const c = createChart(host.current, {
      layout: { background: { type: ColorType.Solid, color: '#0b1220' }, textColor: '#8392a8', fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11 },
      grid: { vertLines: { color: '#111a2c' }, horzLines: { color: '#111a2c' } },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: '#475569', labelBackgroundColor: '#1e293b', width: 1, style: LineStyle.Dashed },
        horzLine: { color: '#475569', labelBackgroundColor: '#1e293b', width: 1, style: LineStyle.Dashed } },
      rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.06, bottom: 0.2 }, autoScale: true, entireTextOnly: true },
      timeScale: { borderColor: '#1e293b', timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 7, minBarSpacing: 2 },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: { time: true, price: true }, axisDoubleClickReset: true },
      autoSize: true,
    });
    const cs = c.addSeries(CandlestickSeries, { upColor: COLORS.up, downColor: COLORS.down, borderUpColor: COLORS.up, borderDownColor: COLORS.down,
      wickUpColor: COLORS.up, wickDownColor: COLORS.down, lastValueVisible: true, priceLineVisible: true, priceLineColor: '#64748b', priceLineStyle: LineStyle.Dotted });
    const vs = c.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'vol', color: '#1f2b44', lastValueVisible: false, priceLineVisible: false });
    c.priceScale('vol').applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
    chart.current = c; candles.current = cs; volume.current = vs;
    markers.current = createSeriesMarkers(cs, []);
    const onMove = (p: MouseEventParams<Time>) => {
      const d = p.seriesData.get(cs) as { open?: number; high?: number; low?: number; close?: number } | undefined;
      const v = p.seriesData.get(vs) as { value?: number } | undefined;
      if (!p.time || !d || d.open === undefined) { setHover(null); return; }
      setHover({ time: p.time as number, open: d.open!, high: d.high!, low: d.low!, close: d.close!, volume: v?.value ?? 0 });
    };
    c.subscribeCrosshairMove(onMove);
    return () => { c.unsubscribeCrosshairMove(onMove); c.remove(); chart.current = null; candles.current = null; volume.current = null; markers.current = null; lastKey.current = ''; };
  }, []);

  // candles — keep the user's zoom when only new bars arrive; refit on symbol/tf change
  useEffect(() => {
    const cs = candles.current, vs = volume.current, c = chart.current;
    if (!cs || !vs || !c) return;
    if (!series || series.symbol !== symbol || series.tf !== tf) {
      // nothing (yet) for THIS symbol/timeframe: clear the canvas rather than leave another series on it
      cs.setData([]); vs.setData([]); lastKey.current = '';
      return;
    }
    dataRef.current = series;
    const key = `${series.symbol}:${series.tf}`;
    const minMove = Number((10 ** -series.decimals).toFixed(series.decimals));
    cs.applyOptions({ priceFormat: { type: 'price', precision: series.decimals, minMove } });
    cs.setData(series.candles.map((k) => ({ time: k.time as UTCTimestamp, open: k.open, high: k.high, low: k.low, close: k.close })));
    vs.setData(series.candles.map((k) => ({ time: k.time as UTCTimestamp, value: k.volume ?? 0, color: k.close >= k.open ? 'rgba(38,166,154,.3)' : 'rgba(239,83,80,.3)' })));
    if (lastKey.current !== key) {
      const n = series.candles.length;
      c.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 160), to: n + 6 });
      lastKey.current = key;
    }
  }, [series, symbol, tf]);

  // levels + markers
  useEffect(() => {
    const cs = candles.current;
    if (!cs) return;
    lines.current.forEach((l) => cs.removePriceLine(l));
    lines.current = [];
    if (decision) {
      const dec = decision.decimals;
      const ref = decision.price.last_closed_1m?.price ?? decision.last_close;
      const dist = (v: number) => (ref != null && decision.atr ? ` ${((v - ref) / decision.atr).toFixed(1)}ATR` : '');
      for (const l of decision.levels) {
        lines.current.push(cs.createPriceLine({ price: l.value, color: COLORS[l.kind], lineWidth: 2,
          lineStyle: l.kind === 'tp' ? LineStyle.Dashed : LineStyle.Solid, axisLabelVisible: true, title: `${l.label} ${px(l.value, dec)}${dist(l.value)}` }));
      }
      if (showExpired && decision.expired_plan) {
        for (const l of decision.expired_plan.levels) {
          lines.current.push(cs.createPriceLine({ price: l.value, color: COLORS.stale, lineWidth: 1, lineStyle: LineStyle.SparseDotted, axisLabelVisible: true, title: `${l.label} (history)` }));
        }
      }
      if (showLadder) {
        for (const lv of decision.levels_ladder.slice(0, 14)) {
          if (typeof lv.value === 'number') lines.current.push(cs.createPriceLine({ price: lv.value, color: COLORS.ladder, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: String(lv.name ?? '') }));
        }
      }
    }
    const first = series?.candles[0]?.time ?? 0;
    const ms: SeriesMarker<Time>[] = showMarkers ? signals
      .filter((s) => s.symbol === symbol && s.created_at && (s.direction === 'BUY' || s.direction === 'SELL'))
      .map((s) => ({ s, t: Math.floor(new Date(s.created_at!).getTime() / 1000) }))
      .filter(({ t }) => t >= first)
      .map(({ s, t }): SeriesMarker<Time> => ({
        time: snap(t, tf) as UTCTimestamp, position: s.direction === 'BUY' ? 'belowBar' : 'aboveBar',
        color: s.bucket === 'REJECTED' ? '#64748b' : s.bucket === 'EXPIRED' ? (s.direction === 'BUY' ? '#3f8f7a' : '#8f3f4a') : s.direction === 'BUY' ? '#26a69a' : '#ef5350',
        shape: s.direction === 'BUY' ? 'arrowUp' : 'arrowDown', size: s.bucket === 'ACTIVE' ? 2 : 1,
        text: `${s.direction} ${s.bucket === 'ACTIVE' ? 'ACTIVE' : s.status.toUpperCase()}${s.grade ? ' ' + s.grade : ''} · ${s.signal_id}`,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number)) : [];
    markers.current?.setMarkers(ms);
  }, [decision, signals, series, symbol, tf, showExpired, showLadder, showMarkers]);

  const zoom = (f: number) => {
    const c = chart.current; const r = c?.timeScale().getVisibleLogicalRange();
    if (!c || !r) return;
    const mid = (r.from + r.to) / 2, half = ((r.to - r.from) / 2) * f;
    c.timeScale().setVisibleLogicalRange({ from: mid - half, to: mid + half });
  };
  const latest = () => chart.current?.timeScale().scrollToRealTime();
  const fit = () => chart.current?.timeScale().fitContent();

  const f = series?.freshness;
  const lb = series?.last_bar;
  const dec = series?.decimals ?? decision?.decimals ?? 2;
  const h = hover;
  return (
    <div className="chart">
      <div className="chart-head">
        <b>{symbol}</b><span className="dim">{tf.toUpperCase()} · closed bars only · UTC</span>
        {f && <span className={`pill ${toneOf(f.state)}`} title={`${f.detail || ''} · engine gate ${fmtAge(f.age_min)} since open / limit ${fmtAge(f.limit_min)}`}>{f.state}</span>}
        {series && <span className={`pill ${sourceTone(series.source_kind)}`} title={series.source_warning || `per-candle source: ${lb?.source}`}>{sourceWord(series.source_kind)}</span>}
        {lb && <span className="dim" title="price-contract-v1: chart_last_bar">last bar <b className="mono" style={{ color: '#e2e8f0' }}>{px(lb.price, dec)}</b> · {fmtHM(lb.bar_open_ts)}–{fmtHM(lb.bar_close_ts)} · closed {fmtAge(Math.max(lb.since_close_min ?? 0, 0))} ago</span>}
        <span style={{ flex: 1 }} />
        <span className="chart-tools">
          <button onClick={() => zoom(0.7)} title="zoom in">+</button><button onClick={() => zoom(1.4)} title="zoom out">−</button>
          <button onClick={fit} title="fit all bars">fit</button><button onClick={latest} title="scroll to newest bar">latest</button>
          <label><input type="checkbox" checked={showMarkers} onChange={(e) => setShowMarkers(e.target.checked)} /> signals</label>
          <label><input type="checkbox" checked={showLadder} onChange={(e) => setShowLadder(e.target.checked)} /> ladder</label>
          <label title="expired plans are history; off by default"><input type="checkbox" checked={showExpired} onChange={(e) => setShowExpired(e.target.checked)} /> expired plan</label>
        </span>
      </div>
      <div className="chart-sub">
        <span className="ohlc mono">
          {h ? <>{fmtTs(new Date(h.time * 1000).toISOString())} · O <b>{px(h.open, dec)}</b> H <b>{px(h.high, dec)}</b> L <b>{px(h.low, dec)}</b> C <b className={h.close >= h.open ? 'good' : 'bad'}>{px(h.close, dec)}</b> · vol {Math.round(h.volume)}</>
            : lb ? <>newest bar {fmtTs(lb.bar_open_ts)} · O/H/L/C of the hovered bar appear here</> : '—'}
        </span>
        <span className="legend">
          <span style={{ color: COLORS.entry }}>Entry</span><span style={{ color: COLORS.sl }}>SL</span><span className="dashed" style={{ color: COLORS.tp }}>TP1 / TP2</span>
          <span className="dashed" style={{ color: COLORS.stale }}>expired (history, off)</span><span className="dashed" style={{ color: '#475569' }}>ladder</span>
          <span className="dim" style={{ marginLeft: 6 }}>{series ? `${series.count} bars · per-candle source: ${series.last_bar?.source || 'unstated'} · platform label: ${series.platform_label}` : ''}</span>
        </span>
      </div>
      <div className="chart-body">
        <div ref={host} />
        {seriesErr && <div className="overlay bad">{symbol} {tf.toUpperCase()} candles could not be loaded: {seriesErr}</div>}
        {!seriesErr && series && series.symbol === symbol && series.count === 0 && <div className="overlay">no closed {tf} candles stored for {symbol} — nothing is drawn from guesswork</div>}
        {!seriesErr && (!series || series.symbol !== symbol || series.tf !== tf) && <div className="overlay">loading {symbol} {tf.toUpperCase()} candles…</div>}
      </div>
      <div className="chart-foot">
        {decision ? (
          <>
            <span><b className="dim">CONFIRMATION:</b> {decision.lane.confirmation_text} <b className={toneOf(decision.lane.confirmation_status)}>→ {decision.lane.stage}</b></span>
            <span className="dim" title="price-contract-v1: engine_reference — the 15m closed bar the decision, ATR and structure were measured on">engine ref <b className="mono" style={{ color: '#cbd5e1' }}>{px(decision.price.engine_reference?.price, decision.decimals)}</b> (15m bar {fmtHM(decision.price.engine_reference?.bar_open_ts)}–{fmtHM(decision.price.engine_reference?.bar_close_ts)}) · ATR {px(decision.atr, decision.decimals)} · structure {decision.structure ?? 'UNKNOWN'} · bias {decision.bias ?? 'UNKNOWN'}</span>
            {decision.price.drift?.state && <span className={decision.price.drift.state === 'MOVED' ? 'warn' : 'dim'} title={decision.price.drift.reason}>drift {decision.price.drift.state}{decision.price.drift.drift_atr != null ? ` ${decision.price.drift.drift_atr} ATR vs latest ${decision.price.drift.latest_bar_tf} bar` : ''}</span>}
            {decision.levels.length > 0 ? <span className="dim" title={decision.levels_rule}>levels: {decision.levels[0].origin}</span> : <span className="dim">no current levels{decision.expired_plan ? ` · last plan ${decision.expired_plan.signal.signal_id} expired → Trade History` : ''}</span>}
          </>
        ) : <span className="dim">decision pending…</span>}
      </div>
    </div>
  );
}
