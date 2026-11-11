// PATTERN STUDIES — Fibonacci extension, anchored VWAP, Wolfe wave, Elliott wave, volume profile.
// The terminal's own DISPLAY-ONLY studies in the chart's "indicators" menu. The adapter calculates
// them from SignalMesh's stored CLOSED candles of the chart's timeframe (studies.py,
// pattern-studies-v1); this file only decides what to draw and paints it. They are not SignalMesh
// engine output and feed nothing. Confirmed Wolfe and valid Elliott setups are recorded server-side in
// the terminal's own Forecast Journal; the other three are kept nowhere. Every entry / stop / target is a
// HYPOTHETICAL ANALYSIS LEVEL. All are OFF by default and remembered in the workspace.
import type { IPrimitivePaneRenderer, IPrimitivePaneView, ISeriesPrimitive, Logical, SeriesAttachedParameter, Time } from 'lightweight-charts';

export type PatternId = 'st-fib' | 'st-avwap' | 'st-wolfe' | 'st-elliott' | 'st-vp';
export interface PatternStudy { id: PatternId; name: string; short: string; color: string; what: string }
export const PATTERN_STUDIES: PatternStudy[] = [
  { id: 'st-fib', name: 'Fibonacci extension — targets from the last swing', short: 'Fib ext', color: '#fbbf24', what: 'levels C + ratio × (B − A) from the last three confirmed swing pivots, with which are reached' },
  { id: 'st-avwap', name: 'Anchored VWAP — from swing high, swing low, day start', short: 'AVWAP', color: '#38bdf8', what: 'tick-volume-weighted average price since each anchor, with a one-deviation band in the table' },
  { id: 'st-wolfe', name: 'Wolfe wave — 5-point wedge, EPA target', short: 'Wolfe', color: '#c084fc', what: 'five alternating pivots in a converging wedge: points 1-5, lines 1-3 / 2-4 / 1-4, entry, SL, TP1, TP2; a four-point wedge reads DEVELOPING' },
  { id: 'st-elliott', name: 'Elliott wave — impulse count and alternative', short: 'Elliott', color: '#34d399', what: 'impulse count 1-5 on confirmed pivots with invalidation and targets, an alternative count, A-B-C after a finished five' },
  { id: 'st-vp', name: 'Volume profile — tick-volume activity by price', short: 'Vol profile', color: '#fb923c', what: 'tick volume by price over the loaded bars: POC, value area high / low, high and low activity nodes' },
];
export const PATTERN_IDS = PATTERN_STUDIES.map((s) => s.id) as string[];
export const PATTERN_NOTE = 'terminal studies · display only · from stored CLOSED candles of the chart timeframe · not SignalMesh engine output · confirmed Wolfe and valid Elliott setups are recorded in the Forecast Journal; the other three are context only · levels are HYPOTHETICAL ANALYSIS LEVELS · volume = MT5 tick volume';

// ---- adapter payload (pattern-studies-v1)
export interface Pt { name: string; kind: 'H' | 'L'; price: number; time: number }
export interface FibData { state: string; note?: string; direction?: 'UP' | 'DOWN'; a?: Pt; b?: Pt; c?: Pt; leg?: number; retrace_pct?: number | null; made_bar?: number; confirmed_at?: number;
  levels?: { ratio: number; price: number; reached: boolean }[]; status?: string; invalidation?: number; invalidated_bar?: number | null; next_level?: { ratio: number; price: number } | null; rule?: string }
export interface AvwapAnchor { id: string; name: string; anchor_time: number; anchor_price: number; bars: number; value: number; sd: number | null; upper: number; lower: number; side: string; distance: number; distance_atr: number | null; points: { t: number; v: number }[] }
export interface AvwapData { state: string; note?: string; anchors: AvwapAnchor[]; last?: number; reading?: string; volume_kind?: string }
export interface WolfePattern { direction: string; side: string; points: Pt[]; entry: number; sl: number; tp1: number; tp2: number; epa: number; invalidation: number; rr1: number | null; rr2: number | null;
  apex_time: number; expires_time: number; zone_5: number[]; made_bar: number; confirmed_at: number; status: string; status_bar: number; done: boolean; level_label: string }
