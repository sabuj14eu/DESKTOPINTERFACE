import { useEffect, useRef, useState } from 'react';
import { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, LineStyle, PriceScaleMode, createChart, createSeriesMarkers,
  type IChartApi, type IPriceLine, type ISeriesApi, type ISeriesMarkersPluginApi, type MouseEventParams, type SeriesMarker, type Time, type UTCTimestamp } from 'lightweight-charts';
import type { CandleSeries, Coverage, DecisionView, LiveBars, SignalRef } from '../api/types';
import { api } from '../api/client';
import { FORECAST_NOTE, FORECAST_STUDIES, type DailyForecast, type FcSettings, type Ranking } from '../forecast';
import { INDICATORS, INDICATOR_NOTE } from '../indicators';
import { SMC_FEATURES, SmcPrimitive, buildShapes, smcTfFor, type SmcData, type SmcFeature, type SmcLevel, type SmcSettings } from '../smc';
import SmcBar from './SmcBar';
import StudyReport, { ForecastMethod } from './StudyReport';
import { fmtAge, fmtHM, fmtTs, px, sourceTone, sourceWord, tfLabel, toneOf } from '../util';
import type { Workspace } from '../workspace';

interface Props {
  series: CandleSeries | null; seriesErr: string; decision: DecisionView | null; signals: SignalRef[]; symbol: string; tf: string; coverage: Coverage | null; live?: LiveBars | null;
  opts: Workspace['chart']; onOpts: (p: Partial<Workspace['chart']>) => void; bars: number; onBars: (n: number) => void;
  indicators: string[]; onIndicators: (ids: string[]) => void; smc: SmcSettings; onSmc: (s: SmcSettings) => void; fc: FcSettings; onFc: (s: FcSettings) => void; onSymbol?: (s: string) => void; full: boolean; onFull: () => void; onSignal: (id: string) => void; compact?: boolean;
}

