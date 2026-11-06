import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Ticket } from '../api/types';

export default function TicketModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [t, setT] = useState<Ticket | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { api.ticket(symbol, 'MANUAL').then(setT).catch((e) => setErr(String(e.message || e))); }, [symbol]);
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: '0 0 8px' }}>Manual order ticket · {symbol}</h3>
        {err && <div className="bad">{err}</div>}
        {t && (t.available ? <>
          <pre className="ticket">{t.text}</pre>
          <div className="warn" style={{ fontSize: 11 }}>{t.note}</div>
          <button className="on" style={{ marginTop: 8 }} onClick={() => { void navigator.clipboard?.writeText(t.text || ''); }}>Copy</button>
        </> : <div className="warn">{t.note}</div>)}
        <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
          <button disabled title="Phase 6">Place via MT5 (disabled)</button>
          <button disabled title="Phase 6">Place via cTrader (disabled)</button>
          <span style={{ flex: 1 }} /><button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