export interface WolfeDeveloping { direction: string; status: string; points: Pt[]; line_13_now: number; point_5_limit: number; waiting_for: string }
export interface WolfeData { state: string; note?: string; pattern: WolfePattern | null; developing: WolfeDeveloping | null; last_finished: WolfePattern | null; log: WolfePattern[] }
export interface ElliottCount { direction: string; dir: number; wave: number; text: string; invalidation: number; break_level: number; target_1: number; target_2: number; target_1_name: string; target_2_name: string;
  ratios: Record<string, number>; rules_met: string; points: Pt[]; level_label: string; made_bar?: number; confirmation?: string }
export interface ElliottData { state: string; note?: string; count: ElliottCount | null; alternative: ElliottCount | null; abc: Pt[]; log: { event: string; bar: number; text: string }[] }
export interface VpData { state: string; note?: string; rows: { low: number; high: number; volume: number; pct_of_max: number; in_value_area: boolean; poc: boolean }[]; poc?: number; vah?: number; val?: number;
  value_area_pct?: number; total_tick_volume?: number; hvn?: number[]; lvn?: number[]; from_time?: number; to_time?: number; bars?: number; last?: number; position?: string; reading?: string; volume_kind?: string }
export interface PatternData {
  symbol: string; tf: string; state: string; note: string; kind: string; method_version: string; methodology: Record<string, string>; level_label: string; recorded: Record<string, boolean>; recorded_note: string; journal?: { module: string; timeframe: string; origin: string; recorded: number; open: number; finished: number; tp1: number; tp2: number; tp1_rate_pct: number | null; tp2_rate_pct: number | null; r_avg: number | null; r_n: number; sample: string }[]; journal_timeframes?: string[];
  source: string; bars_used: number; calculated_at: string; through_close_utc: string | null; atr: number | null; last_close?: number; decimals: number;
  fib: FibData | null; avwap: AvwapData | null; wolfe: WolfeData | null; elliott: ElliottData | null; vp: VpData | null;
}

// ---- what gets painted
export type PShape =
  | { k: 'seg'; study: PatternId; t0: number; p0: number; t1: number | null; p1: number; color: string; width?: number; dash?: number[]; label?: string; faded?: boolean }   // t1 null = to the right edge
  | { k: 'path'; study: PatternId; pts: { t: number; p: number }[]; color: string; width?: number; dash?: number[]; label?: string; faded?: boolean }
  | { k: 'mark'; study: PatternId; t: number; p: number; text: string; color: string; above: boolean; faded?: boolean }
  | { k: 'hbar'; study: PatternId; lo: number; hi: number; frac: number; color: string; alpha: number };
const C = { fib: '251,191,36', grey: '148,163,184', red: '248,113,113', green: '74,222,128', blue: '56,189,248', purple: '192,132,252', em: '52,211,153', orange: '251,146,60', white: '226,232,240' };
const AV_COL: Record<string, string> = { 'swing-high': C.red, 'swing-low': C.green, day: C.blue };
const f = (v: number, d: number) => v.toFixed(d);
export type PatternCounts = Record<PatternId, number>;
export const NO_COUNTS: PatternCounts = { 'st-fib': 0, 'st-avwap': 0, 'st-wolfe': 0, 'st-elliott': 0, 'st-vp': 0 };