const COLORS = { entry: '#38bdf8', sl: '#f43f5e', tp: '#a78bfa', stale: '#64748b', ladder: '#2b3a55', up: '#26a69a', down: '#ef5350' };
const TF_SEC: Record<string, number> = { '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400 };
const snap = (t: number, tf: string) => { const s = TF_SEC[tf] ?? 900; return Math.floor(t / s) * s; };
const utc = (t: number) => new Date(t * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';

type Hover = { time: number; open: number; high: number; low: number; close: number; volume: number } | null;

export default function ChartPanel({ series, seriesErr, decision, signals, symbol, tf, coverage, live, opts, onOpts, bars, onBars, indicators, onIndicators, smc, onSmc, fc, onFc, onSymbol, full, onFull, onSignal, compact }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volume = useRef<ISeriesApi<'Histogram'> | null>(null);
  const studies = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const lines = useRef<IPriceLine[]>([]);
  const markers = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const markerIds = useRef<Map<number, string[]>>(new Map());
  const onSignalRef = useRef(onSignal); onSignalRef.current = onSignal;
  const lastKey = useRef('');
  const liveDrawn = useRef(0);          // how many display-only bars sit after the closed series right now
  const dataRef = useRef<CandleSeries | null>(null);
  const [hover, setHover] = useState<Hover>(null);
  const [auto, setAuto] = useState(true);
  const [menu, setMenu] = useState(false);
  const smcPrim = useRef<SmcPrimitive | null>(null);
  const [smcData, setSmcData] = useState<Record<string, SmcData | undefined>>({});
  const [smcKeys, setSmcKeys] = useState<SmcLevel[] | undefined>(undefined);
  const [smcErr, setSmcErr] = useState('');
  const smcCounts = useRef<Record<SmcFeature, number>>({ sr: 0, fvg: 0, bos: 0, choch: 0, ob: 0, liq: 0, idm: 0 });
  const [, setSmcTick] = useState(0);
  const smcTfsRef = useRef('');
  // forecasting studies (display only): which are on lives in `indicators`, their data comes from /forecast/*
  const fcDailyOn = indicators.includes('fc-daily'), fcRankOn = indicators.includes('fc-ranking');
  const [fcDaily, setFcDaily] = useState<DailyForecast | null>(null);
  const [fcRank, setFcRank] = useState<Ranking | null>(null);
  const [fcErr, setFcErr] = useState('');
  const [fcMethod, setFcMethod] = useState(false);
  const fcLines = useRef<IPriceLine[]>([]);
  const fcHist = useRef<ISeriesApi<'Line'>[]>([]);
  const fcDrawn = useRef({ lines: 0, history: 0 });

  useEffect(() => {
    if (!host.current) return;
    const c = createChart(host.current, {
      layout: { background: { type: ColorType.Solid, color: '#0b1220' }, textColor: '#8392a8', fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11 },
      grid: { vertLines: { color: '#111a2c' }, horzLines: { color: '#111a2c' } },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: '#475569', labelBackgroundColor: '#1e293b', width: 1, style: LineStyle.Dashed },
        horzLine: { color: '#475569', labelBackgroundColor: '#1e293b', width: 1, style: LineStyle.Dashed } },
      rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.06, bottom: 0.2 }, autoScale: true, entireTextOnly: true },
      timeScale: { borderColor: '#1e293b', timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 7, minBarSpacing: 1 },
      // every candle time is the bar OPEN in UTC; the crosshair label says so in full
      localization: { timeFormatter: (t: Time) => utc(t as number) },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: { time: true, price: true }, axisDoubleClickReset: true },
      autoSize: true,
    });
    const cs = c.addSeries(CandlestickSeries, { upColor: COLORS.up, downColor: COLORS.down, borderUpColor: COLORS.up, borderDownColor: COLORS.down,
      wickUpColor: COLORS.up, wickDownColor: COLORS.down, lastValueVisible: true, priceLineVisible: true, priceLineColor: '#94a3b8', priceLineStyle: LineStyle.Dotted, title: 'last close' });
    const vs = c.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'vol', color: '#1f2b44', lastValueVisible: false, priceLineVisible: false });
    c.priceScale('vol').applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
    chart.current = c; candles.current = cs; volume.current = vs;
    (window as unknown as { __smtChart?: unknown }).__smtChart = {
      range: () => c.timeScale().getVisibleLogicalRange(), bars: () => dataRef.current?.count ?? 0, symbol: () => dataRef.current?.symbol,
      autoScale: () => c.priceScale('right').options().autoScale,
      manualScale: () => c.priceScale('right').applyOptions({ autoScale: false }),      // what a user's axis drag does
      // where the newest candle's close is drawn, in px from the top of the pane (null = off-scale)
      lastBarY: () => { const d = dataRef.current; const k = d?.candles[d.candles.length - 1]; return k ? cs.priceToCoordinate(k.close) : null; },
      paneHeight: () => host.current?.clientHeight ?? 0, paneWidth: () => host.current?.clientWidth ?? 0,
      markers: () => Array.from(markerIds.current.values()).flat(), studies: () => Array.from(studies.current.keys()),
      forecast: () => ({ ...fcDrawn.current }),
      smc: () => ({ counts: { ...smcCounts.current }, drawMs: smcPrim.current?.lastDrawMs ?? 0, tfs: smcTfsRef.current }),
      liveBars: () => liveDrawn.current, lastValue: () => { const d = cs.data(); const k = d[d.length - 1] as { close?: number; time?: number } | undefined; return k ? { time: k.time, close: k.close } : null; },
    };
    markers.current = createSeriesMarkers(cs, []);
    smcPrim.current = new SmcPrimitive(); cs.attachPrimitive(smcPrim.current);
    const onMove = (p: MouseEventParams<Time>) => {
      const d = p.seriesData.get(cs) as { open?: number; high?: number; low?: number; close?: number } | undefined;
      const v = p.seriesData.get(vs) as { value?: number } | undefined;
      if (!p.time || !d || d.open === undefined) { setHover(null); return; }
      setHover({ time: p.time as number, open: d.open!, high: d.high!, low: d.low!, close: d.close!, volume: v?.value ?? 0 });
    };
    // a click on a bar that carries a signal marker opens that signal's full information
    const onClick = (p: MouseEventParams<Time>) => { const ids = p.time ? markerIds.current.get(p.time as number) : undefined; if (ids?.length) onSignalRef.current(ids[0]); };
    const syncAuto = () => setAuto(!!c.priceScale('right').options().autoScale);
    c.subscribeCrosshairMove(onMove); c.subscribeClick(onClick);
    const el = host.current;
    el.addEventListener('pointerup', syncAuto); el.addEventListener('wheel', syncAuto, { passive: true }); el.addEventListener('dblclick', syncAuto);
    return () => { el.removeEventListener('pointerup', syncAuto); el.removeEventListener('wheel', syncAuto); el.removeEventListener('dblclick', syncAuto);
      c.unsubscribeCrosshairMove(onMove); c.unsubscribeClick(onClick); c.remove(); chart.current = null; candles.current = null; volume.current = null; markers.current = null; studies.current.clear(); lastKey.current = ''; };
  }, []);

  // price-scale and crosshair modes
  useEffect(() => {
    const c = chart.current; if (!c) return;
    c.priceScale('right').applyOptions({ mode: opts.log ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal });
    c.applyOptions({ crosshair: { mode: opts.magnet ? CrosshairMode.Magnet : CrosshairMode.Normal } });
    volume.current?.applyOptions({ visible: opts.volume });
    c.priceScale('right').applyOptions({ scaleMargins: { top: 0.06, bottom: opts.volume ? 0.2 : 0.06 } });
  }, [opts.log, opts.magnet, opts.volume]);

  // FOCUS THE LATEST BAR, TradingView-style: the newest candle sits about two thirds across the
  // chart with empty space to its right. Used on every symbol/timeframe switch and by "latest".
  const focusLatest = (n: number) => {
    const c = chart.current; if (!c || !n) return;
    // A dragged or wheel-zoomed price axis switches the scale to MANUAL and it stays manual, so a new
    // symbol with a different price range would be drawn outside the visible area (SOL candles at 89
    // under ETH's 2240 axis). Every focus re-enables auto-scaling.
    c.priceScale('right').applyOptions({ autoScale: true }); setAuto(true);
    const width = host.current?.clientWidth || 900;
    const bars = Math.max(40, Math.min(260, Math.floor(width / 7)));   // ~7 px per bar
    const right = Math.round(bars * 0.32);
    c.timeScale().applyOptions({ rightOffset: right });
    c.timeScale().setVisibleLogicalRange({ from: n - (bars - right), to: n + right });
  };

  // candles — keep the user's zoom when only new bars arrive (unless they were following the
  // newest bar, then keep following); focus the latest bar on symbol/tf change
  useEffect(() => {
    const cs = candles.current, vs = volume.current, c = chart.current;
    if (!cs || !vs || !c) return;
    if (!series || series.symbol !== symbol || series.tf !== tf) {
      // nothing (yet) for THIS symbol/timeframe: clear the canvas rather than leave another series on it
      cs.setData([]); vs.setData([]); studies.current.forEach((s) => s.setData([])); lastKey.current = '';
      return;
    }
    const prevN = dataRef.current && dataRef.current.symbol === series.symbol && dataRef.current.tf === series.tf ? dataRef.current.count : 0;
    const before = c.timeScale().getVisibleLogicalRange();
    const wasFollowing = !!before && prevN > 0 && before.to >= prevN - 2;
    dataRef.current = series;
    const key = `${series.symbol}:${series.tf}`;
    const minMove = Number((10 ** -series.decimals).toFixed(series.decimals));
    cs.applyOptions({ priceFormat: { type: 'price', precision: series.decimals, minMove } });
    cs.setData(series.candles.map((k) => ({ time: k.time as UTCTimestamp, open: k.open, high: k.high, low: k.low, close: k.close })));
    liveDrawn.current = 0;
    vs.setData(series.candles.map((k) => ({ time: k.time as UTCTimestamp, value: k.volume ?? 0, color: k.close >= k.open ? 'rgba(38,166,154,.3)' : 'rgba(239,83,80,.3)' })));
    const n = series.candles.length;
    if (lastKey.current !== key) { focusLatest(n); lastKey.current = key; }
    else if (n !== prevN && before && prevN > 0 && !wasFollowing) {
      // more history arrived on the left (a larger bar count): keep the same bars in view
      const shift = n - prevN; c.timeScale().setVisibleLogicalRange({ from: before.from + shift, to: before.to + shift });
    } else if (wasFollowing && n !== prevN) { c.timeScale().scrollToRealTime(); }
  }, [series, symbol, tf]);

  // THE FORMING BAR (display only): bars newer than the newest closed bar, from /live. They are drawn
  // AFTER the closed series with series.update(), in a lighter colour, and are redrawn whenever the
  // closed series is reset. They never enter `series.candles`, the indicators or the levels.
  useEffect(() => {
    const cs = candles.current;
    if (!cs || !series || series.symbol !== symbol || series.tf !== tf || !series.candles.length) return;
    const lastClosed = series.candles[series.candles.length - 1].time;
    const ok = !!live && opts.live && (live.state === 'LIVE' || live.state === 'FROM_1M');
    const bars = ok ? live!.bars.filter((b) => b.time > lastClosed) : [];
    if (!bars.length) {
      if (liveDrawn.current) {      // the feed went away: take the provisional bars off the chart
        cs.setData(series.candles.map((k) => ({ time: k.time as UTCTimestamp, open: k.open, high: k.high, low: k.low, close: k.close })));
        liveDrawn.current = 0;
      }
      cs.applyOptions({ title: 'last close' });
      return;
    }
    try {
      for (const b of bars) {
        const up = b.close >= b.open; const col = b.forming ? (up ? 'rgba(38,166,154,.55)' : 'rgba(239,83,80,.55)') : (up ? COLORS.up : COLORS.down);
        cs.update({ time: b.time as UTCTimestamp, open: b.open, high: b.high, low: b.low, close: b.close, color: col, borderColor: up ? COLORS.up : COLORS.down, wickColor: up ? COLORS.up : COLORS.down });
      }
      liveDrawn.current = bars.length;
      cs.applyOptions({ title: live!.state === 'LIVE' ? 'live' : 'forming (1m)' });
    } catch { /* an out-of-order bar: the next closed-series reset redraws it */ }
  }, [live, series, symbol, tf, opts.live]);

  // SMART MONEY CONCEPTS — which analysis timeframes the switched-on studies need, loaded from the adapter
  // (closed bars only; a structure changes only when a bar closes, so a slow poll is enough)
  const smcTfs = Array.from(new Set(SMC_FEATURES.filter((f) => smc.on[f.id]).map((f) => smcTfFor(smc, f.id, tf)))).sort().join(',');
  smcTfsRef.current = smcTfs;
  useEffect(() => {
    let live = true; let timer: number | undefined;
    setSmcData({}); setSmcKeys(undefined); setSmcErr('');
    if (!smcTfs) return;
    const load = async () => {
      try {
        const got = await Promise.all(smcTfs.split(',').map((t) => api.smc(symbol, t)));
        const keys = smc.on.liq ? (await api.smcKeyLevels(symbol)).levels : undefined;
        if (!live) return;
        setSmcData(Object.fromEntries(got.map((d) => [d.tf, d]))); setSmcKeys(keys); setSmcErr('');
      } catch (e) { if (live) setSmcErr(e instanceof Error ? e.message.slice(0, 120) : String(e)); }
      if (live) timer = window.setTimeout(load, 30000);
    };
    void load();
    return () => { live = false; if (timer) window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, smcTfs, smc.on.liq]);
  useEffect(() => {
    const ok = series && series.symbol === symbol && series.tf === tf;
    const mine = Object.fromEntries(Object.entries(smcData).filter(([, d]) => d && d.symbol === symbol));
    const { shapes, counts } = ok ? buildShapes(smc, tf, mine, smcKeys) : { shapes: [], counts: { sr: 0, fvg: 0, bos: 0, choch: 0, ob: 0, liq: 0, idm: 0 } };
    smcCounts.current = counts; setSmcTick((n) => n + 1);
    smcPrim.current?.set(shapes, ok ? series!.candles.map((k) => k.time) : [], TF_SEC[tf] ?? 900);
  }, [smc, smcData, smcKeys, series, symbol, tf]);

  // the indicators menu closes on Esc (and when the pointer leaves it)
  useEffect(() => {
    if (!menu) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setMenu(false); } };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [menu]);

  // FORECASTING STUDIES — loaded only while switched on; closed bars only, so a slow poll is enough
  useEffect(() => {
    let alive = true; let timer: number | undefined;
    setFcDaily(null); setFcErr('');
    if (!fcDailyOn && !fcRankOn) { setFcRank(null); return; }
    const load = async () => {
      try {
        const [d, r] = await Promise.all([fcDailyOn ? api.forecastDaily(symbol) : null, fcRankOn ? api.forecastRanking(symbol) : null]);
        if (!alive) return;
        setFcDaily(d); setFcRank(r); setFcErr('');
      } catch (e) { if (alive) setFcErr(e instanceof Error ? e.message.slice(0, 140) : String(e)); }
      if (alive) timer = window.setTimeout(load, 30000);
    };
    void load();
    return () => { alive = false; if (timer) window.clearTimeout(timer); };
  }, [symbol, fcDailyOn, fcRankOn]);
  // the two forecast lines (today) and, with "history", the finished days' lines — drawn on the chart
  useEffect(() => {
    const cs = candles.current, c = chart.current; if (!cs || !c) return;
    fcLines.current.forEach((l) => cs.removePriceLine(l)); fcLines.current = [];
    fcHist.current.forEach((s) => c.removeSeries(s)); fcHist.current = [];
    fcDrawn.current = { lines: 0, history: 0 };
    // the price axis makes room for the two forecast lines while the study is on (and only then)
    const show = fcDailyOn && fcDaily && fcDaily.symbol === symbol && fcDaily.state === 'OK' && series && series.symbol === symbol && series.tf === tf;
    const hi = show && fc.side !== 'bottom' ? fcDaily!.top! : null, lo = show && fc.side !== 'top' ? fcDaily!.bottom! : null;
    cs.applyOptions({ autoscaleInfoProvider: (orig: () => { priceRange: { minValue: number; maxValue: number } | null; margins?: { above: number; below: number } } | null) => {
      const r = orig(); if (!r || !r.priceRange || (hi == null && lo == null)) return r;
      return { ...r, priceRange: { minValue: lo == null ? r.priceRange.minValue : Math.min(r.priceRange.minValue, lo), maxValue: hi == null ? r.priceRange.maxValue : Math.max(r.priceRange.maxValue, hi) } };
    } });
    const d = fcDaily; const ok = series && series.symbol === symbol && series.tf === tf && series.candles.length > 0;
    if (!fcDailyOn || !d || d.symbol !== symbol || d.state !== 'OK' || !ok) return;
    const dp = d.decimals; const used = d.used_pct != null ? `  (ADR ${d.used_pct.toFixed(0)}%)` : '';
    if (fc.side !== 'bottom') fcLines.current.push(cs.createPriceLine({ price: d.top!, color: '#f87171', lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `${d.top_done ? 'DAY TOP IN' : 'FORECAST TOP'} ${px(d.top, dp)}${used}` }));
    if (fc.side !== 'top') fcLines.current.push(cs.createPriceLine({ price: d.bottom!, color: '#4ade80', lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `${d.bottom_done ? 'DAY BOTTOM IN' : 'FORECAST BOTTOM'} ${px(d.bottom, dp)}${used}` }));
    for (const sc of d.scenarios) {
      for (const [k, v, col] of [['entry', sc.entry, '#94a3b8'], ['SL', sc.sl, '#fb7185'], ['TP1', sc.tp1, '#c4b5fd'], ['TP2', sc.tp2, '#c4b5fd']] as const)
        fcLines.current.push(cs.createPriceLine({ price: v, color: col, lineWidth: 1, lineStyle: LineStyle.SparseDotted, axisLabelVisible: false, title: `hypothetical ${sc.direction === 'SHORT' ? 'fade short' : 'fade long'} ${k}` }));
    }
    fcDrawn.current.lines = fcLines.current.length;
    if (fc.history && (TF_SEC[tf] ?? 900) < 86400) {
      const times = series!.candles.map((k) => k.time);
      for (const [key, col] of [['top', '#f87171'], ['bottom', '#4ade80']] as const) {
        if ((key === 'top' && fc.side === 'bottom') || (key === 'bottom' && fc.side === 'top')) continue;
        const pts: ({ time: UTCTimestamp; value: number } | { time: UTCTimestamp })[] = [];
        for (const h of d.history) {
          const inDay = times.filter((t) => t >= h.day_start && t < h.day_end);
          if (inDay.length < 2) continue;
          if (pts.length && (pts[pts.length - 1].time as number) >= inDay[0]) continue;
          pts.push({ time: inDay[0] as UTCTimestamp, value: h[key] }, { time: inDay[inDay.length - 1] as UTCTimestamp, value: h[key] });
          const next = times.find((t) => t >= h.day_end);
          if (next !== undefined) pts.push({ time: next as UTCTimestamp });          // a gap: days are not joined
        }
        const clean = pts.filter((p, i) => i === 0 || (p.time as number) > (pts[i - 1].time as number));
        if (clean.length < 2) continue;
        const s = c.addSeries(LineSeries, { color: col, lineWidth: 1, lineStyle: LineStyle.Dotted, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false });
        s.setData(clean); fcHist.current.push(s); fcDrawn.current.history += 1;
      }
    }
  }, [fcDaily, fcDailyOn, fc.side, fc.history, series, symbol, tf]);

  // indicators (display-only studies from indicators.ts)
  useEffect(() => {
    const c = chart.current; if (!c) return;
    for (const [id, s] of Array.from(studies.current)) if (!indicators.includes(id)) { c.removeSeries(s); studies.current.delete(id); }
    const ok = series && series.symbol === symbol && series.tf === tf;
    for (const def of INDICATORS.filter((d) => indicators.includes(d.id))) {
      let s = studies.current.get(def.id);
      if (!s) { s = c.addSeries(LineSeries, { color: def.color, lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }); studies.current.set(def.id, s); }
      s.setData(ok ? def.compute(series!.candles).map((p) => ({ time: p.time as UTCTimestamp, value: p.value })) : []);
    }
  }, [indicators, series, symbol, tf]);

  // levels + markers
  useEffect(() => {
    const cs = candles.current;
    if (!cs) return;
    lines.current.forEach((l) => cs.removePriceLine(l));
    lines.current = [];
    if (decision && decision.symbol === symbol) {
      const dec = decision.decimals;
      const ref = decision.price.last_closed_1m?.price ?? decision.last_close;
      const dist = (v: number) => (ref != null && decision.atr ? ` ${((v - ref) / decision.atr).toFixed(1)}ATR` : '');
      for (const l of decision.levels) {
        lines.current.push(cs.createPriceLine({ price: l.value, color: COLORS[l.kind], lineWidth: 2,
          lineStyle: l.kind === 'tp' ? LineStyle.Dashed : LineStyle.Solid, axisLabelVisible: true, title: `${l.label} ${px(l.value, dec)}${dist(l.value)}` }));
      }
      if (opts.expired && decision.expired_plan) {
        for (const l of decision.expired_plan.levels) {
          lines.current.push(cs.createPriceLine({ price: l.value, color: COLORS.stale, lineWidth: 1, lineStyle: LineStyle.SparseDotted, axisLabelVisible: true, title: `${l.label} (history)` }));
        }
      }
      if (opts.ladder) {
        for (const lv of decision.levels_ladder.slice(0, 16)) {
          if (typeof lv.value !== 'number') continue;
          const above = ref != null && lv.value > ref;
          lines.current.push(cs.createPriceLine({ price: lv.value, color: above ? '#7f3b48' : '#2f6b5c', lineWidth: 1, lineStyle: LineStyle.Dotted,
            axisLabelVisible: true, axisLabelColor: above ? '#4a2430' : '#1d4038', axisLabelTextColor: '#cbd5e1', title: `${String(lv.name ?? '')}${lv.tf ? ' ' + lv.tf : ''}` }));
        }
      }
    }
    const first = series?.candles[0]?.time ?? 0;
    const ids = new Map<number, string[]>();
    const ms: SeriesMarker<Time>[] = opts.markers ? signals
      .filter((s) => s.symbol === symbol && s.created_at && (s.direction === 'BUY' || s.direction === 'SELL'))
      .filter((s) => opts.history || s.bucket === 'ACTIVE' || s.bucket === 'PENDING')
      .map((s) => ({ s, t: snap(Math.floor(new Date(s.created_at!).getTime() / 1000), tf) }))
      .filter(({ t }) => t >= first)
      .map(({ s, t }): SeriesMarker<Time> => {
        ids.set(t, [...(ids.get(t) ?? []), s.signal_id]);
        return { time: t as UTCTimestamp, position: s.direction === 'BUY' ? 'belowBar' : 'aboveBar',
          color: s.bucket === 'REJECTED' ? '#64748b' : s.bucket === 'EXPIRED' ? (s.direction === 'BUY' ? '#3f8f7a' : '#8f3f4a') : s.direction === 'BUY' ? '#26a69a' : '#ef5350',
          shape: s.direction === 'BUY' ? 'arrowUp' : 'arrowDown', size: s.bucket === 'ACTIVE' ? 2 : 1,
          // a marker is a SIGNAL (a recommendation), and says so; it is never drawn as a fill
          text: `${s.system || 'signal'} ${s.direction} ${opts.history ? s.status : s.bucket}${s.grade ? ' ' + s.grade : ''}` };
      })
      .sort((a, b) => (a.time as number) - (b.time as number)) : [];
    markerIds.current = ids;
    markers.current?.setMarkers(ms);
  }, [decision, signals, series, symbol, tf, opts.expired, opts.ladder, opts.markers, opts.history]);

  const zoom = (f: number) => {
    const c = chart.current; const r = c?.timeScale().getVisibleLogicalRange();
    if (!c || !r) return;
    const mid = (r.from + r.to) / 2, half = ((r.to - r.from) / 2) * f;
    c.timeScale().setVisibleLogicalRange({ from: mid - half, to: mid + half });
  };
  const pan = (dir: number) => {
    const c = chart.current; const r = c?.timeScale().getVisibleLogicalRange();
    if (!c || !r) return;
    const step = (r.to - r.from) * 0.4 * dir;
    c.timeScale().setVisibleLogicalRange({ from: r.from + step, to: r.to + step });
  };
  const latest = () => focusLatest(dataRef.current?.count ?? 0);
  // FIT: every stored bar that was loaded, edge to edge, price axis back on auto
  const fit = () => { const c = chart.current; if (!c) return; c.priceScale('right').applyOptions({ autoScale: true }); setAuto(true); c.timeScale().applyOptions({ rightOffset: 2 }); c.timeScale().fitContent(); };
  const toggleAuto = () => { const c = chart.current; if (!c) return; const next = !c.priceScale('right').options().autoScale; c.priceScale('right').applyOptions({ autoScale: next }); setAuto(next); };

  const f = series?.freshness;
  const lb = series?.last_bar;
  const dec = series?.decimals ?? decision?.decimals ?? 2;
  const h = hover;
  const span = TF_SEC[tf] ?? 900;
  const active = INDICATORS.filter((d) => indicators.includes(d.id));
  const fcActive = FORECAST_STUDIES.filter((d) => indicators.includes(d.id));
  const toggleInd = (id: string, on: boolean) => onIndicators(on ? [...indicators.filter((x) => x !== id), id] : indicators.filter((x) => x !== id));
  return (
    <div className={'chart' + (full ? ' is-full' : '')} data-testid="chart">
      <div className="chart-head">
        <b className="chart-title">{symbol} · {tfLabel(tf)}</b><span className="dim hide-s">{opts.live && live && (live.state === 'LIVE' || live.state === 'FROM_1M') ? 'closed bars + forming bar · UTC' : 'closed bars · UTC'}</span>
        {f && <span className={`pill ${toneOf(f.state)}`} title={`${f.detail || ''} · engine gate ${fmtAge(f.age_min)} since open / limit ${fmtAge(f.limit_min)}`}>{f.state}</span>}
        {series && <span className={`pill ${sourceTone(series.source_kind)}`} title={series.source_warning || `per-candle source: ${lb?.source}`}>{sourceWord(series.source_kind)}</span>}
        {lb && <span className="dim" title="price-contract-v1: chart_last_bar">last bar <b className="mono" style={{ color: '#e2e8f0' }}>{px(lb.price, dec)}</b> · {fmtHM(lb.bar_open_ts)}–{fmtHM(lb.bar_close_ts)} · closed {fmtAge(Math.max(lb.since_close_min ?? 0, 0))} ago</span>}
        {opts.live && live && <span className={`pill ${live.state === 'LIVE' ? 'good' : live.state === 'FROM_1M' ? 'warn' : 'muted'}`} data-testid="live-state" title={`${live.rule}${live.error ? ' · ' + live.error : ''}`}>
          {live.state === 'LIVE' ? '● LIVE BAR · bridge' : live.state === 'FROM_1M' ? 'FORMING BAR · from 1m' : `NO LIVE BAR · ${live.bridge_state ?? live.state}`}</span>}
        <span style={{ flex: 1 }} />
        <button className={full ? 'on' : ''} onClick={onFull} data-testid="chart-full" title="full-screen chart (F) — hides every panel; Esc restores them">{full ? '⤡ exit full screen' : '⤢ full screen'}</button>
      </div>
      <div className="chart-tools" role="toolbar" aria-label="Chart tools">
        {full && <span className="tool-group"><b className="chart-title">{symbol} · {tfLabel(tf)}</b><button className="on" onClick={onFull} data-testid="chart-full-exit" title="leave full screen (Esc)">⤡ exit full screen</button></span>}
        <span className="tool-group" title="time scale">
          <button onClick={() => pan(-1)} title="scroll back in time">◀</button><button onClick={() => pan(1)} title="scroll forward in time">▶</button>
          <button onClick={() => zoom(0.7)} title="zoom in (mouse wheel)">＋</button><button onClick={() => zoom(1.4)} title="zoom out (mouse wheel)">－</button>
          <button onClick={fit} data-testid="chart-fit" title="fit every loaded bar into the chart">fit all</button><button onClick={latest} title="jump to the newest bar">latest ⇥</button>
        </span>
        <span className="tool-group" title="price scale">
          <button className={auto ? 'on' : ''} onClick={toggleAuto} data-testid="chart-auto" title="auto-scale the price axis to the visible bars (drag the price axis to scale by hand; double-click it to reset)">auto</button>
          <button className={opts.log ? 'on' : ''} onClick={() => onOpts({ log: !opts.log })} title="logarithmic price scale">log</button>
          <button className={opts.magnet ? 'on' : ''} onClick={() => onOpts({ magnet: !opts.magnet })} title="crosshair snaps to the bar's close">magnet</button>
        </span>
        <span className="tool-group" title="how many closed bars are requested from SignalMesh">
          <select value={bars} onChange={(e) => onBars(Number(e.target.value))} aria-label="Bars loaded">{[300, 500, 1000].map((n) => <option key={n} value={n}>{n} bars</option>)}</select>
        </span>
        <span className="tool-group">
          <label><input type="checkbox" checked={opts.markers} onChange={(e) => onOpts({ markers: e.target.checked })} /> signals</label>
          <label title="also mark expired, rejected, cancelled and closed signals (can be dense)"><input type="checkbox" checked={opts.history} onChange={(e) => onOpts({ history: e.target.checked })} /> history</label>
          <label title="SignalMesh's structural level ladder"><input type="checkbox" checked={opts.ladder} onChange={(e) => onOpts({ ladder: e.target.checked })} /> ladder</label>
          <label title="expired plans are history; off by default"><input type="checkbox" checked={opts.expired} onChange={(e) => onOpts({ expired: e.target.checked })} /> expired plan</label>
          <label title="draw the bar that is still forming (display only — the engine decides on closed bars)"><input type="checkbox" checked={opts.live} onChange={(e) => onOpts({ live: e.target.checked })} /> live bar</label>
          <label title="MT5 tick volume per bar (not traded size)"><input type="checkbox" checked={opts.volume} onChange={(e) => onOpts({ volume: e.target.checked })} /> volume</label>
        </span>
        <span className="tool-group menu-host">
          <button className={active.length + fcActive.length ? 'on' : ''} onClick={() => setMenu((v) => !v)} data-testid="chart-indicators" title="indicators and forecasting studies — all display only, all off by default">ƒ indicators{active.length + fcActive.length ? ` (${active.length + fcActive.length})` : ''}</button>
          {menu && <div className="menu ind-menu" onMouseLeave={() => setMenu(false)} data-testid="indicator-menu">
            <div className="menu-title">Indicators</div>
            {INDICATORS.map((d) => <label key={d.id}><input type="checkbox" checked={indicators.includes(d.id)} onChange={(e) => toggleInd(d.id, e.target.checked)} /> <span style={{ color: d.color }}>━</span> {d.name}</label>)}
            <div className="dim" style={{ fontSize: 10, maxWidth: 300, marginTop: 2 }}>{INDICATOR_NOTE}</div>
            <div className="menu-title" style={{ marginTop: 8 }}>Forecasting studies</div>
            {FORECAST_STUDIES.map((d) => <label key={d.id} title={d.what}><input type="checkbox" data-testid={`ind-${d.id}`} checked={indicators.includes(d.id)} onChange={(e) => toggleInd(d.id, e.target.checked)} /> <span style={{ color: d.color }}>━</span> {d.name}</label>)}
            <div className="fc-opts">
              <select value={fc.side} onChange={(e) => onFc({ ...fc, side: e.target.value as FcSettings['side'] })} aria-label="Forecast lines shown" data-testid="fc-side" title="which daily forecast line is drawn">
                <option value="both">top + bottom</option><option value="top">top only (bearish side)</option><option value="bottom">bottom only (bullish side)</option></select>
              <label title="also draw the finished days' forecast lines (dotted)"><input type="checkbox" checked={fc.history} onChange={(e) => onFc({ ...fc, history: e.target.checked })} data-testid="fc-history" /> history</label>
              <button onClick={() => { setFcMethod(true); setMenu(false); }} data-testid="fc-method-menu" title="how it is calculated, from which closed bars, and when">ⓘ method</button>
            </div>
            <div className="dim" style={{ fontSize: 10, maxWidth: 300, marginTop: 4 }}>{FORECAST_NOTE}</div>
          </div>}
        </span>
      </div>
      <SmcBar s={smc} onChange={onSmc} chartTf={tf} data={smcData} counts={smcCounts.current} error={smcErr} />
      {!compact && !full && <div className="chart-sub">
        <span className="ohlc mono" data-testid="ohlc">
          {h ? <>{utc(h.time)} → {fmtHM(new Date((h.time + span) * 1000).toISOString())} · O <b>{px(h.open, dec)}</b> H <b>{px(h.high, dec)}</b> L <b>{px(h.low, dec)}</b> C <b className={h.close >= h.open ? 'good' : 'bad'}>{px(h.close, dec)}</b> · vol {Math.round(h.volume)}</>
            : lb ? <>newest bar {fmtTs(lb.bar_open_ts)} → {fmtHM(lb.bar_close_ts)} · move the crosshair over a bar for its time and O/H/L/C</> : '—'}
        </span>
        <span className="legend">
          <span style={{ color: COLORS.entry }}>Entry</span><span style={{ color: COLORS.sl }}>SL</span><span className="dashed" style={{ color: COLORS.tp }}>TP1 / TP2</span>
          <span className="dashed" style={{ color: '#475569' }}>ladder</span><span className="arrow">▲▼ signal (click for origin)</span>
          {active.map((d) => <span key={d.id} style={{ color: d.color }}>{d.short}</span>)}
          {fcActive.map((d) => <span key={d.id} className="dashed" style={{ color: d.color }}>{d.short}</span>)}
          <span className="dim hide-s" style={{ marginLeft: 6 }}>{series ? `${series.count} bars loaded · source ${series.last_bar?.source || 'unstated'}` : ''}</span>
        </span>
      </div>}
      <div className="chart-body">
        <div ref={host} />
        {decision && decision.symbol === symbol && !compact && !full && (
          <div className="chart-badge">
            <div className={`struct ${toneOf(decision.structure)}`}>{decision.structure ?? 'STRUCTURE UNKNOWN'}{decision.bias ? <span className={`bias ${toneOf(decision.bias)}`}> · {decision.bias.toUpperCase()}</span> : null}{decision.regime ? <span className="dim"> · {decision.regime}</span> : null}</div>
            <div className="dim">engine 15m structure (scanner swing=3) · ATR {px(decision.atr, decision.decimals)}</div>
            {(() => { const sg = decision.signal ?? decision.expired_plan?.signal; const w = sg?.pine ?? {}; const keys = ['trend', 'choch', 'inducement', 'sweep', 'trap_bias', 'loc_zone', 'killzone', 'htf_align', 'level_src', 'ny_regime', 'method'].filter((k) => w[k] !== undefined);
              return sg && (keys.length || sg.market_structure) ? (
                <div className="pine">
                  <span className="dim">{sg.system} said{sg.age_h != null ? ` ${sg.age_h}h ago` : ''}{sg.stale ? ' (expired)' : ''}: </span>
                  {sg.market_structure && <span>structure <b>{sg.market_structure}</b> </span>}
                  {keys.map((k) => <span key={k}>{k} <b className={toneOf(String(w[k]))}>{String(w[k])}</b> </span>)}
                </div>) : null; })()}
          </div>)}
        <StudyReport symbol={symbol} daily={fcDaily} ranking={fcRank} showDaily={fcDailyOn} showRanking={fcRankOn} err={fcErr} s={fc} onChange={onFc} onSymbol={onSymbol} />
        {fcMethod && <ForecastMethod daily={fcDaily} ranking={fcRank} onClose={() => setFcMethod(false)} />}
        {seriesErr && <div className="overlay bad">{symbol} {tfLabel(tf)} candles could not be loaded: {seriesErr}</div>}
        {!seriesErr && series && series.symbol === symbol && series.count === 0 && (
          <div className="overlay"><div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--warn)' }}>No {tfLabel(tf)} candles stored for {symbol}</div>
            <div style={{ marginTop: 6 }}>SignalMesh keeps only the timeframes its MT5 reporter pushes. Nothing is interpolated or invented here.</div>
            {coverage?.symbol === symbol && <div style={{ marginTop: 6 }}>Stored for {symbol}: <b>{coverage.timeframes.filter((r) => r.stored).map((r) => tfLabel(r.tf)).join(', ') || 'none'}</b></div>}
            <div className="dim" style={{ marginTop: 6, fontSize: 11 }}>To get this timeframe, add it to BB_CANDLE_TFS in the mt5_reporter settings on the MT5 box (e.g. 1m,5m,15m,30m,1h,4h,1d) and restart the reporter; it backfills history.</div>
          </div></div>)}
        {!seriesErr && (!series || series.symbol !== symbol || series.tf !== tf) && <div className="overlay">loading {symbol} {tfLabel(tf)} candles…</div>}
      </div>
      {!full && !compact && <div className="chart-foot">
        {decision ? (
          <>
            <span><b className="dim">CONFIRMATION:</b> {decision.lane.confirmation_text} <b className={toneOf(decision.lane.confirmation_status)}>→ {decision.lane.stage}</b></span>
            <span className="dim" title="price-contract-v1: engine_reference — the 15m closed bar the decision, ATR and structure were measured on">engine ref <b className="mono" style={{ color: '#cbd5e1' }}>{px(decision.price.engine_reference?.price, decision.decimals)}</b> (15m bar {fmtHM(decision.price.engine_reference?.bar_open_ts)}–{fmtHM(decision.price.engine_reference?.bar_close_ts)}) · ATR {px(decision.atr, decision.decimals)} · structure {decision.structure ?? 'UNKNOWN'} · bias {decision.bias ?? 'UNKNOWN'}</span>
            {decision.price.drift?.state && <span className={decision.price.drift.state === 'MOVED' ? 'warn' : 'dim'} title={decision.price.drift.reason}>drift {decision.price.drift.state}{decision.price.drift.drift_atr != null ? ` ${decision.price.drift.drift_atr} ATR vs latest ${decision.price.drift.latest_bar_tf} bar` : ''}</span>}
            {decision.levels.length > 0 ? <span className="dim" title={decision.levels_rule}>levels: {decision.levels[0].origin}</span> : <span className="dim">no current levels{decision.expired_plan ? ` · last plan ${decision.expired_plan.signal.signal_id} expired → Trade History` : ''}</span>}
            {decision.levels_ladder.length > 0 && <span className="ladder-list" title="SignalMesh's structural level ladder (brief.level_ladder): named closed-bar highs and lows per timeframe — context, never a plan">
              ladder: {decision.levels_ladder.slice(0, 12).map((l, i) => <span key={i} className={typeof l.value === 'number' && decision.last_close != null && l.value > decision.last_close ? 'bad' : 'good'}>{l.name} {px(l.value, decision.decimals)}</span>)}
            </span>}
          </>
        ) : <span className="dim">decision pending…</span>}
      </div>}
    </div>
  );
}
