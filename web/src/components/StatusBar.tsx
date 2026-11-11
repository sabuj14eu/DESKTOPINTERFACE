import { useEffect, useState } from 'react';
import type { AccountView, Health } from '../api/types';
import { buildWord } from '../build';
import { fmtTs, money } from '../util';
import { EnvBadge } from './AccountSelector';

/** MT5-style status line: the SELECTED account's broker figures, and the data connection. */
export default function StatusBar({ account, health, healthErr, counts }: { account: AccountView | null; health: Health | null; healthErr: string; counts: { positions: number; orders: number } | null }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 1000); return () => window.clearInterval(t); }, []);
  const up = health?.upstream;
  const ok = !healthErr && !!up?.reachable && !!up?.ok;
  return (
    <div className="statusbar" data-testid="statusbar">
      {account ? <>
        <EnvBadge a={account} />
        <span title={account.field_sources.balance}>Balance: <b className="mono" data-testid="sb-balance">{money(account.balance, account.currency)}</b></span>
        <span title={account.field_sources.equity}>Equity: <b className="mono" data-testid="sb-equity">{money(account.equity, account.currency)}</b></span>
        <span title={account.field_sources.used_margin || 'the reporter did not send this field'}>Margin: <b className="mono">{money(account.used_margin, account.currency)}</b></span>
        <span title={account.field_sources.free_margin}>Free margin: <b className="mono">{money(account.free_margin, account.currency)}</b></span>
        <span title={account.field_sources.margin_level || 'the reporter did not send this field'}>Margin level: <b className="mono">{account.margin_level == null ? 'NOT AVAILABLE' : account.margin_level.toFixed(2) + ' %'}</b></span>
        {counts && <span className="dim">{counts.positions} position(s) · {counts.orders} order(s)</span>}
      </> : <span className="muted">No broker account connected — broker figures are not shown.</span>}
      <span style={{ flex: 1 }} />
      <span className={ok ? 'good' : 'bad'}>● {ok ? 'SignalMesh connected' : healthErr ? 'adapter unreachable' : 'SignalMesh not ready'}</span>
      <span className="dim" data-testid="sb-version">{health?.build ? `${health.build.label} · ${buildWord(health.build)} · ${health.build.environment} · deployed ${fmtTs(health.build.started_at)}` : '—'} · read-only</span>
      <span className="mono dim">{now.toISOString().slice(11, 19)} UTC</span>
    </div>
  );
}
