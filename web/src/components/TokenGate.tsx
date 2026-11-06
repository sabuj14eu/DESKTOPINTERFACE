import { useState } from 'react';
import { setToken } from '../api/client';

export default function TokenGate({ onDone }: { onDone: () => void }) {
  const [v, setV] = useState('');
  return (
    <div className="gate">
      <form onSubmit={(e) => { e.preventDefault(); setToken(v.trim()); onDone(); }}>
        <div className="brand accent" style={{ fontWeight: 800, marginBottom: 10 }}>SIGNALMESH · TERMINAL</div>
        <div className="muted" style={{ marginBottom: 8 }}>This terminal is protected. Enter the access token (SMT_ACCESS_TOKEN).</div>
        <input type="password" value={v} onChange={(e) => setV(e.target.value)} style={{ width: '100%' }} autoFocus placeholder="access token" />
        <button className="on" style={{ marginTop: 10, width: '100%' }} type="submit">Unlock</button>
      </form>
    </div>
  );
}