export function buildPatternShapes(on: (id: PatternId) => boolean, d: PatternData | null): { shapes: PShape[]; counts: PatternCounts } {
  const shapes: PShape[] = []; const counts = { ...NO_COUNTS };
  const add = (s: PShape) => { shapes.push(s); counts[s.study]++; };
  if (!d || d.state !== 'OK') return { shapes, counts };
  const dp = d.decimals;
  const poly = (study: PatternId, pts: Pt[], color: string, o: { dash?: number[]; faded?: boolean; width?: number; wrap?: (n: string) => string } = {}) => {
    add({ k: 'path', study, pts: pts.map((p) => ({ t: p.time, p: p.price })), color, width: o.width ?? 1.6, dash: o.dash, faded: o.faded });
    for (const p of pts) add({ k: 'mark', study, t: p.time, p: p.price, text: o.wrap ? o.wrap(p.name) : p.name, color, above: p.kind === 'H', faded: o.faded });
  };

  const vp = d.vp;
  if (on('st-vp') && vp && vp.state === 'OK') {
    for (const r of vp.rows) if (r.volume > 0) add({ k: 'hbar', study: 'st-vp', lo: r.low, hi: r.high, frac: r.pct_of_max / 100, color: r.poc ? C.orange : r.in_value_area ? C.blue : C.grey, alpha: r.poc ? 0.55 : r.in_value_area ? 0.26 : 0.14 });
    add({ k: 'seg', study: 'st-vp', t0: vp.from_time!, p0: vp.poc!, t1: null, p1: vp.poc!, color: C.orange, width: 1.4, label: `POC ${f(vp.poc!, dp)} · tick-volume` });
    add({ k: 'seg', study: 'st-vp', t0: vp.from_time!, p0: vp.vah!, t1: null, p1: vp.vah!, color: C.blue, dash: [5, 4], label: `VAH ${f(vp.vah!, dp)}` });
    add({ k: 'seg', study: 'st-vp', t0: vp.from_time!, p0: vp.val!, t1: null, p1: vp.val!, color: C.blue, dash: [5, 4], label: `VAL ${f(vp.val!, dp)}` });
  }
  const av = d.avwap;
  if (on('st-avwap') && av && av.state === 'OK') {
    for (const a of av.anchors) {
      const col = AV_COL[a.id] ?? C.blue;
      add({ k: 'path', study: 'st-avwap', pts: a.points.map((p) => ({ t: p.t, p: p.v })), color: col, width: 1.8, label: `AVWAP ${a.id === 'day' ? 'day' : a.id === 'swing-high' ? 'from high' : 'from low'} ${f(a.value, dp)}` });
      add({ k: 'mark', study: 'st-avwap', t: a.anchor_time, p: a.anchor_price, text: '⚓', color: col, above: a.id === 'swing-high' });
    }
  }
  const fb = d.fib;
  if (on('st-fib') && fb && fb.state === 'OK' && fb.a && fb.b && fb.c) {
    const dead = fb.status === 'INVALIDATED';
    poly('st-fib', [fb.a, fb.b, fb.c], C.grey, { dash: [4, 3], faded: dead, width: 1.2 });
    for (const lv of fb.levels ?? []) add({ k: 'seg', study: 'st-fib', t0: fb.c.time, p0: lv.price, t1: null, p1: lv.price, color: C.fib, width: lv.ratio === 1 || lv.ratio === 1.618 ? 1.5 : 1, dash: lv.reached ? [2, 4] : undefined, faded: lv.reached || dead,
      label: `FIB ${lv.ratio} · ${f(lv.price, dp)}${lv.reached ? ' ✓ reached' : ''}` });
    add({ k: 'seg', study: 'st-fib', t0: fb.c.time, p0: fb.invalidation!, t1: null, p1: fb.invalidation!, color: C.red, dash: [2, 3], faded: dead, label: `fib ${dead ? 'INVALIDATED' : 'invalid on a close beyond'} C ${f(fb.invalidation!, dp)}` });
  }
  const w = d.wolfe;
  if (on('st-wolfe') && w) {
    const p = w.pattern ?? (w.developing ? null : w.last_finished);
    if (p) {
      const faded = p.done; const q = p.points; const bull = p.direction === 'BULLISH'; const col = bull ? C.green : C.red;
      const at = (a: Pt, b: Pt, t: number) => a.price + (b.price - a.price) * (t - a.time) / (b.time - a.time);
      poly('st-wolfe', q, C.purple, { faded, width: 1.8 });
      add({ k: 'seg', study: 'st-wolfe', t0: q[0].time, p0: q[0].price, t1: p.apex_time, p1: at(q[0], q[2], p.apex_time), color: C.purple, dash: [5, 3], faded, label: 'line 1-3' });
      add({ k: 'seg', study: 'st-wolfe', t0: q[1].time, p0: q[1].price, t1: p.apex_time, p1: at(q[1], q[3], p.apex_time), color: C.purple, dash: [5, 3], faded, label: 'line 2-4' });
      add({ k: 'seg', study: 'st-wolfe', t0: q[0].time, p0: q[0].price, t1: p.apex_time, p1: p.epa, color: col, dash: [2, 3], faded, label: `target line 1-4 → EPA ${f(p.epa, dp)}` });
      for (const [name, v, c2] of [['entry', p.entry, C.white], ['SL', p.sl, C.red], ['TP1', p.tp1, col], ['TP2', p.tp2, col]] as const)
        add({ k: 'seg', study: 'st-wolfe', t0: p.made_bar, p0: v, t1: p.expires_time, p1: v, color: c2, dash: [3, 3], faded, label: `Wolfe ${name} ${f(v, dp)} · hypothetical${name === 'entry' ? ` · ${p.status}` : ''}` });
    } else if (w.developing) {
      const q = w.developing.points;
      poly('st-wolfe', q, C.purple, { dash: [3, 4], faded: true, width: 1.4, wrap: (n) => `${n}?` });
      add({ k: 'seg', study: 'st-wolfe', t0: q[3].time, p0: w.developing.point_5_limit, t1: null, p1: w.developing.point_5_limit, color: C.purple, dash: [2, 4], faded: true,
        label: `Wolfe DEVELOPING (4 of 5, not confirmed) · point 5 ${w.developing.direction === 'BULLISH' ? 'at or below' : 'at or above'} ${f(w.developing.point_5_limit, dp)}` });
    }
  }
  const e = d.elliott;
  if (on('st-elliott') && e && e.state === 'OK' && e.count) {
    const c = e.count; const lastT = c.points[c.points.length - 1].time;
    if (e.alternative) poly('st-elliott', e.alternative.points, C.grey, { dash: [3, 4], faded: true, width: 1.2, wrap: (n) => `alt ${n}` });
    poly('st-elliott', c.points, C.em, { width: 1.8, wrap: (n) => (n === '0' ? '0' : `(${n})`) });
    if (e.abc.length) poly('st-elliott', [c.points[c.points.length - 1], ...e.abc].map((p, i) => (i === 0 ? { ...p, name: '' } : p)), C.orange, { dash: [4, 3], width: 1.4 });
    add({ k: 'seg', study: 'st-elliott', t0: lastT, p0: c.invalidation, t1: null, p1: c.invalidation, color: C.red, dash: [2, 3], label: `Elliott ${c.wave === 6 ? 'wave-5 end' : 'invalid beyond'} ${f(c.invalidation, dp)}` });
    add({ k: 'seg', study: 'st-elliott', t0: lastT, p0: c.target_1, t1: null, p1: c.target_1, color: C.em, dash: [5, 3], label: `Elliott ${c.target_1_name} ${f(c.target_1, dp)}` });
    add({ k: 'seg', study: 'st-elliott', t0: lastT, p0: c.target_2, t1: null, p1: c.target_2, color: C.em, dash: [5, 3], label: `Elliott ${c.target_2_name} ${f(c.target_2, dp)}` });
  }
  return { shapes, counts };
}

