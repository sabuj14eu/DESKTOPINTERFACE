import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { BuildIdentity, Release } from '../api/types';
import { UI_BUILD, buildWord, uiMismatch } from '../build';
import { fmtTs } from '../util';

const envTone = (e: string) => (e === 'PRODUCTION' ? 'prod' : e === 'STAGING' ? 'stage' : 'local');

/** WHICH TERMINAL IS RUNNING. Everything shown comes from the build (see adapter build.py and the
 *  Dockerfile's meta stage); nothing is typed here. Click for the details and the release history. */
export default function VersionBadge({ build, compact }: { build: BuildIdentity | undefined; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const [rel, setRel] = useState<Release[] | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { if (open && !rel) api.version().then((v) => setRel(v.releases)).catch((e) => setErr(String(e.message || e))); }, [open, rel]);
  useEffect(() => { if (!open) return; const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } }; window.addEventListener('keydown', k, true); return () => window.removeEventListener('keydown', k, true); }, [open]);
  const b = build;
  const mismatch = uiMismatch(b);
  return (
    <>
      <button className="ver" onClick={() => setOpen(true)} data-testid="version-badge" title="which terminal is running — click for build details and release history">
        <span className="brand">SIGNALMESH TERMINAL</span><span className="sep">|</span><b data-testid="version">{b ? b.label : '…'}</b>
        {b && <span className={`envtag ${envTone(b.environment)}`} data-testid="environment">{b.environment}</span>}
        {b && b.data !== `${b.environment} DATA` && <span className="envtag fixture" data-testid="data-kind">{b.data}</span>}
        {b && !compact && <span className="mono dim" data-testid="build-commit">{buildWord(b)}</span>}
        {mismatch && <span className="envtag fixture">RELOAD — old page</span>}
      </button>
      {open && <div className="modal-bg" onClick={() => setOpen(false)}>
        <div className="modal about" onClick={(e) => e.stopPropagation()} data-testid="about">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><h3 style={{ margin: 0 }}>SignalMesh Terminal {b?.label}</h3><span style={{ flex: 1 }} /><button onClick={() => setOpen(false)}>✕</button></div>
          {b && <div className="kv wide" style={{ marginTop: 10 }}>
            <span className="k">Terminal version</span><span><b>{b.version}</b></span>
            <span className="k">Build number</span><span className="mono">{b.build ?? (b.shallow ? 'not available (shallow checkout)' : 'UNKNOWN')}</span>
            <span className="k">Git commit</span><span className="mono">{b.commit}{b.dirty ? <b className="warn"> + uncommitted local changes</b> : ''}{b.commit_time ? <span className="dim"> · committed {fmtTs(b.commit_time)}</span> : null}</span>
            <span className="k">Environment</span><span><span className={`envtag ${envTone(b.environment)}`}>{b.environment}</span></span>
            <span className="k">Data on screen</span><span><b className={b.data === 'TEST FIXTURES' ? 'warn' : ''}>{b.data}</b></span>
            <span className="k">Built</span><span>{b.built_at ? fmtTs(b.built_at) : 'UNKNOWN (not an image build)'}</span>
            <span className="k">Last deployment</span><span>{fmtTs(b.started_at)} <span className="dim">(this server process started)</span></span>
            <span className="k">UI in this browser</span><span className={mismatch ? 'bad' : ''}><span className="mono">V{UI_BUILD.version} · {buildWord(UI_BUILD)}</span>{mismatch ? ' — DIFFERENT from the server: reload the page (Ctrl+Shift+R)' : ' — same build as the server'}</span>
            <span className="k">Read from</span><span className="dim">{b.source}</span>
          </div>}
          <h4>Release history</h4>
          {err && <div className="bad">{err}</div>}
          {!rel && !err && <div className="dim">loading…</div>}
          <div className="releases">{(rel ?? []).map((r) => (
            <div key={r.version} className="release"><b>{r.version}</b> <span className="dim">{r.date}</span>{r.version === b?.version ? <span className="pill good" style={{ marginLeft: 6 }}>running</span> : null}
              {([['Changes', r.changes], ['Fixed bugs', r.fixed], ['Outstanding issues', r.outstanding]] as const).map(([t, items]) => items.length > 0 && (
                <div key={t}><div className="rel-h">{t}</div><ul className="plain">{items.map((x, i) => <li key={i} className={t === 'Outstanding issues' ? 'warn' : ''}>{x}</li>)}</ul></div>))}
            </div>))}</div>
        </div>
      </div>}
    </>
  );
}
