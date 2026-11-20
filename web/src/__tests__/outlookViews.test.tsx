/**
 * The three outlook views (outlook-views-v1): Market Outlook, the Call Ledger and the Turning Point record.
 * The laws they are held to:
 *  - "HAS BEEN", NEVER "WILL": question one reports what price has done; no forecast word, no likelihood, no arrow;
 *  - UNKNOWN IS NOT A DIRECTION: UNKNOWN, NO CLEAR TREND and a SERIES FAULT are printed as what they are, in neutral colour;
 *  - UNPROVEN STAYS UNPROVEN: counts and a hit rate are printed without green or red;
 *  - NOTHING TRADES ON THIS: no button in any of the three views;
 *  - a route the platform has not shipped reads NOT BUILT, never an empty panel.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { CallLedger, MarketOutlook, TurningPoints } from '../outlook';
import { CallLedgerView, MarketOutlookView, TurningPointView, day } from '../components/OutlookTabs';

afterEach(cleanup);
const RULE = 'outlook-views-v1';
const board = { calls: 6, pending: 2, resolved: 4, hits: 1, invalidated: 1, expired: 1, both: 1, hit_rate: 0.25, label: 'UNPROVEN', verdict: 'UNPROVEN — 3 call(s) resolved with an invalidation level; under 20 is luck (Evidence Law)' };
const lvl = (value: number, name: string) => ({ value, name, date: '2026-11-20', dist_pct: 0.1037, dist_atr: 0.972 });
const down: MarketOutlook = {
  state: 'OK', terminal_rule: RULE, rule: 'market-scenarios-v1', symbol: 'GOLD', as_of: '2026-11-20T23:08:01+00:00', read_at: '2026-11-20T23:09:00+00:00', decimals: 2,
  plain: 'Three questions from closed daily candles: where price HAS been heading, the level where it gets interesting, and the daily close that would prove the reading wrong. A state, not a forecast.',
  authority: 'a description of closed daily bars and the levels on them — scenarios, not a forecast.',
  read: { state: 'DOWN', structure: 'LH/LL', structure_rule: 'structure-v1', bars: 120, bar_day: '2026-11-20', bar_age_days: 0.0, close: 4820, atr: 5.14286, series_fault: '', reason: '',
    heading: { word: 'DOWN so far', why: 'lower highs and lower lows on the daily chart: the last two confirmed swing highs fell and the last two swing lows fell' },
    interesting: [{ kind: 'WITH THE TREND', text: 'a rally up into this resistance is where a seller of rallies looks', level: lvl(4825, 'prior day high'), then: lvl(4841.5, 'prior week low') }],
    wrong: { side: 'above', value: 4866, text: 'a daily CLOSE above the last confirmed swing high: the lower-highs structure this reading rests on would be broken', dist_pct: 0.954, dist_atr: 8.94 },
    above: [lvl(4825, 'prior day high')], below: [lvl(4819, 'prior day low')], swing_highs: [4896, 4866], swing_lows: [4879, 4849] },
  overview: [{ symbol: 'GOLD', state: 'DOWN', close: 4820, bar_day: '2026-11-20', reason: '', above: lvl(4825, 'prior day high'), below: lvl(4819, 'prior day low'), wrong: { side: 'above', value: 4866, text: '' }, decimals: 2 },
    { symbol: 'US100', state: 'UNKNOWN', close: 4820, bar_day: '2026-11-20', reason: '40 date(s) carry TWO daily bars in the last 160 — two series under one name', above: null, below: null, wrong: null, decimals: 1 }],
  track: { rule: 'system-daily-call-v1', atr_mult: 1.0, board, here: { calls: 2, hits: 1, invalidated: 0 }, open: { direction: 'BEARISH', ref_price: 4300, target: 4294.86, invalidation: 4305.14, recorded_at: '2026-11-20T23:08:00+00:00' } },
};
const unknownRead = (over: object): MarketOutlook => ({ ...down, read: { state: 'UNKNOWN', structure: 'UNKNOWN', bars: 30, close: null, atr: null, heading: null, interesting: [], wrong: null, above: [], below: [], series_fault: '', reason: 'only 30 closed daily bars stored — 60 needed before a daily structure is trustworthy', ...over } });
// words that would turn a description into a prediction; none may appear in the Market Outlook view
const FORECAST = /\bwill\b|probab|confiden|likely|chance of|expect|predicts? (a|the|that)|↑|↓|▲|▼|→ (up|down)/i;

describe('Market Outlook', () => {
  it('opens with the platform\'s plain sentence and asks the three questions in the platform\'s words', () => {
    render(<MarketOutlookView d={down} symbol="GOLD" />);
    expect(screen.getByTestId('outlook-plain').textContent).toBe(down.plain);
    expect(screen.getByTestId('outlook-q1').textContent).toContain('Where has price been heading?');
    expect(screen.getByTestId('outlook-q2').textContent).toContain('At which level does it get interesting?');
    expect(screen.getByTestId('outlook-q3').textContent).toContain('What would prove this wrong?');
    expect(screen.getByTestId('outlook-heading').textContent).toBe('DOWN so far');
    expect(screen.getByTestId('outlook-q3').textContent).toContain('a daily close above 4866.00');
  });

  it('shows real prices with their bar date, and the reading\'s own bar and read time', () => {
    render(<MarketOutlookView d={down} symbol="GOLD" />);
    const t = screen.getByTestId('outlook').textContent!;
    expect(t).toContain('4825.00 prior day high (20 Nov 2026 bar · 0.1% away · 1.0 daily ATR)');
    expect(t).toContain('last daily close 4820.00 · 20 Nov 2026 bar');
    expect(t).toContain('SignalMesh read 2026-11-20 23:08');
    expect(t).toContain('ATR = the usual size of one daily bar — for GOLD now about 5.14');
    expect(screen.getByTestId('outlook-track-open').textContent).toContain('BEARISH from 4300.00 — continues at 4294.86, turned at 4305.14');
  });

  it('says HAS BEEN and never WILL: no forecast word, no likelihood, no arrow', () => {
    render(<MarketOutlookView d={down} symbol="GOLD" />);
    const t = screen.getByTestId('outlook').textContent!.replace('swing highs 4896.00 → 4866.00', '').replace('swing lows 4879.00 → 4849.00', '').replace('whether patterns on these candles predict the next move, and none did', '');
    expect(t).not.toMatch(FORECAST);
    expect(t).toContain('This is what price HAS done, not what it does next');
    expect(t).toContain('not a forecast and not a signal');
  });

  it('prints UNKNOWN as UNKNOWN, in a neutral colour, with the platform\'s reason — and asks no question it cannot answer', () => {
    render(<MarketOutlookView d={unknownRead({})} symbol="ANT" />);
    const st = screen.getByTestId('outlook-state');
    expect(st.textContent).toContain('UNKNOWN — only 30 closed daily bars stored');
    expect(st.textContent).toContain('UNKNOWN is not a direction');
    expect(st.className).toBe('ov-neutral');
    expect(screen.queryByTestId('outlook-q1')).toBeNull();
    expect(screen.queryByTestId('outlook-above')).toBeNull();
  });

  it('prints a SERIES FAULT as one, reads nothing from the series, and stays neutral', () => {
    render(<MarketOutlookView d={unknownRead({ close: 4820, bars: 160, bar_day: '2026-11-20', series_fault: '40 date(s) carry TWO daily bars in the last 160 — two series under one name', reason: 'the daily series is not one clean series' })} symbol="US100" />);
    const st = screen.getByTestId('outlook-state');
    expect(st.textContent).toContain('SERIES FAULT — 40 date(s) carry TWO daily bars');
    expect(st.textContent).toContain('Nothing is read from this series');
    expect(st.querySelector('.good, .bad')).toBeNull();
    expect(screen.queryByTestId('outlook-q1')).toBeNull();
  });

  it('NO CLEAR TREND is not coloured as a direction and has nothing to prove wrong', () => {
    const d: MarketOutlook = { ...down, read: { ...down.read!, state: 'NO CLEAR TREND', structure: 'MIXED', heading: { word: 'NO CLEAR TREND', why: 'the last two daily swing highs and swing lows disagree — measured, and it is not a direction' }, wrong: null } };
    render(<MarketOutlookView d={d} symbol="BTC" />);
    expect(screen.getByTestId('outlook-heading').className).toBe('ov-word muted');
    expect(screen.getByTestId('outlook-q3').textContent).toContain('There is no trend reading to break: the structure is MIXED');
  });

  it('the counted record prints UNPROVEN and its counts without green or red', () => {
    render(<MarketOutlookView d={down} symbol="GOLD" />);
    const box = screen.getByTestId('outlook-track');
    expect(screen.getByTestId('outlook-track-verdict').textContent).toBe(board.verdict);
    expect(box.textContent).toContain('6 call(s) · 2 open · 1 continued · 1 turned · 1 expired · 1 reached both levels in one bar · continued 25% of 4 finished');
    expect(box.querySelector('.good, .bad')).toBeNull();
  });

  it('the overview keeps a faulted or unknown asset neutral with its reason', () => {
    render(<MarketOutlookView d={down} symbol="GOLD" />);
    const row = screen.getByTestId('outlook-overview').querySelector('[data-row=US100]')!;
    expect(row.textContent).toContain('UNKNOWN');
    expect(row.textContent).toContain('TWO daily bars');
    expect(row.querySelector('.good, .bad')).toBeNull();
  });

  it('a platform without the route reads NOT BUILT, never an empty panel', () => {
    render(<MarketOutlookView d={{ state: 'NOT_BUILT', terminal_rule: RULE, note: 'NOT BUILT — this SignalMesh build has no GET /api/v1/market/outlook route (it arrived in platform 5.210). Nothing is shown in its place.' }} symbol="GOLD" />);
    const t = screen.getByTestId('outlook-not-built').textContent!;
    expect(t).toContain('NOT BUILT — this SignalMesh build has no GET /api/v1/market/outlook route');
    expect(screen.queryByTestId('outlook-overview')).toBeNull();
  });

  it('wires nothing to trade: no button anywhere in the view', () => {
    render(<MarketOutlookView d={down} symbol="GOLD" />);
    expect(screen.getByTestId('outlook').querySelectorAll('button, input, select, a').length).toBe(0);
  });
});

describe('Call Ledger', () => {
  const led: CallLedger = { state: 'OK', terminal_rule: RULE, rule: 'system-daily-call-v1', scoring_rule: 'analyst-ledger-v1', analyst: 'SignalMesh daily', as_of: '2026-11-20T23:08:01+00:00',
    plain: 'The system writes down its own daily-trend call per asset and the candles score it. Equal distance both ways, so a coin is right half the time. Under 20 finished calls the verdict is UNPROVEN.',
    definition: 'one call per asset when the daily structure reads UP or DOWN', board,
    rows: [{ id: 2, symbol: 'SILVER', direction: 'BULLISH', ref_price: 50, target: 54.479, invalidation: 45.521, recorded_at: '2026-11-20T23:08:00+00:00', expires_at: '2026-12-20T23:08:00+00:00', why: 'daily structure HH/HL on the 20 Nov 2026 bar', outcome: 'PENDING', outcome_at: null, r: null, stored: false, decimals: 3 },
      { id: 1, symbol: 'GOLD', direction: 'BEARISH', ref_price: 4400, target: 4356, invalidation: 4444, recorded_at: '2026-11-11T23:08:00+00:00', why: 'daily structure LH/LL', outcome: 'TARGET HIT', outcome_at: '2026-11-13T23:08:00+00:00', r: 1, stored: true, decimals: 2 },
      { id: 3, symbol: 'EURUSD', direction: 'BEARISH', ref_price: 1.085, target: 1.07415, invalidation: 1.09585, recorded_at: '2026-11-13T23:08:00+00:00', why: '', outcome: 'INVALIDATED', outcome_at: '2026-11-15T23:08:00+00:00', r: -1, stored: false, decimals: 5 }] };

  it('opens with the platform\'s plain sentence, explains its words, and prints every row with real prices', () => {
    render(<CallLedgerView d={led} />);
    expect(screen.getByTestId('ledger-plain').textContent).toBe(led.plain);
    const t = screen.getByTestId('ledger').textContent!;
    for (const w of ['Nobody types these', 'Invalidation = the price that proves it wrong', 'R = the result counted in units']) expect(t).toContain(w);
    const rows = screen.getByTestId('ledger-rows').querySelectorAll('tbody tr');
    expect(rows.length).toBe(3);
    expect(rows[0].textContent).toContain('SILVERBULLISH50.00054.47945.521');
    expect(rows[1].textContent).toContain('TARGET HIT');
    expect(rows[1].textContent).toContain('+1.00');
    expect(rows[2].textContent).toContain('−1.00'.replace('−', '-'));
  });

  it('UNPROVEN stays UNPROVEN: the verdict is the platform\'s and nothing is green or red — not the rate, not an outcome, not an R', () => {
    render(<CallLedgerView d={led} />);
    expect(screen.getByTestId('ledger-verdict').textContent).toBe(board.verdict);
    expect(screen.getByTestId('ledger-counts').textContent).toContain('continued 25% of 4 finished');
    expect(screen.getByTestId('ledger').querySelector('.good, .bad')).toBeNull();
  });

  it('says when a finished call\'s outcome is not stored on the row yet', () => {
    render(<CallLedgerView d={led} />);
    const rows = screen.getByTestId('ledger-rows').querySelectorAll('tbody tr');
    expect(rows[2].textContent).toContain('INVALIDATED · not stored yet');
    expect(rows[1].textContent).not.toContain('not stored yet');
    expect(rows[0].textContent).not.toContain('not stored yet');     // a pending call has no outcome to store
  });

  it('an empty ledger says why, and a missing route says NOT BUILT', () => {
    render(<CallLedgerView d={{ ...led, rows: [], board: { calls: 0, verdict: 'NO RESOLVED CALL YET — nothing is known in either direction' } }} />);
    expect(screen.getByTestId('ledger-rows').textContent).toContain('no call is not a failed call');
    cleanup();
    render(<CallLedgerView d={{ state: 'NOT_BUILT', terminal_rule: RULE, note: 'NOT BUILT — this SignalMesh build has no GET /api/v1/ledger/system route (it arrived in platform 5.210).' }} />);
    expect(screen.getByTestId('ledger-not-built').textContent).toContain('NOT BUILT — this SignalMesh build has no GET /api/v1/ledger/system route');
  });

  it('wires nothing to trade', () => {
    render(<CallLedgerView d={led} />);
    expect(screen.getByTestId('ledger').querySelectorAll('button, input, select, a').length).toBe(0);
  });
});

describe('Turning Point record', () => {
  const word = (n: number, hits: number, base: number, verdict: string) => ({ n, hits, hit_rate: hits / n, base_rate: base, lift: hits / n - base, lift_needed: 0.15, verdict });
  const tp: TurningPoints = { state: 'OK', terminal_rule: RULE, rule: 'turning-point-record-v1', as_of: '2026-11-20T23:08:01+00:00', config_hash: '88c19c433d611210',
    plain: 'The score of an old exam, not today\'s price: how often a model\'s \'falls first\' or \'rises first\' came true, against how often it happens anyway.',
    question: { horizon_bars: 24, atr_mult: 1.0, threshold: 0.6, touch_on: 'close' }, total_rows: 58, skill_rows: 58, shadow_rows: 0,
    overall: { word: 'NO ROBUST EDGE', why: '1 of 1 cell(s) examined carry a judged word (n ≥ 20) and none beats its base rate' },
    gate: { open: false, why: 'NO FORECAST CARD — stopped at: P1 search — a word beats its base rate by more than noise', steps: [{ name: 'P1 search — a word beats its base rate by more than noise', passed: false }, { name: 'P2 shadow — live calls stored for 14 days, outcomes filled', passed: false, note: 'never armed: no shadow call was ever stored' }] },
    words: { top: 'PROBABLE TOP', bottom: 'PROBABLE BOTTOM' },
    cells: [{ symbol: 'GOLD', tf: '1h', model_repo: 'repo/x', model_revision: 'rev-a', readable: true, rows: 58, word: 'NO ROBUST EDGE', candidate_words: [], held_words: [], holdout_state: 'NOT SPENT', computed_from: '2026-11-20T23:08:00+00:00', decimals: 2, holdout: null,
      search: { points: 58, independent: 58, base: { down: 0.41, up: 0.59, none: 0 }, brier_down: 0.461, brier_ref_down: 0.243, brier_up: 0.461, brier_ref_up: 0.243, first_as_of: '2020-01-06T00:00:00+00:00', last_as_of: '2020-03-03T00:00:00+00:00',
        example: { as_of: '2020-03-03T00:00:00+00:00', price: 100, atr: 1, down_at: 99, up_at: 101 },
        words: { 'PROBABLE TOP': word(28, 9, 0.41, 'NO ROBUST EDGE (hit rate not above the base rate) — a valid end'), 'PROBABLE BOTTOM': word(21, 10, 0.59, 'NO ROBUST EDGE (hit rate not above the base rate) — a valid end') } } }] };

  it('opens with the platform\'s plain sentence, the overall word, and why there is no forecast card', () => {
    render(<TurningPointView d={tp} />);
    expect(screen.getByTestId('tp-plain').textContent).toBe(tp.plain);
    expect(screen.getByTestId('tp-word').textContent).toBe('NO ROBUST EDGE');
    const gate = screen.getByTestId('tp-gate').textContent!;
    expect(gate).toContain('NO FORECAST CARD — stopped at: P1 search');
    expect(gate).toContain('no reading for today');
    expect(gate).toContain('✗ P2 shadow — live calls stored for 14 days, outcomes filled — never armed: no shadow call was ever stored');
  });

  it('one box per cell, with the question\'s real prices and the platform\'s own counts and verdicts', () => {
    render(<TurningPointView d={tp} />);
    const cells = screen.getAllByTestId('tp-cell');
    expect(cells.length).toBe(1);
    const t = cells[0].textContent!;
    expect(t).toContain('GOLD · 1h');
    expect(screen.getByTestId('tp-example').textContent).toContain('price was 100.00 and one ATR was 1.00, so the question was "does it reach 99.00 first, or 101.00 first?"');
    expect(t).toContain('PROBABLE TOP289 (32%)41%-9 pts+15 ptsNO ROBUST EDGE (hit rate not above the base rate) — a valid end');
    expect(t).toContain('holdout NOT SPENT');
  });

  it('explains its words and shows no direction for today', () => {
    render(<TurningPointView d={tp} />);
    const t = screen.getByTestId('turning-points').textContent!;
    for (const w of ['not about today\'s price', 'score of an old exam', 'Came true = how often the model was right', 'Happens anyway = how often price did that with no model at all']) expect(t).toContain(w);
    expect(t).not.toMatch(/confiden/i);
    expect(screen.getByTestId('turning-points').querySelector('.good, .bad')).toBeNull();
    expect(screen.getByTestId('turning-points').querySelectorAll('button, input, select, a').length).toBe(0);
  });

  it('an empty record is not a clean result, and a missing route says NOT BUILT', () => {
    render(<TurningPointView d={{ ...tp, cells: [], overall: { word: 'NO RECORD', why: 'no stored row answers this build\'s question' } }} />);
    expect(screen.getByTestId('turning-points').textContent).toContain('an empty table is not a clean result');
    cleanup();
    render(<TurningPointView d={{ state: 'NOT_BUILT', terminal_rule: RULE, note: 'NOT BUILT — this SignalMesh build has no GET /api/v1/turning-points route (it arrived in platform 5.210).' }} />);
    expect(screen.getByTestId('turning-points-not-built').textContent).toContain('NOT BUILT');
  });
});

describe('dates', () => {
  it('re-spells the platform\'s date and shifts nothing', () => {
    expect(day('2026-11-20')).toBe('20 Nov 2026');
    expect(day('2020-03-05T00:00:00+00:00')).toBe('5 Mar 2020');
    expect(day(null)).toBe('NOT AVAILABLE');
  });
});
