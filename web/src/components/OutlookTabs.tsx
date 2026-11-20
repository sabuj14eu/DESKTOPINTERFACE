import { api } from '../api/client';
import type { CallLedger, MarketOutlook, OutlookLevel, Scoreboard, TpCell, TpSegment, TurningPoints } from '../outlook';
import { fmtTs, px, usePoll } from '../util';

// OUTLOOK VIEWS (outlook-views-v1) — three Toolbox tabs that show what three SignalMesh pages show (platform 5.210):
// Market Outlook, the Call Ledger and the Turning Point record. DISPLAY ONLY. Every word, level, state, count, rate and
// verdict is the platform's; this file formats and explains, it calculates nothing.
//
// The laws of these three views:
//  * "HAS BEEN", NEVER "WILL". Question one reports what price has done. No arrow, no likelihood figure, no certainty word.
//  * UNKNOWN IS NOT A DIRECTION. UNKNOWN, NO CLEAR TREND and a SERIES FAULT are printed as what they are, in a neutral colour.
//  * UNPROVEN STAYS UNPROVEN. A count of results is printed without green or red; a handful of results is not a trend.
//  * NOTHING TRADES ON THIS. No button, ticket or alert is wired to anything here.
//  * A route the platform does not have reads NOT BUILT — never an empty panel.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** "2026-11-20" (or an ISO time) -> "20 Nov 2026". The platform's own date, re-spelled; nothing is shifted. */
export const day = (iso?: string | null) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? ''); return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : 'NOT AVAILABLE'; };
const one = (v?: number | null) => (v == null ? null : v.toFixed(1));
const share = (v?: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`);
const points = (v?: number | null) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${Math.round(v * 100)} pts`);
const num = (v?: number | null, dp = 3) => (v == null ? '—' : v.toFixed(dp));
// the colour of a measured state: UP and DOWN describe what price HAS done; everything else is neutral
const stateTone = (s?: string) => (s === 'UP' ? 'good' : s === 'DOWN' ? 'bad' : 'muted');

function Foot({ d, rule }: { d: { authority?: string; as_of?: string; read_at?: string; terminal_rule: string }; rule?: string }) {
  return <div className="dim ov-foot">{d.authority ? `${d.authority} · ` : ''}rule {rule || 'NOT AVAILABLE'} · SignalMesh read {fmtTs(d.as_of)} · terminal read {fmtTs(d.read_at)} · shown as SignalMesh sends it; the terminal calculates none of it.</div>;
}
function NotBuilt({ note, testid }: { note?: string; testid: string }) {
  return <div className="note warn" data-testid={`${testid}-not-built`}><b>NOT BUILT</b> — {(note || 'this SignalMesh build does not have this route yet.').replace(/^NOT BUILT — /, '')}</div>;
}
function Dist({ l }: { l: { dist_pct?: number | null; dist_atr?: number | null } }) {
  const a = one(l.dist_pct), b = one(l.dist_atr);
  return <>{a != null ? `${a}% away` : ''}{a != null && b != null ? ' · ' : ''}{b != null ? `${b} daily ATR` : ''}</>;
}
function Level({ l, dec }: { l: OutlookLevel; dec: number }) {
  return <><b className="mono">{px(l.value, dec)}</b> <span className="muted">{l.name}</span> <span className="dim">({day(l.date)} bar · <Dist l={l} />)</span></>;
}

