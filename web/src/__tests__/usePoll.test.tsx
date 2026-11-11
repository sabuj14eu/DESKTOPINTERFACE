/**
 * The stale-price bug, as a unit test: a slow answer for the PREVIOUS symbol must never
 * overwrite the CURRENT symbol's data, and switching must clear the old data at once.
 * Sequence under test: GOLD -> BTC -> SILVER -> GOLD with deliberately slow responses.
 */
import { act, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { usePoll } from '../util';

type Quote = { symbol: string; price: number };
const PRICES: Record<string, number> = { GOLD: 4068.15, BTC: 75721.49, SILVER: 51.927 };

function makeLoader(delays: Record<string, number>) {
  const calls: string[] = [];
  const loader = (symbol: string) => () => new Promise<Quote>((resolve) => {
    calls.push(symbol);
    setTimeout(() => resolve({ symbol, price: PRICES[symbol] }), delays[symbol] ?? 10);
  });
  return { loader, calls };
}

function Harness({ loader }: { loader: (s: string) => () => Promise<Quote> }) {
  const [symbol, setSymbol] = useState('GOLD');
  const q = usePoll(loader(symbol), 60_000, [symbol]);
  return (
    <div>
      <span data-testid="symbol">{symbol}</span>
      <span data-testid="shown">{q.data ? `${q.data.symbol}:${q.data.price}` : 'loading'}</span>
      {['GOLD', 'BTC', 'SILVER'].map((s) => <button key={s} onClick={() => setSymbol(s)}>{s}</button>)}
    </div>
  );
}

describe('usePoll keeps every displayed price with its own symbol', () => {
  it('drops a late answer from the previous symbol and clears on switch', async () => {
    vi.useFakeTimers();
    // GOLD answers slowly (300 ms); BTC fast (10 ms); SILVER medium (50 ms)
    const { loader } = makeLoader({ GOLD: 300, BTC: 10, SILVER: 50 });
    render(<Harness loader={loader} />);
    expect(screen.getByTestId('shown').textContent).toBe('loading');

    // switch to BTC before GOLD's slow answer arrives
    await act(async () => { screen.getByText('BTC').click(); });
    expect(screen.getByTestId('shown').textContent).toBe('loading');          // cleared at once
    await act(async () => { await vi.advanceTimersByTimeAsync(20); });
    expect(screen.getByTestId('shown').textContent).toBe('BTC:75721.49');
    // now GOLD's old answer lands (300 ms after it was asked) — it must be ignored
    await act(async () => { await vi.advanceTimersByTimeAsync(400); });
    expect(screen.getByTestId('shown').textContent).toBe('BTC:75721.49');

    await act(async () => { screen.getByText('SILVER').click(); });
    expect(screen.getByTestId('shown').textContent).toBe('loading');
    await act(async () => { await vi.advanceTimersByTimeAsync(60); });
    expect(screen.getByTestId('shown').textContent).toBe('SILVER:51.927');

    await act(async () => { screen.getByText('GOLD').click(); });
    expect(screen.getByTestId('shown').textContent).toBe('loading');
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    expect(screen.getByTestId('shown').textContent).toBe('GOLD:4068.15');
    vi.useRealTimers();
  });
});