/** Paints the pattern studies over the candles. Coordinates are resolved at draw time, so zoom and scroll follow. */
export class PatternPrimitive implements ISeriesPrimitive<Time> {
  private p: SeriesAttachedParameter<Time> | null = null;
  private shapes: PShape[] = [];
  private times: number[] = [];
  private step = 900;
  private views: IPrimitivePaneView[] = [
    { zOrder: () => 'bottom', renderer: (): IPrimitivePaneRenderer => ({ draw: (t) => this.draw(t, true) }) },
    { zOrder: () => 'top', renderer: (): IPrimitivePaneRenderer => ({ draw: (t) => this.draw(t, false) }) },
  ];
  attached(p: SeriesAttachedParameter<Time>) { this.p = p; }
  detached() { this.p = null; }
  paneViews() { return this.views; }
  updateAllViews() { /* coordinates are computed in draw() */ }
  set(shapes: PShape[], times: number[], stepSec: number) { this.shapes = shapes; this.times = times; this.step = stepSec; this.p?.requestUpdate(); }

  private x(t: number): number | null {
    const ts = this.times; const p = this.p; if (!p || !ts.length) return null;
    let idx: number;
    if (t <= ts[0]) idx = (t - ts[0]) / this.step;
    else if (t >= ts[ts.length - 1]) idx = ts.length - 1 + (t - ts[ts.length - 1]) / this.step;
    else { let lo = 0, hi = ts.length - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (ts[m] < t) lo = m + 1; else hi = m; } idx = lo; }
    return p.chart.timeScale().logicalToCoordinate(idx as Logical);
  }

  private draw(target: Parameters<IPrimitivePaneRenderer['draw']>[0], back: boolean) {
    const p = this.p; if (!p || !this.shapes.length) return;
    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const W = mediaSize.width, H = mediaSize.height;
      const y = (v: number) => p.series.priceToCoordinate(v);
      const placed: [number, number, number, number][] = [];
      const text = (label: string, x: number, yy: number, color: string, faded?: boolean, force?: boolean) => {
        ctx.font = '10px ui-monospace, Menlo, monospace';
        const w = ctx.measureText(label).width + 8; const bx = Math.max(2, Math.min(W - w - 2, x)); const by = Math.max(2, Math.min(H - 14, yy - 7));
        if (!force && placed.some(([a, b, c, d]) => bx < a + c && bx + w > a && by < b + d && by + 13 > b)) return;
        placed.push([bx, by, w, 13]);
        ctx.fillStyle = 'rgba(11,18,32,.85)'; ctx.fillRect(bx, by, w, 13);
        ctx.fillStyle = `rgba(${color},${faded ? 0.6 : 1})`; ctx.textBaseline = 'middle'; ctx.fillText(label, bx + 4, by + 7);
      };
      ctx.save();
      for (const s of this.shapes) {
        if ((s.k === 'hbar') !== back) continue;
        if (s.k === 'hbar') {
          const ya = y(s.hi), yb = y(s.lo); if (ya == null || yb == null) continue;
          const w = Math.max(1, s.frac * W * 0.26);
          ctx.fillStyle = `rgba(${s.color},${s.alpha})`; ctx.fillRect(W - w, Math.min(ya, yb), w, Math.max(1, Math.abs(yb - ya) - 1));
          continue;
        }
        ctx.setLineDash('dash' in s && s.dash ? s.dash : []); ctx.lineWidth = 'width' in s && s.width ? s.width : 1;
        ctx.strokeStyle = `rgba(${s.color},${s.faded ? 0.5 : 0.95})`;
        if (s.k === 'seg') {
          const xa = this.x(s.t0), xb = s.t1 == null ? W : this.x(s.t1), ya = y(s.p0), yb = y(s.p1);
          if (xa == null || xb == null || ya == null || yb == null) continue;
          if (Math.max(xa, xb) < 0 || Math.min(xa, xb) > W) continue;
          ctx.beginPath(); ctx.moveTo(xa, ya); ctx.lineTo(xb, yb); ctx.stroke();
          if (s.label) { const lw = ctx.measureText(s.label).width; text(s.label, Math.min(xb, W) - lw - 14 - (s.t1 == null ? W * 0.27 : 0), yb - 8, s.color, s.faded); }
        } else if (s.k === 'path') {
          let started = false, lx = 0, ly = 0;
          ctx.beginPath();
          for (const q of s.pts) { const xx = this.x(q.t), yy = y(q.p); if (xx == null || yy == null) continue; if (started) ctx.lineTo(xx, yy); else { ctx.moveTo(xx, yy); started = true; } lx = xx; ly = yy; }
          if (!started) continue;
          ctx.stroke();
          if (s.label) text(s.label, lx + 6, ly, s.color, s.faded);
        } else {
          const xx = this.x(s.t), yy = y(s.p); if (xx == null || yy == null || xx < -20 || xx > W + 20 || !s.text) continue;
          ctx.font = 'bold 11px ui-monospace, Menlo, monospace';
          const w = ctx.measureText(s.text).width;
          text(s.text, xx - w / 2 - 4, yy + (s.above ? -12 : 12), s.color, s.faded, true);
        }
      }
      ctx.restore();
    });
  }
}
