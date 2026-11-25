/**
 * a desk that was NOT READ is not a desk that found nothing.
 * Before this, a timeout of GET /api/v1/market/desk printed "the desk returned no lanes for GOLD" — a sentence about
 * the platform's answer when there was no answer. The two facts now have two sentences.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { DeskLanesEmpty } from '../components/TradingPanel';

afterEach(cleanup);

describe('the Desk lanes box with no lane to print', () => {
  it('says NOT READ, with the read\'s own failure word and the wait, when the desk did not answer', () => {
    render(<DeskLanesEmpty symbol="GOLD" read={{ state: 'NOT_READ', provider_state: 'DOWN', error: 'SignalMesh unreachable: ReadTimeout: timed out', timeout_s: 20, note: '' }} />);
    const el = screen.getByTestId('desk-not-read');
    expect(el.textContent).toContain('NOT READ');
    expect(el.textContent).toContain('DOWN');
    expect(el.textContent).toContain('20 s');
    expect(el.textContent).toContain('Nothing is said about the market');
    expect(el.textContent).not.toContain('returned no lanes');
    expect(el.getAttribute('title')).toContain('ReadTimeout');
    expect(screen.queryByTestId('desk-no-lanes')).toBeNull();
  });

  it('says the desk returned no lanes only when the desk answered', () => {
    render(<DeskLanesEmpty symbol="GOLD" read={{ state: 'OK', provider_state: '', error: '', timeout_s: null, note: '' }} />);
    expect(screen.getByTestId('desk-no-lanes').textContent).toBe('the desk returned no lanes for GOLD');
    expect(screen.queryByTestId('desk-not-read')).toBeNull();
  });

  it('keeps the old sentence for an adapter that sends no desk_read key', () => {
    render(<DeskLanesEmpty symbol="GOLD" />);
    expect(screen.getByTestId('desk-no-lanes').textContent).toBe('the desk returned no lanes for GOLD');
  });
});
