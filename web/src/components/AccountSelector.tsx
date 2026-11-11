import { useState } from 'react';
import type { AccountView, Accounts } from '../api/types';
import { fmtTs, orNA } from '../util';

export const envTone = (e: string) => (e === 'LIVE' ? 'live' : e === 'DEMO' ? 'demo' : 'unk');
export const typeLabel = (a: AccountView) => (a.combined ? `${a.accounts_in_total} MT5 ACCOUNTS · COMBINED` : `${a.platform === 'CTRADER' ? 'cTrader' : 'MT5'} ${a.environment === 'UNKNOWN' ? '· TYPE UNKNOWN' : a.environment === 'LIVE' ? 'Live' : 'Demo'}`);
export function EnvBadge({ a }: { a: AccountView }) {
  return <span className={`env ${a.combined ? 'unk' : envTone(a.environment)}`} title={a.combined ? 'a total over several accounts — not one account' : a.field_sources.environment || 'the broker row does not say DEMO or LIVE'}>{a.combined ? 'COMBINED' : a.environment === 'UNKNOWN' ? 'DEMO/LIVE UNKNOWN' : a.environment}</span>;
}

/** The account in the toolbar. Lists ONLY accounts that are reporting right now; one is selected
 *  at a time and every broker figure on screen belongs to it. */
export default function AccountSelector({ data, error, selected, onSelect }: { data: Accounts | null; error: string; selected: AccountView | null; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const list = data?.accounts ?? [];
  const connectedPlatforms = new Set(list.map((a) => a.platform));
  return (
    <span className="acct menu-host" data-testid="account-selector">
      <button className="acct-btn" onClick={() => setOpen((v) => !v)} aria-haspopup="listbox" aria-expanded={open} title="broker account — only genuinely connected accounts are listed">
        {selected ? <><EnvBadge a={selected} /> <b>{selected.platform === 'CTRADER' ? 'cTrader' : 'MT5'}</b> <span className="mono">{selected.login_masked ?? (selected.combined ? 'all accounts' : 'id n/a')}</span>
          <span className="dim hide-s">{selected.server ? ` · ${selected.server}` : ''}</span> <span className="good">●</span></>
          : <span className={error ? 'bad' : 'muted'}>{error ? 'accounts unavailable' : data ? 'NO ACCOUNT CONNECTED' : 'accounts…'}</span>} ▾
      </button>
      {open && <div className="menu acct-menu" role="listbox" onMouseLeave={() => setOpen(false)}>
        <div className="menu-title">Connected accounts</div>
        {list.map((a) => (
          <div key={a.id} role="option" aria-selected={a.id === selected?.id} className={'acct-row' + (a.id === selected?.id ? ' sel' : '')} data-testid="account-option" onClick={() => { onSelect(a.id); setOpen(false); }}>
            <div><EnvBadge a={a} /> <b>{typeLabel(a)}</b> <span className="good" style={{ float: 'right' }}>● {a.connection}</span></div>
            <div className="kv">
              <span className="k">Broker</span><span>{orNA(a.broker)}</span>
              <span className="k">Account</span><span className="mono">{orNA(a.login_masked)}</span>
              <span className="k">Server</span><span>{orNA(a.server)}</span>
              <span className="k">Heartbeat</span><span>{a.last_heartbeat ? fmtTs(a.last_heartbeat) : 'NOT AVAILABLE'}</span>
            </div>
          </div>))}
        {!list.length && <div className="note">{error || 'No broker account is reporting to SignalMesh right now.'}</div>}
        {(data?.disconnected.length ?? 0) > 0 && <div className="note dim">{data!.disconnected.length} known account(s) not connected — listed under Account Information, not selectable.</div>}
        <div className="menu-title">Supported account types</div>
        <div className="note">{(data?.supported_types ?? ['MT5 Demo', 'MT5 Live', 'cTrader Demo', 'cTrader Live']).map((t) => {
          // lit ONLY when a connected account's own broker row says it is that type
          const on = list.some((a) => !a.combined && a.environment !== 'UNKNOWN' && typeLabel(a) === t);
          return <span key={t} className={on ? 'good' : 'dim'} style={{ marginRight: 10 }}>{on ? '●' : '○'} {t}</span>; })}
          {list.some((a) => a.platform === 'MT5' && (a.combined || a.environment === 'UNKNOWN')) && <div className="warn" style={{ marginTop: 4 }} data-testid="type-unknown">MT5 connected, but SignalMesh does not say whether an account is DEMO or LIVE — neither is marked.</div>}
          {!connectedPlatforms.has('CTRADER') && <div className="dim" style={{ marginTop: 4 }}>cTrader: not connected (no cTrader account reports to SignalMesh).</div>}
        </div>
        {data && <div className="note dim" title={data.rule}>{data.note}</div>}
      </div>}
    </span>
  );
}