// ------------------------------------------------------------------------------------------------ Market Outlook
export function MarketOutlookView({ d, symbol }: { d: MarketOutlook; symbol: string }) {
  if (d.state === 'NOT_BUILT') return <div data-testid="outlook"><NotBuilt note={d.note} testid="outlook" /></div>;
  const r = d.read; const dec = d.decimals ?? 2; const sym = d.symbol || symbol; const t = d.track;
  const fault = r?.series_fault || '';
  const readable = !!r?.heading && !fault;
  return (
    <div data-testid="outlook" data-symbol={sym}>
      <div className="wall signal"><span className="tag">SIGNALMESH · A STATE, NOT A FORECAST</span> <span data-testid="outlook-plain">{d.plain}</span></div>
      <div className="ov-body">
        <div className="card ov-plain">
          <b>In plain words.</b> This reads the <b>daily</b> chart of {sym} and answers three questions: where price <b>has been</b> heading, which price level matters next, and which daily close would prove the reading wrong.
          It describes what already happened. It is <b>not a forecast and not a signal</b>, and nothing trades on it.
          <div className="dim" style={{ marginTop: 3 }}><b>ATR</b> = the usual size of one daily bar{r?.atr != null ? <> — for {sym} now about <span className="mono">{px(r.atr, dec)}</span></> : null}. <b>Structure</b> = the pattern of the last swing highs and swing lows: HH/HL means higher highs and higher lows, LH/LL means lower highs and lower lows.</div>
        </div>

        <div className="ov-head" data-testid="outlook-head">
          <b style={{ fontSize: 16 }}>{sym}</b> <span className="dim">daily</span>
          {r?.close != null ? <span className="muted"> · last daily close <b className="mono">{px(r.close, dec)}</b> · {day(r.bar_day)} bar · closed {r.bar_age_days ?? 'NOT AVAILABLE'} day(s) ago on the market clock · {r.bars} closed bars read</span>
            : <span className="muted"> · {r?.bars ?? 0} closed daily bars read</span>}
        </div>
        {!r && <div className="note warn" data-testid="outlook-state">NOT AVAILABLE — SignalMesh sent no reading for {sym}.</div>}
        {fault ? <div className="ov-neutral" data-testid="outlook-state"><b>SERIES FAULT</b> — {fault}. <span className="dim">{r?.reason}. Nothing is read from this series.</span></div>
          : r && r.state === 'UNKNOWN' ? <div className="ov-neutral" data-testid="outlook-state"><b>UNKNOWN</b> — {r.reason || 'no reason given'}. <span className="dim">UNKNOWN is not a direction.</span></div> : null}

        {readable && r && <div className="ov-grid">
          <div className="card" data-testid="outlook-q1">
            <h4>1 · Where has price been heading?</h4>
            <div className={`ov-word ${stateTone(r.state)}`} data-testid="outlook-heading">{r.heading!.word}</div>
            <div>{r.heading!.why}.</div>
            <div className="dim" style={{ marginTop: 4 }}>structure <b>{r.structure}</b> (rule {r.structure_rule}){r.swing_highs?.length ? ` · swing highs ${r.swing_highs.map((v) => px(v, dec)).join(' → ')}` : ''}{r.swing_lows?.length ? ` · swing lows ${r.swing_lows.map((v) => px(v, dec)).join(' → ')}` : ''}</div>
            <div className="warn" style={{ marginTop: 4, fontSize: 11 }}>This is what price HAS done, not what it does next. SignalMesh tested whether patterns on these candles predict the next move, and none did (see the Turning Point tab). So this is a state to read, not a forecast.</div>
          </div>
          <div className="card" data-testid="outlook-q2">
            <h4>2 · At which level does it get interesting?</h4>
            {(r.interesting ?? []).length ? r.interesting!.map((i, k) => <div key={k} style={{ marginBottom: 5 }}>
              <span className="pill muted">{i.kind}</span>
              <div><Level l={i.level} dec={dec} /></div>
              <div className="muted">{i.text}.</div>
              {i.then ? <div className="dim">next: <Level l={i.then} dec={dec} /></div> : null}
            </div>) : <div className="muted">No measured level on one or both sides of price in the {r.bars} daily bars read.</div>}
            <div className="dim" style={{ fontSize: 11 }}>Levels are highs and lows of closed daily bars, each named with its bar. They are places to look, not entries.</div>
          </div>
          <div className="card" data-testid="outlook-q3">
            <h4>3 · What would prove this wrong?</h4>
            {r.wrong ? <>
              <div className="ov-word">a daily close {r.wrong.side} <span className="mono">{px(r.wrong.value, dec)}</span></div>
              <div>{r.wrong.text}.</div>
              <div className="dim" style={{ marginTop: 4 }}>{one(r.wrong.dist_pct) != null ? `${one(r.wrong.dist_pct)}% from the last close` : ''}{one(r.wrong.dist_atr) != null ? ` · ${one(r.wrong.dist_atr)} daily ATR` : ''}</div>
            </> : <div className="muted">There is no trend reading to break: the structure is {r.structure}. A direction appears only when two swing highs and two swing lows agree.</div>}
            <div className="dim" style={{ marginTop: 4, fontSize: 11 }}>This reading is from the {day(r.bar_day)} daily bar. It is replaced when a newer daily bar closes.</div>
          </div>
        </div>}

        <div className="card" data-testid="outlook-track">
          <h4>How often has the daily trend continued? — counted, not guessed</h4>
          {!t ? <div className="muted">NOT AVAILABLE — SignalMesh sent no record.</div> : t.fault ? <div className="muted">unavailable — {t.fault}</div> : <>
            <div className="muted">Each time a daily trend reads UP or DOWN, SignalMesh writes down one call by itself: {t.atr_mult ?? 'NOT AVAILABLE'} daily ATR with the trend before the same distance against it. A coin is right half the time.</div>
            <div style={{ marginTop: 4 }}><b data-testid="outlook-track-verdict">{t.board?.verdict ?? 'NOT AVAILABLE'}</b></div>
            <div className="muted" style={{ marginTop: 3 }}>all assets: <Counts b={t.board} /> &nbsp;|&nbsp; {sym}: {t.here?.calls ?? 0} call(s) · {t.here?.hits ?? 0} continued · {t.here?.invalidated ?? 0} turned</div>
            {t.open ? <div className="muted" style={{ marginTop: 3 }} data-testid="outlook-track-open">open on {sym} now: {t.open.direction} from <span className="mono">{px(t.open.ref_price, dec)}</span> — continues at <span className="mono">{px(t.open.target, dec)}</span>, turned at <span className="mono">{px(t.open.invalidation, dec)}</span> (written {fmtTs(t.open.recorded_at)})</div> : null}
            <div className="dim" style={{ marginTop: 3, fontSize: 11 }}>A handful of results is not a verdict: it reads UNPROVEN until enough calls have finished. Every call is in the <b>Call Ledger</b> tab.</div>
          </>}
        </div>

        {readable && r && <div className="ov-grid two">
          <div className="card" data-testid="outlook-above"><h4>Resistance — measured levels above {px(r.close, dec)}</h4>
            {(r.above ?? []).length ? r.above!.map((l, k) => <div key={k} className="ov-level"><Level l={l} dec={dec} /></div>) : <div className="dim">none in the bars read — price is at the top of its range</div>}</div>
          <div className="card" data-testid="outlook-below"><h4>Support — measured levels below {px(r.close, dec)}</h4>
            {(r.below ?? []).length ? r.below!.map((l, k) => <div key={k} className="ov-level"><Level l={l} dec={dec} /></div>) : <div className="dim">none in the bars read — price is at the bottom of its range</div>}</div>
        </div>}

        <div className="dim" style={{ margin: '6px 0 3px' }}><b>Every core asset at a glance</b> — one row each, from its own closed daily bars.</div>
        <table className="grid" data-testid="outlook-overview">
          <thead><tr><th>Asset</th><th>Daily trend so far</th><th>Last daily close</th><th>Nearest level above</th><th>Nearest level below</th><th>Wrong if a daily close is</th></tr></thead>
          <tbody>
            {(d.overview ?? []).map((x) => <tr key={x.symbol} className={x.symbol === sym ? 'sel' : ''} data-row={x.symbol}>
              <td><b>{x.symbol}</b></td>
              <td><b className={stateTone(x.state)}>{x.state}</b>{x.reason ? <div className="dim ov-wrap">{x.reason}</div> : null}</td>
              <td className="mono">{x.close != null ? px(x.close, x.decimals) : '—'}{x.bar_day ? <span className="dim"> · {day(x.bar_day)} bar</span> : null}</td>
              <td>{x.above ? <><span className="mono">{px(x.above.value, x.decimals)}</span> <span className="dim">{x.above.name}</span></> : '—'}</td>
              <td>{x.below ? <><span className="mono">{px(x.below.value, x.decimals)}</span> <span className="dim">{x.below.name}</span></> : '—'}</td>
              <td>{x.wrong ? <>{x.wrong.side} <span className="mono">{px(x.wrong.value, x.decimals)}</span></> : <span className="dim">— no trend to break</span>}</td>
            </tr>)}
            {!(d.overview ?? []).length && <tr><td colSpan={6} className="dim">SignalMesh sent no overview rows</td></tr>}
          </tbody>
        </table>
        <Foot d={d} rule={d.rule} />
      </div>
    </div>
  );
}

