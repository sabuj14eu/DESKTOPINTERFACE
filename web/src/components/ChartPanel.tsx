import { useEffect, useRef } from 'react';
import { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineStyle, createChart, createSeriesMarkers,
  type IChartApi, type IPriceLine, type ISeriesApi, type ISeriesMarkersPluginApi, type SeriesMarker, type Time, type UTCTimestamp } from 'lightweight-charts';
import type { CandleSeries, DecisionView, SignalRef } from '../api/types';
import { fmtAge, fmtTs, px, toneOf } from '../util';

interface Props { series: CandleSeries | null; seriesErr: string; decision: DecisionView | null; signals: SignalRef[]; symbol: string; tf: string }

const COLORS = { entry: '#38bdf8', sl: '#f43f5e', tp: '#a78bfa', stale: '#64748b', ladder: '#334155' };

export default function ChartPanel({ series, seriesErr, decision, signals, symbol, tf }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volume = useRef<ISeriesApi<'Histogram'> | null>(null);
  const lines = useRef<IPriceLine[]>([]);
  const markers = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const lastKey = useRef('');

  useEffect(() => {
    if (!host.current) return;
    const c = createChart(host.current, {
      layout: { background: { type: ColorType.Solid, color: '#0b1220' }, textColor: '#8392a8', fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11 },
      grid: { vertLines: { color: '#111a2c' }, horzLines: { color: '#111a2c' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.08, bottom: 0.22 } },
      timeScale: { borderColor: '#1e293b', timeVisible: true, secondsVisible: false, rightOffset: 6 },
      autoSize: true,
    });
    const cs = c.addSeries(CandlestickSeries, { upColor: '#22c55e', downColor: '#f43f5e', borderVisible: false, wickUpColor: '#22c55e', wickDownColor: '#f43f5e' });
    const vs = c.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'vol', color: '#1f2b44' });
    c.priceScale('vol').applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });
    chart.current = c; candles.current = cs; volume.current = vs;
    markers.current = createSeriesMarkers(cs, []);
    return () => { c.remove(); chart.current = null; candles.current = null; volume.current = null; markers.current = null; lastKey.current = ''; };
  }, []);

  // candles
  useEffect(() => {
    const cs = candles.current, vs = volume.current, c = chart.current;
    if (!cs || !vs || !c || !series) return;
    const key = `${series.symbol}:${series.tf}`;
    cs.applyOptions({ priceFormat: { type: 'price', precision: series.decimals, minMove: Number((10 ** -series.decimals).toFixed(series.decimals)) } });
    cs.setData(series.candles.map((k) => ({ time: k.time as UTCTimestamp, open: k.open, high: k.high, low: k.low, close: k.close })));
    vs.setData(series.candles.map((k) => ({ time: k.time as UTCTimestamp, value: k.volume ?? 0, color: k.close >= k.open ? 'rgba(34,197,94,.25)' : 'rgba(244,63,94,.25)' })));
    if (lastKey.current !== key) { c.timeScale().fitContent(); lastKey.current = key; }
  }, [series]);

  // levels + markers
  useEffect(() => {
    const cs = candles.current;
    if (!cs) return;
    lines.current.forEach((l) => cs.removePriceLine(l));
    lines.current = [];
    if (decision) {
      for (const l of decision.levels) {
        lines.current.push(cs.createPriceLine({
          price: l.value, color: l.stale ? COLORS.stale : COLORS[l.kind], lineWidth: l.stale ? 1 : 2,
          lineStyle: l.kind === 'tp' || l.stale ? LineStyle.Dashed : LineStyle.Solid, axisLabelVisible: true,
          title: l.label + (l.stale ? ' (expired)' : ''),
        }));
      }
      for (const lv of decision.levels_ladder.slice(0, 12)) {
        if (typeof lv.value === 'number') {
          lines.current.push(cs.createPriceLine({ price: lv.value, color: COLORS.ladder, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: String(lv.name ?? '') }));
        }
      }
    }
    const first = series?.candles[0]?.time ?? 0;
    const ms: SeriesMarker<Time>[] = signals
      .filter((s) => s.symbol === symbol && s.created_at && (s.direction === 'BUY' || s.direction === 'SELL'))
      .map((s) => {
        const t = Math.floor(new Date(s.created_at!).getTime() / 1000);
        return { s, t };
      })
      .filter(({ t }) => t >= first)
      .map(({ s, t }): SeriesMarker<Time> => ({
        time: snap(t, tf) as UTCTimestamp, position: s.direction === 'BUY' ? 'belowBar' : 'aboveBar',
        color: s.bucket === 'REJECTED' ? '#64748b' : s.direction === 'BUY' ? '#22c55e' : '#f43f5e',
        shape: s.direction === 'BUY' ? 'arrowUp' : 'arrowDown',
        text: `${s.direction} ${s.status}${s.grade ? ' ' + s.grade : ''}`,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));
    markers.current?.setMarkers(ms);
  }, [decision, signals, series, symbol, tf]);

  const f = series?.freshness;
  return (
    <div className="chart">
      <div className="chart-head">
        <b>{symbol}</b><span className="dim">{tf.toUpperCase()} · closed bars only · times UTC</span>
        {f && <span className={`pill ${toneOf(f.state)}`} title={f.detail}>{f.state}{f.age_min != null ? ` · newest bar ${fmtAge(f.age_min)} old` : ''}</span>}
        {series && <span className="dim">{series.count} bars · source: {series.provenance.source} · engine {fmtTs(series.provenance.engine_as_of)}</span>}
        <span style={{ flex: 1 }} />
        <div className="legend">
          <span style={{ color: COLORS.entry }}>Entry</span><span style={{ color: COLORS.sl }}>SL</span>
          <span className="dashed" style={{ color: COLORS.tp }}>TP1 / TP2</span><span className="dashed" style={{ color: COLORS.stale }}>expired plan</span>
          <span className="dashed" style={{ color: '#475569' }}>structural ladder</span>
        </div>
      </div>
      <div className="chart-body">
        <div ref={host} />
        {seriesErr && <div className="overlay bad">{seriesErr}</div>}
        {!seriesErr && series && series.count === 0 && <div className="overlay">no closed {tf} candles stored for {symbol} — nothing is drawn from guesswork</div>}
        {!seriesErr && !series && <div className="overlay">loading candles…</div>}
      </div>
      <div className="chart-foot">
        {decision ? (
          <>
            <span><b className="dim">CONFIRMATION:</b> {decision.lane.confirmation_text} <b className={toneOf(decision.lane.confirmation_status)}>→ {decision.lane.stage}</b></span>
            <span className="dim">ATR {px(decision.atr, decision.decimals)} · structure {decision.structure ?? 'UNKNOWN'} · bias {decision.bias ?? 'UNKNOWN'} · last close {px(decision.last_close, decision.decimals)} @ {fmtTs(decision.last_bar_ts)}</span>
            {decision.levels.length > 0 && <span className="dim" title={decision.levels_rule}>levels from {decision.levels[0].origin}{decision.levels[0].stale ? ' — EXPIRED, shown as history' : ''}</span>}
          </>
        ) : <span className="dim">decision pending…</span>}
      </div>
    </div>
  );
}

const TF_SEC: Record<string, number> = { '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400 };
function snap(t: number, tf: string) { const s = TF_SEC[tf] ?? 900; return Math.floor(t / s) * s; }
