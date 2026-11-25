/**
 * Whose plan is it, and whose win rate (signal-sender-v1, sender-cards-v1).
 *  - the plan card keeps showing the newest plan of EVERY sender; the word "brain" is printed only for a v18 row;
 *  - the Performance tab prints SignalMesh's sender cards line by line: n and the Evidence word beside every rate, the break-even
 *    with the word "planned", null as UNKNOWN — and no state of the read is ever shown as "no sender has posted".
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { BrainPlan, SignalRef } from '../api/types';
import SenderCardsView, { type SenderCards } from '../components/SenderCards';
import { planTitle } from '../components/TradingPanel';

afterEach(cleanup);
const sig = (system: string, name: string, brain: boolean): SignalRef => ({ signal_id: 'X', system, symbol: 'SILVER', tf: '15m', direction: 'SELL', entry: 1, sl: 2, tp1: 0.5, tp2: 0.2, rr: 1, grade: '',
  status: 'approved', confidence: null, council_approve: null, council_total: null, created_at: null, age_h: 0.1, stale: false, bucket: 'ACTIVE', reason: '', market_structure: '', pine: {},
  sender: { system, name, brain, note: '' }, rr_tp1: 0.5 });
const plan = (s: SignalRef | null): BrainPlan => ({ state: s ? 'LIVE' : 'NEVER_POSTED', signal: s, note: '', rule: '', sender: s?.sender, brain: !!s?.sender?.brain });

describe('the plan card title', () => {
  it('says "brain" only for a v18 row', () => {
    expect(planTitle(plan(sig('v18', 'Pine v18 · council', true)))).toBe('Latest brain plan');
    expect(planTitle(plan(sig('NQ-EA', 'NRTR EA', false)))).toBe('Latest plan · NRTR EA');
    expect(planTitle(plan(sig('mt5', 'MT5 EA sensor', false)))).toBe('Latest plan · MT5 EA sensor');
    expect(planTitle(plan(sig('mt5', 'MT5 EA sensor', false)))).not.toContain('brain');
    expect(planTitle(plan(null))).toBe('Latest plan');
  });
});

const row = (over: Record<string, unknown>) => ({ label: 'SCALP', sent: 200, n: 150, wins: 70, losses: 80, flat: 0, win_rate: 46.7, ci: [39.0, 54.5] as [number, number], avg_rr: 0.67, planned_be: 59.9,
  evidence: 'JUDGEABLE', reading: 'the whole interval sits BELOW the planned break-even', filled: 150, no_fill: 40, running: 10, false_break: 12, ...over });
const cards = (over: Partial<SenderCards>): SenderCards => ({ state: 'OK', note: '', terminal_rule: 'sender-cards-v1', rule: 'signal-senders-v1', reading: 'no headline win rate exists per sender', cards: [
  { id: 'S3', name: 'NQ-EA · the NRTR EAs · DEMO account', state: 'POSTED', judged_by: 'nobody on this platform', outcome_is: "a win is 'reached TP1'", sent: 300, days: 30, with_outcome: 210, without_outcome: 90,
    tables: [{ title: 'by plan kind — each line its own strategy and its own sample', kind: 'ea', rows: [row({}), row({ label: 'QML', n: 0, wins: 0, losses: 0, win_rate: null, ci: null, avg_rr: null, planned_be: null, evidence: 'UNPROVEN', reading: 'no outcome on record' })] }] },
  { id: 'S2', name: 'MT5 EA sensor', state: 'NEVER POSTED', sent: 0, days: 0, with_outcome: 0, without_outcome: 0, tables: [] },
], ...over });

describe('the sender cards on the Performance tab', () => {
  it('prints each line with its n, its Evidence word and a PLANNED break-even, and adds nothing', () => {
    render(<SenderCardsView s={cards({})} />);
    const rows = screen.getAllByTestId('sender-row');
    expect(rows).toHaveLength(2);
    const t = rows[0].textContent!;
    expect(t).toContain('SCALP'); expect(t).toContain('150'); expect(t).toContain('46.7 %'); expect(t).toContain('39 – 54.5 %');
    expect(t).toContain('59.9 % planned'); expect(t).toContain('1:0.67'); expect(t).toContain('JUDGEABLE'); expect(t).toContain('BELOW the planned break-even');
    // an unknown rate is UNKNOWN, never 0
    const u = rows[1].textContent!;
    expect(u).toContain('UNKNOWN'); expect(u).not.toContain('0 %'); expect(u).toContain('UNPROVEN');
    // an EA's "win" is named as the EA's own word, not money
    expect(screen.getAllByTestId('sender-card')[0].textContent).toContain('Not the money a position made');
    expect(screen.getAllByTestId('sender-card')[1].textContent).toContain('no row has arrived from this sender');
    // no pooled figure and no rate on the card's head
    const head = screen.getByTestId('sender-cards').textContent!;
    expect(head).toContain('no pooled rate');
    expect(document.querySelectorAll('.good, .bad').length).toBe(0);            // no colour for good or bad
  });

  it.each([['NOT_BUILT', 'NOT AVAILABLE on this platform build'], ['NOT_LOADED', 'STILL BEING COUNTED'], ['FAULT', 'could not read'], ['NOT_READ', 'NOT READ']])(
    'state %s is named and shows no card', (state, note) => {
      render(<SenderCardsView s={cards({ state, note, cards: [] })} />);
      const el = screen.getByTestId('sender-cards-state');
      expect(el.textContent).toContain(state.replace('_', ' ')); expect(el.textContent).toContain(note);
      expect(screen.queryByTestId('sender-card')).toBeNull();
    });
});
