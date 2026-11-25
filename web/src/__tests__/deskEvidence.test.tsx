/**
 * Platform 5.206 and 5.211 on the Desk lanes box and the verdict board:
 *  - a history cell that is not loaded yet reads NOT LOADED YET, never n=0;
 *  - the platform's cells_note is printed word for word above the rows, in the warning colour when the cells are not ready;
 *  - a small cell prints the platform's `level` sentence even when it was not backed off (a single stock is never pooled);
 *  - without the new keys (an older platform) the lines read as they did in 2.9.0.
 * Every word asserted here is the platform's; the component computes none of it.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { LaneCard, VerdictBoard, VerdictBoardRow } from '../api/types';
import { ownHistoryLine, VerdictBoardCard } from '../components/TradingPanel';

const lane = (own_history: LaneCard['own_history'], extra: Partial<LaneCard> = {}): LaneCard => ({
  label: 'Session', engine: 'session-v1', tf: '1h', decision: 'BUY', order_type: 'BUY LIMIT', entry: 1, sl: 0.9, tp1: 1.1, tp2: 1.2, rr1: 1, reasons: [], verdict: '', paper: true,
  own_history, verdict_v1: { verdict: 'POSITIVE', icon: '✓', tone: 'good' }, verdict_v2: { verdict: 'CANNOT SEPARATE', icon: '?', tone: 'unknown' }, ...extra,
});
afterEach(cleanup);   // this vitest setup has no globals, so the library does not unmount between tests by itself
const Line = ({ l }: { l: LaneCard }) => <div data-testid="line">{ownHistoryLine(l)}</div>;
const unk = { verdict: 'UNKNOWN', icon: '?', tone: 'unknown' };
const row = (over: Partial<VerdictBoardRow>): VerdictBoardRow => ({
  engine: 'scalp-v1', label: 'Scalp', tf: '15m', key: 'HH/HL-BUY', structure: 'HH/HL', direction: 'BUY', current: false, n: 0, symbol_n: 0, backed_off: false, level: '',
  expectancy_r: null, sd: null, wins: 0, losses: 0, lo_r: null, hi_r: null, v1: unk, v2: unk, change: 'UNDER THE FLOOR', change_why: '', ...over,
});
const board = (over: Partial<VerdictBoard>): VerdictBoard => ({
  state: 'OK', note: '', rule: 'verdict-board-v1', terminal_rule: '', symbol: 'ETH', rows: [], is_not: 'not a performance comparison', authority: 'PAPER', fault: '', paper: true,
  summary: { cells: 8, measured: 0, under_floor: 8, backed_off: 0, v1_positive: 0, v1_negative: 0, v2_positive: 0, v2_negative: 0, v2_cannot_separate: 0, ticks_withdrawn: 0, crosses_withdrawn: 0 },
  rules: { cell: 'lane-history-v2 — each engine\'s own resolved paper fills' }, ...over,
});

describe('a lane\'s own-history line', () => {
  it.each(['COMPUTING', 'COLD', 'FAILED'])('reads NOT LOADED YET with the platform\'s sentence when the cell is %s — never n=0', (state) => {
    render(<Line l={lane({ rule: 'lane-history-v2', state, cells_age_s: null, n: 0, symbol_n: 0, backed_off: false, level: `session-v1 × ETH × HH/HL-BUY — history cells ${state}: computed off the page` })} />);
    const t = screen.getByTestId('line').textContent!;
    expect(t).toContain('own history: NOT LOADED YET');
    expect(t).toContain(`history cells ${state}`);
    expect(t).not.toContain('n=0');
    expect(t).not.toContain('UNKNOWN');
  });

  it('a loaded cell with no fills still reads UNKNOWN (n=0), with the cell\'s name', () => {
    render(<Line l={lane({ rule: 'lane-history-v2', state: 'FRESH', cells_age_s: 240, n: 0, symbol_n: 0, backed_off: false, level: 'swing-v1 × GOLD × HH/HL-BUY' })} />);
    expect(screen.getByTestId('line').textContent).toContain('own history: UNKNOWN (n=0) · swing-v1 × GOLD × HH/HL-BUY');
  });

  it('a single stock\'s small cell prints the platform\'s reason although it was not backed off', () => {
    const level = 'session-v1 × ANT × HH/HL-BUY — n=3, under 20; a single stock is never pooled with other assets';
    render(<Line l={lane({ rule: 'lane-history-v2', state: 'FRESH', n: 3, symbol_n: 3, backed_off: false, expectancy_r: 0.333, level }, { verdict_v1: unk, verdict_v2: unk })} />);
    const t = screen.getByTestId('line').textContent!;
    expect(t).toContain('n=3');
    expect(t).toContain(level);
  });

  it('a measured cell of its own (n of 20 or more, not backed off) prints no level sentence', () => {
    render(<Line l={lane({ rule: 'lane-history-v2', state: 'FRESH', n: 132, symbol_n: 132, backed_off: false, expectancy_r: 0.047, level: 'scalp-v1 × GOLD × HH/HL-BUY' })} />);
    const t = screen.getByTestId('line').textContent!;
    expect(t).toContain('own history: n=132 · +0.047R · CANNOT SEPARATE ? · v1 POSITIVE ✓');
    expect(t).not.toContain('scalp-v1 × GOLD');
  });

  it('without a state key (a platform before 5.206) the line is the 2.9.0 line', () => {
    render(<Line l={lane({ rule: 'lane-history-v1', n: 47, symbol_n: 9, backed_off: true, expectancy_r: 0.118, level: 'session-v1 × all symbols × HH/HL-BUY — the GOLD cell holds n=9, under 20' })} />);
    expect(screen.getByTestId('line').textContent).toBe('own history: n=47 · +0.118R · CANNOT SEPARATE ? · v1 POSITIVE ✓ · session-v1 × all symbols × HH/HL-BUY — the GOLD cell holds n=9, under 20');
  });
});

describe('the verdict board and the platform\'s history cells', () => {
  const NOTE = 'HISTORY CELLS NOT LOADED YET (COMPUTING) — they are computed off the page after a restart; every row below reads UNKNOWN until they land. Reload in a minute.';

  it('prints cells_note word for word, in the warning colour, while the box is still folded — and no row says UNDER THE FLOOR without its reason', () => {
    render(<VerdictBoardCard symbol="ETH" vb={board({ cells_ready: false, cells_note: NOTE, rows: [row({ cells_state: 'COMPUTING', cells_age_s: null })] })} />);
    const note = screen.getByTestId('verdict-board-cells-note');
    expect(note.textContent).toBe(NOTE);
    expect(note.className).toBe('warn');
    expect(screen.queryByTestId('verdict-board-rows')).toBeNull();
    fireEvent.click(screen.getByTestId('verdict-board-toggle'));
    expect(screen.getByTestId('verdict-board-rows').textContent).toContain('UNDER THE FLOOR — history cells COMPUTING: NOT LOADED YET');
  });

  it('prints the note quietly when the cells are loaded, and leaves the change word alone', () => {
    const ready = 'history cells computed 4 min ago off the page (lane-cells-v1), refreshed about every 10 minutes';
    render(<VerdictBoardCard symbol="GOLD" vb={board({ cells_ready: true, cells_note: ready, rows: [row({ cells_state: 'FRESH', cells_age_s: 240 })] })} />);
    const note = screen.getByTestId('verdict-board-cells-note');
    expect(note.textContent).toBe(ready);
    expect(note.className).toBe('dim');
    fireEvent.click(screen.getByTestId('verdict-board-toggle'));
    expect(screen.getByTestId('verdict-board-rows').textContent).not.toContain('NOT LOADED YET');
  });

  it('prints no note at all when the platform sent none (before 5.206)', () => {
    render(<VerdictBoardCard symbol="GOLD" vb={board({ rows: [row({})] })} />);
    expect(screen.queryByTestId('verdict-board-cells-note')).toBeNull();
  });

  it('prints the cell rule from the payload, whichever version it names', () => {
    render(<VerdictBoardCard symbol="GOLD" vb={board({ rows: [row({})] })} />);
    fireEvent.click(screen.getByTestId('verdict-board-toggle'));
    expect(screen.getByTestId('verdict-board').textContent).toContain('cell: lane-history-v2');
  });
});

describe('the lane history counted by plans (platform 5.214)', () => {
  const PLANS = 'by plans (lane-cells-v2): UNKNOWN ? — 31 plan(s) on 9 day(s), standing for 412 bar(s), mean +0.101R (31 plans, but born on only 9 day(s) — under the floor of 20 days)';

  it('with a plan count the old line is labelled "by bars (an upper bound)"; without one it reads as before', () => {
    const h = { rule: 'lane-history-v2', state: 'FRESH', n: 132, symbol_n: 132, backed_off: false, expectancy_r: 0.047, level: 'scalp-v1 × GOLD × HH/HL-BUY' };
    render(<Line l={lane(h, { own_history_plans_line: PLANS, own_history_plans: { rule: 'lane-history-v3', cells_rule: 'lane-cells-v2', n: 31, verdict: { verdict: 'UNKNOWN', tone: 'unknown', held_by: 'days floor' } } })} />);
    expect(screen.getByTestId('line').textContent).toContain('by bars (an upper bound): n=132 · +0.047R');
    cleanup();
    render(<Line l={lane(h)} />);
    expect(screen.getByTestId('line').textContent).toContain('own history: n=132 · +0.047R');
  });

  it('the board prints the plan count first, with the platform\'s own note and sentence, and labels the bar count', () => {
    render(<VerdictBoardCard symbol="GOLD" vb={board({ plans: { rule: 'lane-history-v3', cells_rule: 'lane-cells-v2', days_floor: 20, positive: 1, negative: 0, cannot_separate: 2, unknown: 5, note: 'Read that column.' },
      rows: [row({ plans_line: PLANS, plans: { verdict: { verdict: 'UNKNOWN', tone: 'unknown' } } })] })} />);
    const top = screen.getByTestId('verdict-board-plans').textContent!;
    expect(top).toContain('BY PLANS (lane-history-v3 on lane-cells-v2): 1✓ · 0✗ · 2 cannot separate · 5 unknown');
    expect(top).toContain('Read that column.');
    expect(screen.getByTestId('verdict-board-summary').textContent).toContain('BY BARS (an upper bound) — ');
    fireEvent.click(screen.getByTestId('verdict-board-toggle'));
    expect(screen.getByTestId('vrow-plans').textContent).toBe(PLANS);
    expect(screen.getByTestId('verdict-board-rows').textContent).toContain('by bars:');
  });

  it('prints nothing about plans when the platform sent none', () => {
    render(<VerdictBoardCard symbol="GOLD" vb={board({ rows: [row({})] })} />);
    expect(screen.queryByTestId('verdict-board-plans')).toBeNull();
    expect(screen.getByTestId('verdict-board-summary').textContent).not.toContain('BY BARS');
  });
});
