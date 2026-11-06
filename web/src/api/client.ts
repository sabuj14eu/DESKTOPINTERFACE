import type { CandleSeries, DecisionView, Health, MarketWatchRow, SignalRef, Ticket, TradeRow } from './types';

const TOKEN_KEY = 'smt_token';
export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; } };
export const setToken = (t: string) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* private window */ } };

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...(init?.headers as Record<string, string> | undefined) };
  const tok = getToken();
  if (tok) headers['X-Terminal-Token'] = tok;
  const r = await fetch(path, { ...init, headers });
  const text = await r.text();
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!r.ok) {
    const detail = (body && typeof body === 'object' && 'detail' in body) ? (body as { detail: unknown }).detail : body;
    throw new ApiError(r.status, typeof detail === 'string' ? detail : JSON.stringify(detail), body);
  }
  return body as T;
}

export const api = {
  health: () => call<Health>('/api/terminal/health'),
  marketWatch: () => call<{ as_of: string; provider: string; is_fixture: boolean; rows: MarketWatchRow[]; price_rule: string; source_rule: string; portfolio: { accounts?: number; online?: number; error?: string } }>('/api/terminal/market-watch'),
  candles: (symbol: string, tf: string, n = 300) => call<CandleSeries>(`/api/terminal/candles?symbol=${encodeURIComponent(symbol)}&tf=${tf}&n=${n}`),
  decision: (symbol: string) => call<DecisionView>(`/api/terminal/decision?symbol=${encodeURIComponent(symbol)}`),
  signals: (bucket: string, symbol = '') => call<{ as_of: string; bucket: string; ttl_h: number; rule: string; rows: SignalRef[] }>(`/api/terminal/signals?bucket=${bucket}&symbol=${encodeURIComponent(symbol)}`),
  trades: (status: string) => call<{ as_of: string; source: string; rows: TradeRow[] }>(`/api/terminal/trades?status=${status}`),
  performance: () => call<{ as_of: string; stats: Record<string, unknown>; portfolio: Record<string, unknown>; ea_performance: Record<string, unknown>; evidence_law: string }>('/api/terminal/performance'),
  news: (symbol: string) => call<Record<string, unknown>>(`/api/terminal/news?symbol=${encodeURIComponent(symbol)}`),
  sources: () => call<Record<string, unknown>>('/api/terminal/sources'),
  system: () => call<Record<string, unknown>>('/api/terminal/system'),
  ticket: (symbol: string, mode = 'MANUAL') => call<Ticket>('/api/terminal/execution/ticket', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol, mode }) }),
};