/** The scoreboard's counts, in the platform's own numbers. No colour: under the floor a rate is luck, and above it the verdict sentence speaks. */
function Counts({ b }: { b?: Scoreboard }) {
  if (!b) return <>NOT AVAILABLE</>;
  return <>{b.calls ?? 0} call(s) · {b.pending ?? 0} open · {b.hits ?? 0} continued · {b.invalidated ?? 0} turned · {b.expired ?? 0} expired{b.both ? ` · ${b.both} reached both levels in one bar` : ''}{b.resolved ? ` · continued ${share(b.hit_rate)} of ${b.resolved} finished` : ''}</>;
}

export function MarketOutlookTab({ symbol, pollMs }: { symbol: string; pollMs: number }) {
  const { data, error } = usePoll(() => api.outlook(symbol), Math.max(pollMs * 4, 60_000), [symbol]);
  if (error) return <div className="note bad" data-testid="outlook-error">Market Outlook could not be read from SignalMesh: {error}</div>;
  if (!data) return <div className="note">loading Market Outlook…</div>;
  return <MarketOutlookView d={data} symbol={symbol} />;
}

// ------------------------------------------------------------------------------------------------ Call Ledger
export function CallLedgerView({ d }: { d: CallLedger }) {
  if (d.state === 'NOT_BUILT') return <div data-testid="ledger"><NotBuilt note={d.note} testid="ledger" /></div>;
  const rows = d.rows ?? []; const b = d.board;
  return (
    <div data-testid="ledger">
      <div className="wall signal"><span className="tag">SIGNALMESH · ITS OWN CALLS, COUNTED</span> <span data-testid="ledger-plain">{d.plain}</span></div>
      <div className="ov-body">
        <div className="card ov-plain">
          <b>In plain words.</b> Nobody types these. When an asset's daily trend reads UP or DOWN, SignalMesh writes down one call by itself, <b>before</b> anyone knows how it ends. Later the candles decide whether it was right.
          It is a way to count honestly. It is <b>not a signal</b> and nothing trades on it.
          <div className="dim" style={{ marginTop: 3 }}><b>BULLISH</b> = the call says price rises first; <b>BEARISH</b> = falls first. <b>Target</b> = the price that makes the call right. <b>Invalidation</b> = the price that proves it wrong.
            <b> R</b> = the result counted in units of the distance to the invalidation: +1.00 means the target was reached, −1.00 means the invalidation was reached.</div>
          {d.definition ? <div className="dim" style={{ marginTop: 3 }}>The rule, in SignalMesh's words: {d.definition}.</div> : null}
        </div>

        <div className="card" data-testid="ledger-board">
          <h4>Scoreboard — {d.analyst || 'the system'} · all assets together</h4>
          <div><b data-testid="ledger-verdict">{b?.verdict ?? 'NOT AVAILABLE'}</b></div>
          <div className="muted" style={{ marginTop: 3 }} data-testid="ledger-counts"><Counts b={b} /></div>
          <div className="dim" style={{ marginTop: 3, fontSize: 11 }}>Both distances are equal, so about half of the calls continue by chance. A few results say nothing in either direction; the counts are shown without green or red for that reason.</div>
        </div>

        <table className="grid" data-testid="ledger-rows">
          <thead><tr><th>Asset</th><th>Call</th><th>Start price</th><th>Target</th><th>Invalidation</th><th>Written (UTC)</th><th>Expires (UTC)</th><th>Outcome</th><th>Decided (UTC)</th><th title="result in units of the distance to the invalidation">R</th><th>Why it was written</th></tr></thead>
          <tbody>
            {rows.map((x) => <tr key={x.id}>
              <td><b>{x.symbol}</b></td><td>{x.direction}</td>
              <td className="mono">{px(x.ref_price, x.decimals)}</td><td className="mono">{px(x.target, x.decimals)}</td><td className="mono">{px(x.invalidation, x.decimals)}</td>
              <td className="dim">{fmtTs(x.recorded_at)}</td><td className="dim">{fmtTs(x.expires_at)}</td>
              <td><span className="pill muted">{x.outcome}</span>{x.outcome !== 'PENDING' && x.stored === false ? <span className="dim" title="SignalMesh worked this outcome out from the candles on this read; its sweeper has not stored it on the row yet"> · not stored yet</span> : null}</td>
              <td className="dim">{x.outcome_at ? fmtTs(x.outcome_at) : '—'}</td>
              <td className="mono">{x.r == null ? '—' : `${x.r >= 0 ? '+' : ''}${x.r.toFixed(2)}`}</td>
              <td className="dim ov-wrap">{x.why || '—'}</td>
            </tr>)}
            {!rows.length && <tr><td colSpan={11} className="dim">No call is written yet. A call is written only when an asset's daily trend reads UP or DOWN — no call is not a failed call.</td></tr>}
          </tbody>
        </table>
        <Foot d={d} rule={d.rule ? `${d.rule}${d.scoring_rule ? ` (scored by ${d.scoring_rule})` : ''}` : undefined} />
      </div>
    </div>
  );
}

export function CallLedgerTab({ pollMs }: { pollMs: number }) {
  const { data, error } = usePoll(() => api.callLedger(), Math.max(pollMs * 4, 60_000));
  if (error) return <div className="note bad" data-testid="ledger-error">The Call Ledger could not be read from SignalMesh: {error}</div>;
  if (!data) return <div className="note">loading the Call Ledger…</div>;
  return <CallLedgerView d={data} />;
}

// ------------------------------------------------------------------------------------------------ Turning Point record
function Segment({ name, seg, cell }: { name: string; seg: TpSegment; cell: TpCell }) {
  const dec = cell.decimals; const ex = seg.example;
  return (
    <div style={{ marginTop: 6 }}>
      <div className="muted"><b>{name}</b> · {seg.points} point(s), {seg.independent} independent (their outcome windows do not overlap) · bars replayed {day(seg.first_as_of)} … {day(seg.last_as_of)}</div>
      {ex ? <div className="ov-example" data-testid="tp-example">Which prices? On this box's newest tested moment ({fmtTs(ex.as_of)}): price was <b className="mono">{px(ex.price, dec)}</b> and one ATR was <b className="mono">{px(ex.atr, dec)}</b>, so the question was
        "does it reach <b className="mono">{px(ex.down_at, dec)}</b> first, or <b className="mono">{px(ex.up_at, dec)}</b> first?"</div> : null}
      <table className="grid" style={{ marginTop: 3 }}>
        <thead><tr><th>The model said</th><th>Times</th><th>Came true</th><th title="how often that outcome happens anyway, whatever the model says">Happens anyway</th><th title="came true minus happens anyway">Lift</th><th title="the lift that chance alone can produce with this many points">Noise floor</th><th>Verdict</th></tr></thead>
        <tbody>{Object.entries(seg.words ?? {}).map(([w, x]) => <tr key={w}>
          <td><b>{w}</b></td><td className="mono">{x.n}</td><td className="mono">{x.hits} ({share(x.hit_rate)})</td><td className="mono">{share(x.base_rate)}</td>
          <td className="mono">{points(x.lift)}</td><td className="mono">{points(x.lift_needed)}</td><td className="ov-wrap">{x.verdict}</td></tr>)}</tbody>
      </table>
      {seg.base ? <div className="dim" style={{ marginTop: 2 }}>what happened over these points: down first {share(seg.base.down)} · up first {share(seg.base.up)} · neither {share(seg.base.none)}
        {seg.brier_down != null ? <> · error of the model's stated odds (Brier score, lower is better): down {num(seg.brier_down)} against {num(seg.brier_ref_down)} for always answering the usual rate · up {num(seg.brier_up)} against {num(seg.brier_ref_up)}</> : null}</div> : null}
    </div>
  );
}

export function TurningPointView({ d }: { d: TurningPoints }) {
  if (d.state === 'NOT_BUILT') return <div data-testid="turning-points"><NotBuilt note={d.note} testid="turning-points" /></div>;
  const o = d.overall, g = d.gate, q = d.question ?? {}, cells = d.cells ?? [];
  return (
    <div data-testid="turning-points">
      <div className="wall signal"><span className="tag">SIGNALMESH · AN OLD TEST'S SCORE</span> <span data-testid="tp-plain">{d.plain}</span></div>
      <div className="ov-body">
        <div className="card ov-plain">
          <b>In plain words.</b> This is <b>not about today's price</b>. It is the score of an old exam. A computer model was shown hundreds of moments from the past and asked one question each time:
          <b> "From here, will price first FALL by one ATR, or first RISE by one ATR?"</b> (ATR = the usual size of one bar on that chart; each box below shows what it was in price.)
          <div className="dim" style={{ marginTop: 3 }}>
            <b>{d.words?.top ?? 'PROBABLE TOP'}</b> = the model said "it falls first". <b>{d.words?.bottom ?? 'PROBABLE BOTTOM'}</b> = "it rises first".
            <b> Came true</b> = how often the model was right. <b>Happens anyway</b> = how often price did that with no model at all.
            If "came true" is not clearly higher than "happens anyway", the model knows nothing. That is what NO ROBUST EDGE means, and it is why no forecast card was built.</div>
        </div>

        <div className="card" data-testid="tp-overall">
          <h4>The result</h4>
          <div className="ov-word" data-testid="tp-word">{o?.word ?? 'NOT AVAILABLE'}</div>
          <div className="muted">{o?.why}</div>
          <div className="dim" style={{ marginTop: 3, fontSize: 11 }}>{d.total_rows ?? 0} stored row(s): {d.skill_rows ?? 0} from the test · {d.shadow_rows ?? 0} live or shadow{d.fake_rows ? ` · ${d.fake_rows} from a test sampler (never counted)` : ''}
            {' '}· question {d.config_hash}: which is touched first within {q.horizon_bars} bars, the price now minus {q.atr_mult} ATR or plus {q.atr_mult} ATR, judged on {q.touch_on === 'close' ? 'closes' : q.touch_on}; the model says a word only at P ≥ {q.threshold}</div>
        </div>

        <div className="card" data-testid="tp-gate">
          <h4>Why there is no forecast card</h4>
          <div><b>{g?.why ?? 'NOT AVAILABLE'}</b></div>
          <div className="muted" style={{ marginTop: 3 }}>This tab holds <b>no reading for today</b>: every row behind it is a replayed bar from history, scored against what price did next. A card that shows a direction opens only when every step below reads ✓.</div>
          <ul className="plain" style={{ marginTop: 4 }}>{(g?.steps ?? []).map((s) => <li key={s.name}><b>{s.passed ? '✓' : '✗'}</b> {s.name}{s.note ? <span className="dim"> — {s.note}</span> : null}</li>)}</ul>
        </div>

        <div className="dim" style={{ margin: '6px 0 3px' }}><b>Cells examined: {cells.length}</b> — one cell is one asset, one timeframe and one model. Cells are never added together; with {cells.length} examined, any "best" cell is the best of {cells.length}.</div>
        {!cells.length && <div className="note">No test row is stored. Nothing was tested, so nothing is known in either direction — an empty table is not a clean result.</div>}
        {cells.map((c) => <div className="card" key={`${c.symbol}|${c.tf}|${c.model_revision}`} data-testid="tp-cell" data-cell={`${c.symbol}|${c.tf}`}>
          <div><b style={{ fontSize: 14 }}>{c.symbol} · {c.tf}</b> &nbsp;<b>{c.word}</b> <span className="dim">· model {c.model_repo || '—'} @ {(c.model_revision ?? '').slice(0, 16)} · {c.rows ?? 0} row(s) · tested {day(c.computed_from)} · holdout {c.holdout_state}</span></div>
          {c.candidate_words?.length && c.holdout ? <div className="muted" style={{ marginTop: 3 }}>On the search part <b>{c.candidate_words.join(' and ')}</b> cleared the noise floor. On the holdout — data the search never saw, used once —
            {c.held_words?.length ? <> <b>{c.held_words.join(' and ')}</b> cleared it again. That opens shadow calls, not a card.</> : <> it did <b>not</b>. The candidate is closed; a holdout is never run twice.</>}</div> : null}
          {c.readable === false ? <div className="muted" style={{ marginTop: 3 }}>These rows answer another question (config {c.config_hash}, not this build's {d.config_hash}). They are counted and kept, and not re-read under a rule they were not made for.</div> : null}
          {c.search ? <Segment name="SEARCH — the older part of history, where the model was examined" seg={c.search} cell={c} /> : null}
          {c.holdout ? <Segment name="HOLDOUT — the newest part, kept aside and used once" seg={c.holdout} cell={c} /> : null}
        </div>)}
        <Foot d={d} rule={d.rule} />
      </div>
    </div>
  );
}

export function TurningPointTab({ pollMs }: { pollMs: number }) {
  const { data, error } = usePoll(() => api.turningPoints(), Math.max(pollMs * 20, 300_000));
  if (error) return <div className="note bad" data-testid="turning-points-error">The Turning Point record could not be read from SignalMesh: {error}</div>;
  if (!data) return <div className="note">loading the Turning Point record…</div>;
  return <TurningPointView d={data} />;
}
