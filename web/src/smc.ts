// SMART MONEY CONCEPTS — drawing side. The structures come from the adapter (`/api/terminal/smc`,
// smc-v1: display-only studies of stored CLOSED candles, no lookahead, no repaint). This file only
// decides WHICH of them to draw (toggles, timeframe, side, history, de-cluttering) and paints them
// on the chart through a lightweight-charts series primitive. Nothing here reaches the engine.
import type { IPrimitivePaneRenderer, IPrimitivePaneView, ISeriesPrimitive, Logical, SeriesAttachedParameter, Time } from 'lightweight-charts';

export type SmcFeature = 'sr' | 'fvg' | 'bos' | 'choch' | 'ob' | 'liq' | 'idm';
export const SMC_FEATURES: { id: SmcFeature; name: string; short: string }[] = [
  { id: 'sr', name: 'Support & Resistance', short: 'S/R' }, { id: 'fvg', name: 'Fair Value Gap', short: 'FVG' },
  { id: 'bos', name: 'Break of Structure', short: 'BOS' }, { id: 'choch', name: 'Change of Character', short: 'CHoCH' },
  { id: 'ob', name: 'Order Blocks', short: 'Order Blocks' }, { id: 'liq', name: 'Liquidity', short: 'Liquidity' },
  { id: 'idm', name: 'Inducement', short: 'Inducement' },
];
export const SMC_TFS = ['5m', '15m', '30m', '1h', '4h', '1d', '1w'] as const;
export const SMC_TF_MIN: Record<string, number> = { '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440, '1w': 10080 };
export const SMC_TF_LABEL: Record<string, string> = { '5m': 'M5', '15m': 'M15', '30m': 'M30', '1h': 'H1', '4h': 'H4', '1d': 'D1', '1w': 'W1' };

export interface SmcSettings {
  on: Record<SmcFeature, boolean>;
  tf: Record<SmcFeature, string>;          // 'chart' or an analysis timeframe
  side: 'both' | 'bull' | 'bear';
  history: boolean;                         // also draw resolved structures (mitigated, invalidated, swept, old breaks)
  opacity: number;                          // zone fill, 0.05 … 0.5
}
const all = (v: boolean) => ({ sr: v, fvg: v, bos: v, choch: v, ob: v, liq: v, idm: v });
export const SMC_DEFAULT: SmcSettings = {
  on: all(false), tf: { sr: 'chart', fvg: 'chart', bos: 'chart', choch: 'chart', ob: 'chart', liq: 'chart', idm: 'chart' },
  side: 'both', history: false, opacity: 0.16,
};
export const smcAll = (s: SmcSettings, v: boolean): SmcSettings => ({ ...s, on: all(v) });
export function smcSanitize(raw: Partial<SmcSettings> | undefined): SmcSettings {
  const d = SMC_DEFAULT; if (!raw) return d;
  const on = { ...d.on }, tf = { ...d.tf };
  for (const f of SMC_FEATURES) { on[f.id] = !!raw.on?.[f.id]; const t = raw.tf?.[f.id]; tf[f.id] = t && (t === 'chart' || (SMC_TFS as readonly string[]).includes(t)) ? t : 'chart'; }
  return { on, tf, side: raw.side === 'bull' || raw.side === 'bear' ? raw.side : 'both', history: !!raw.history,
    opacity: Math.max(0.05, Math.min(0.5, Number(raw.opacity) || d.opacity)) };
}
/** The analysis timeframe a feature really uses on this chart: its own choice when that is not below the chart's, else the chart's (M1 charts analyse M5). */
export function smcTfFor(s: SmcSettings, f: SmcFeature, chartTf: string): string {
  const base = chartTf === '1m' ? '5m' : chartTf;
  const want = s.tf[f];
  return want !== 'chart' && SMC_TF_MIN[want] >= SMC_TF_MIN[base] ? want : base;
}

// ---- adapter payload (smc-v1)
interface Row { tf: string; time?: number; confirmed_at?: number; status?: string; status_at?: number | null; dir?: string }
export interface SmcZone extends Row { low: number; high: number; filled_pct?: number; strength?: string; strength_atr?: number | null; from?: string; scope?: string; kind?: string; touches?: number; level?: number }
export interface SmcEvent extends Row { type: 'BOS' | 'CHoCH'; scope: 'external' | 'internal'; level: number; swing_time: number; note?: string }
export interface SmcLevel extends Row { level: number; side?: string; kind?: string; touches?: number; note?: string }
export interface SmcData {
  symbol: string; tf: string; state: string; note?: string; rule: string; methodology: Record<string, string>; source: string; bars_used: number;
  calculated_at: string; through_bar: number | null; through_close: number | null; atr: number | null; last_close?: number; decimals: number;
  trend: { external: string | null; internal: string | null };
  structure: SmcEvent[]; pending: SmcEvent[]; fvg: SmcZone[]; order_blocks: SmcZone[]; liquidity: SmcLevel[]; inducement: SmcLevel[]; sr: SmcZone[];
}

// ---- what gets painted
export interface Shape {
  feature: SmcFeature; kind: 'zone' | 'line'; t0: number; t1: number | null;      // t1 null = extends to the right edge
  lo: number; hi: number; color: string; fill?: number; dash?: number[]; width?: number; label: string; faded?: boolean; labelAt?: 'right' | 'mid';
}
const C = { bull: '34,197,94', bear: '244,63,94', sup: '59,130,246', res: '249,115,22', liq: '168,85,247', fvgBull: '45,212,191', fvgBear: '251,113,133', idm: '234,179,8' };
const recent = <T extends Row>(rows: T[], n: number) => [...rows].sort((a, b) => (b.confirmed_at ?? 0) - (a.confirmed_at ?? 0)).slice(0, n);
const px = (v: number, d: number) => v.toFixed(d);

export function buildShapes(s: SmcSettings, chartTf: string, data: Record<string, SmcData | undefined>, keyLevels: SmcLevel[] | undefined): { shapes: Shape[]; counts: Record<SmcFeature, number> } {
  const shapes: Shape[] = [];
  const counts: Record<SmcFeature, number> = { sr: 0, fvg: 0, bos: 0, choch: 0, ob: 0, liq: 0, idm: 0 };
  const sideOk = (dir?: string) => s.side === 'both' || !dir || dir === s.side;
  const add = (sh: Shape) => { shapes.push(sh); counts[sh.feature]++; };
  const of = (f: SmcFeature) => { const d = data[smcTfFor(s, f, chartTf)]; return d && d.state === 'OK' ? d : null; };
  const L = (tf: string) => SMC_TF_LABEL[tf] ?? tf;
  let d: SmcData | null;

  if (s.on.sr && (d = of('sr'))) {
    const ref = d.last_close ?? 0; const dd = d;
    const rows = [...d.sr].filter((z) => sideOk(z.kind === 'support' ? 'bull' : 'bear'))
      .sort((a, b) => (b.touches ?? 0) - (a.touches ?? 0) || Math.abs((a.level ?? 0) - ref) - Math.abs((b.level ?? 0) - ref)).slice(0, s.history ? 14 : 8);
    for (const z of rows) {
      const col = z.kind === 'support' ? C.sup : C.res; const weak = z.strength === 'weak';
      add(weak ? { feature: 'sr', kind: 'line', t0: z.time ?? 0, t1: null, lo: z.level!, hi: z.level!, color: col, dash: [2, 4], width: 1, label: `${L(z.tf)} prev swing ${z.kind === 'support' ? 'low' : 'high'} ${px(z.level!, dd.decimals)} · weak`, labelAt: 'right' }
        : { feature: 'sr', kind: 'zone', t0: z.time ?? 0, t1: null, lo: z.low, hi: z.high, color: col, fill: s.opacity * (z.strength === 'strong' ? 1.15 : 0.8), width: z.strength === 'strong' ? 1.5 : 1,
          label: `${L(z.tf)} ${z.kind === 'support' ? 'SUPPORT' : 'RESISTANCE'} ${px(z.level!, dd.decimals)} · ${z.strength} ×${z.touches}`, labelAt: 'right' });
    }
  }
  if (s.on.fvg && (d = of('fvg'))) {
    const live = d.fvg.filter((z) => z.status !== 'mitigated' && sideOk(z.dir));
    const old = s.history ? recent(d.fvg.filter((z) => z.status === 'mitigated' && sideOk(z.dir)), 14) : [];
    for (const z of [...recent(live, 8), ...old]) {
      const done = z.status === 'mitigated';
      add({ feature: 'fvg', kind: 'zone', t0: z.time ?? 0, t1: done ? (z.status_at ?? z.confirmed_at ?? null) : null, lo: z.low, hi: z.high, color: z.dir === 'bull' ? C.fvgBull : C.fvgBear,
        fill: s.opacity * (done ? 0.45 : 1), dash: [4, 3], faded: done,
        label: `${L(z.tf)} ${z.dir === 'bull' ? 'bull' : 'bear'} FVG · ${z.status === 'fresh' ? 'fresh' : z.status === 'partial' ? `partly mitigated ${z.filled_pct}%` : 'mitigated'}`, labelAt: 'right' });
    }
  }
  if (s.on.ob && (d = of('ob'))) {
    const live = d.order_blocks.filter((z) => z.status !== 'invalidated' && sideOk(z.dir));
    const old = s.history ? recent(d.order_blocks.filter((z) => z.status === 'invalidated' && sideOk(z.dir)), 10) : [];
    for (const z of [...recent(live, 6), ...old]) {
      const dead = z.status === 'invalidated';
      add({ feature: 'ob', kind: 'zone', t0: z.time ?? 0, t1: dead ? (z.status_at ?? null) : null, lo: z.low, hi: z.high, color: z.dir === 'bull' ? C.bull : C.bear, fill: s.opacity * (dead ? 0.4 : 1.1), faded: dead,
        width: z.strength === 'strong' ? 1.6 : 1,
        label: `${L(z.tf)} ${z.dir === 'bull' ? 'bull' : 'bear'} OB · ${z.strength}${z.strength_atr != null ? ` ${z.strength_atr} ATR` : ''} · ${z.status === 'fresh' ? 'fresh, unmitigated' : z.status}`, labelAt: 'right' });
    }
  }
  for (const f of ['bos', 'choch'] as const) {
    if (!s.on[f] || !(d = of(f))) continue;
    const type = f === 'bos' ? 'BOS' : 'CHoCH'; const dd = d;
    const ev = d.structure.filter((e) => e.type === type && sideOk(e.dir));
    const pick = [...recent(ev.filter((e) => e.scope === 'external'), s.history ? 16 : 5), ...recent(ev.filter((e) => e.scope === 'internal'), s.history ? 12 : 3)];
    for (const e of pick) {
      add({ feature: f, kind: 'line', t0: e.swing_time, t1: e.time ?? null, lo: e.level, hi: e.level, color: e.dir === 'bull' ? C.bull : C.bear, width: e.scope === 'external' ? 1.6 : 1,
        dash: f === 'choch' ? [6, 3] : e.scope === 'internal' ? [2, 3] : undefined, label: `${e.scope === 'internal' ? 'i' : ''}${type} ${L(e.tf)} ${px(e.level, dd.decimals)}`, labelAt: 'mid' });
    }
    for (const e of d.pending.filter((p) => p.type === type && sideOk(p.dir) && p.scope === 'external')) {
      add({ feature: f, kind: 'line', t0: e.swing_time, t1: null, lo: e.level, hi: e.level, color: e.dir === 'bull' ? C.bull : C.bear, width: 1, dash: [1, 5], faded: true,
        label: `${L(e.tf)} ${type}? ${px(e.level, dd.decimals)} · unconfirmed`, labelAt: 'right' });
    }
  }
  if (s.on.liq) {
    d = of('liq');
    const rows: SmcLevel[] = [...(d ? d.liquidity : []), ...(keyLevels ?? [])].filter((l) => sideOk(l.dir));
    const ref = d?.last_close ?? 0; const dec = d?.decimals ?? 2;
    const live = rows.filter((l) => l.status === 'unswept').sort((a, b) => Math.abs(a.level - ref) - Math.abs(b.level - ref)).slice(0, 10);
    const old = s.history ? recent(rows.filter((l) => l.status !== 'unswept'), 10) : recent(rows.filter((l) => l.status === 'swept'), 3);
    for (const l of [...live, ...old]) {
      const open = l.status === 'unswept';
      add({ feature: 'liq', kind: 'line', t0: l.time ?? 0, t1: open ? null : (l.status_at ?? null), lo: l.level, hi: l.level, color: C.liq, width: (l.touches ?? 1) > 1 ? 1.6 : 1, dash: open ? [5, 3] : [1, 3], faded: !open,
        label: `${L(l.tf)} ${l.side} ${l.kind} ${px(l.level, dec)} · ${l.status === 'unswept' ? 'unswept' : l.status === 'swept' ? 'SWEPT (wick)' : 'broken (close)'}`, labelAt: 'right' });
    }
  }
  if (s.on.idm && (d = of('idm'))) {
    const dd = d;
    const live = d.inducement.filter((l) => l.status === 'potential' && sideOk(l.dir));
    const old = recent(d.inducement.filter((l) => l.status !== 'potential' && sideOk(l.dir)), s.history ? 10 : 2);
    for (const l of [...recent(live, 4), ...old]) {
      const open = l.status === 'potential';
      add({ feature: 'idm', kind: 'line', t0: l.time ?? 0, t1: open ? null : (l.status_at ?? null), lo: l.level, hi: l.level, color: C.idm, width: 1, dash: [3, 3], faded: !open,
        label: `${L(l.tf)} IDM ${px(l.level, dd.decimals)} · ${open ? 'potential' : l.status === 'swept' ? 'swept — confirmed sweep' : 'broken'}`, labelAt: 'right' });
    }
  }
  return { shapes, counts };
}

/** Paints the shapes behind / over the candles. Coordinates are resolved at draw time, so zoom and scroll follow for free. */
export class SmcPrimitive implements ISeriesPrimitive<Time> {
  private p: SeriesAttachedParameter<Time> | null = null;
  private shapes: Shape[] = [];
  private times: number[] = [];
  private step = 900;
  lastDrawMs = 0;
  private views: IPrimitivePaneView[] = [
    { zOrder: () => 'bottom', renderer: (): IPrimitivePaneRenderer => ({ draw: (t) => this.draw(t, 'zone') }) },
    { zOrder: () => 'top', renderer: (): IPrimitivePaneRenderer => ({ draw: (t) => this.draw(t, 'line') }) },
  ];
  attached(p: SeriesAttachedParameter<Time>) { this.p = p; }
  detached() { this.p = null; }
  paneViews() { return this.views; }
  updateAllViews() { /* coordinates are computed in draw() */ }
  set(shapes: Shape[], times: number[], stepSec: number) { this.shapes = shapes; this.times = times; this.step = stepSec; this.p?.requestUpdate(); }

  private x(t: number): number | null {
    const ts = this.times; const p = this.p; if (!p || !ts.length) return null;
    let idx: number;
    if (t <= ts[0]) idx = (t - ts[0]) / this.step;
    else if (t >= ts[ts.length - 1]) idx = ts.length - 1 + (t - ts[ts.length - 1]) / this.step;
    else { let lo = 0, hi = ts.length - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (ts[m] < t) lo = m + 1; else hi = m; } idx = lo; }
    return p.chart.timeScale().logicalToCoordinate(idx as Logical);
  }

  private draw(target: Parameters<IPrimitivePaneRenderer['draw']>[0], layer: 'zone' | 'line') {
    const p = this.p; if (!p || !this.shapes.length) return;
    const t0 = performance.now();
    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const W = mediaSize.width, H = mediaSize.height;
      const placed: [number, number, number, number][] = [];
      const text = (label: string, x: number, y: number, color: string, faded?: boolean) => {
        ctx.font = '10px ui-monospace, Menlo, monospace';
        const w = ctx.measureText(label).width + 8; const bx = Math.max(2, Math.min(W - w - 2, x)); const by = Math.max(2, Math.min(H - 14, y - 7));
        if (placed.some(([a, b, c, d]) => bx < a + c && bx + w > a && by < b + d && by + 13 > b)) return;      // de-clutter: an overlapping label is not drawn
        placed.push([bx, by, w, 13]);
        ctx.fillStyle = 'rgba(11,18,32,.82)'; ctx.fillRect(bx, by, w, 13);
        ctx.fillStyle = `rgba(${color},${faded ? 0.6 : 1})`; ctx.textBaseline = 'middle'; ctx.fillText(label, bx + 4, by + 7);
      };
      ctx.save();
      for (const s of this.shapes) {
        if (s.kind !== layer) continue;
        const xa = this.x(s.t0); const xb = s.t1 == null ? W : this.x(s.t1);
        const ya = p.series.priceToCoordinate(s.hi); const yb = p.series.priceToCoordinate(s.lo);
        if (xa == null || xb == null || ya == null || yb == null) continue;
        const x0 = Math.max(-2, Math.min(xa, xb)), x1 = Math.min(W + 2, Math.max(xa, xb));
        if (x1 < 0 || x0 > W || Math.max(ya, yb) < 0 || Math.min(ya, yb) > H) continue;
        ctx.setLineDash(s.dash ?? []); ctx.lineWidth = s.width ?? 1; ctx.strokeStyle = `rgba(${s.color},${s.faded ? 0.45 : 0.9})`;
        if (s.kind === 'zone') {
          const h = Math.max(1, yb - ya);
          ctx.fillStyle = `rgba(${s.color},${s.fill ?? 0.15})`; ctx.fillRect(x0, ya, x1 - x0, h); ctx.strokeRect(x0 + 0.5, ya + 0.5, x1 - x0, h);
          text(s.label, x1 - ctx.measureText(s.label).width - 14, ya + 8, s.color, s.faded);
        } else {
          ctx.beginPath(); ctx.moveTo(x0, ya + 0.5); ctx.lineTo(x1, ya + 0.5); ctx.stroke();
          const lw = ctx.measureText(s.label).width;
          text(s.label, s.labelAt === 'mid' ? (x0 + x1) / 2 - lw / 2 : x1 - lw - 14, ya - 8, s.color, s.faded);
        }
      }
      ctx.restore();
    });
    this.lastDrawMs = performance.now() - t0;
  }
}
