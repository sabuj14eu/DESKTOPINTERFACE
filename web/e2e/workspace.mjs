// TERMINAL V2 ACCEPTANCE, in the real UI (fixture adapter or a real one):
//   1 full-screen chart · 2 hide/restore both side panels · 3 resize by dragging · 4 layout survives a reload
//   5 open a signal and read its originating engine and strategy · 6 switch between two connected accounts
//   7/8 the account figures, positions and orders on screen are the selected account's own
//   9 a signal is never shown as a broker execution · phone layout: chart + bottom navigation
//   TERM_URL=http://127.0.0.1:8090 node e2e/workspace.mjs      SHOTS=dir also writes screenshots
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = (process.env.TERM_URL || 'http://127.0.0.1:8090').replace(/\/$/, '');
const headers = process.env.TERM_KEY ? { 'X-Terminal-Key': process.env.TERM_KEY } : {};
const SHOTS = process.env.SHOTS || '';
const api = async (p) => (await fetch(BASE + p, { headers })).json();
let fails = 0;
const check = (label, ok, detail = '') => { console.log(`  ${ok ? 'OK  ' : 'FAIL'} ${label}${detail ? ' — ' + detail : ''}`); if (!ok) fails++; };
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1 });
const pg = await ctx.newPage();
if (process.env.TERM_KEY) await pg.setExtraHTTPHeaders(headers);
const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` }); };
const ready = (page) => page.waitForFunction(() => window.__smtChart?.bars() > 0 && window.__smtChart?.range() != null, null, { timeout: 30000 });
const W = () => pg.evaluate(() => ({ chart: window.__smtChart.paneWidth(), h: window.__smtChart.paneHeight(), win: window.innerWidth, winH: window.innerHeight }));
const box = async (id) => (await pg.getByTestId(id).count()) ? await pg.getByTestId(id).boundingBox() : null;

await pg.goto(BASE + '/', { waitUntil: 'networkidle' });
await pg.evaluate(() => localStorage.removeItem('smt_workspace_v2'));
await pg.reload({ waitUntil: 'networkidle' });
await ready(pg);
await shot(pg, '01-default-workspace');
check('no indicator is drawn by default (moving averages stay off until switched on)', (await pg.evaluate(() => window.__smtChart.studies().length)) === 0);

console.log('== version identification ==');
const hb = (await api('/api/terminal/health')).build;
check('toolbar shows the running version', (await pg.getByTestId('version').innerText()) === `V${hb.version}`, await pg.getByTestId('version').innerText());
check('toolbar shows the environment', (await pg.getByTestId('environment').innerText()) === hb.environment, hb.environment);
check('toolbar shows build number and git commit of the server build', (await pg.getByTestId('build-commit').innerText()).includes(hb.commit), await pg.getByTestId('build-commit').innerText());
check('fixture data is named in the toolbar when it is fixtures', hb.data !== 'TEST FIXTURES' || (await pg.getByTestId('data-kind').innerText()) === 'TEST FIXTURES');
check('the page in the browser is the same build as the server', !(await pg.getByTestId('version-badge').innerText()).includes('RELOAD'));
await pg.getByTestId('version-badge').click(); await pg.getByTestId('about').waitFor();
check('release history lists the running version first', (await pg.locator('.release').first().innerText()).startsWith(hb.version));
await pg.keyboard.press('Escape'); await pg.getByTestId('about').waitFor({ state: 'detached' });

console.log('== live forming bar (display only) ==');
const lv = await api('/api/terminal/live?symbol=GOLD&tf=15m');
if (lv.state === 'LIVE' || lv.state === 'FROM_1M') {
  await pg.waitForFunction(() => window.__smtChart.liveBars() > 0, null, { timeout: 15000 });
  const closedN = await pg.evaluate(() => window.__smtChart.bars());
  const a1 = await pg.evaluate(() => window.__smtChart.lastValue());
  check('a forming bar is drawn after the newest closed bar', a1.time > (await api('/api/terminal/candles?symbol=GOLD&tf=15m&n=10')).candles.at(-1).time, JSON.stringify(a1));
  await pg.waitForFunction((c) => window.__smtChart.lastValue()?.close !== c, a1.close, { timeout: 15000 });
  check('and it moves between polls', true);
  check('the closed series is unchanged by it', (await pg.evaluate(() => window.__smtChart.bars())) === closedN);
  check('the chart says which source the forming bar has', (await pg.getByTestId('live-state').innerText()).includes(lv.state === 'LIVE' ? 'LIVE BAR' : 'from 1m'));
} else console.log(`  NOTE no forming bar available here (${lv.state}) — live checks skipped`);

console.log('== brain plan and desk lanes ==');
const dv = await api(`/api/terminal/decision?symbol=${await pg.locator('.pricebox').getAttribute('data-symbol')}`);
await pg.getByTestId('desk-lanes').waitFor();
check('Latest brain plan shows the engine\'s plan state', (await pg.getByTestId('brain-plan').innerText()).toUpperCase().includes(dv.brain_plan.state.replace('_', ' ')));
check('one row per desk lane, marked PAPER', (await pg.locator('[data-testid=desk-lanes] .lane').count()) === dv.lanes.length && (await pg.getByTestId('desk-lanes').innerText()).includes('PAPER'), `${dv.lanes.length} lanes`);

console.log('== 2. hide and restore both side panels ==');
const w0 = await W();
await pg.getByTestId('toggle-left').click(); await pg.getByTestId('toggle-right').click(); await pg.waitForTimeout(300);
const w1 = await W();
check('both side panels hidden', !(await box('panel-left')) && !(await box('panel-right')));
check('chart takes the full width when both are hidden', w1.chart >= w1.win - 4, `chart ${w1.chart}px of ${w1.win}px (was ${w0.chart}px)`);
await shot(pg, '02-side-panels-hidden');
await pg.getByTestId('toggle-left').click(); await pg.getByTestId('toggle-right').click(); await pg.waitForTimeout(300);
check('both side panels restored at their widths', (await box('panel-left'))?.width === 300 && (await box('panel-right'))?.width === 330);
check('chart back to its previous width', (await W()).chart === w0.chart);

console.log('== 1. full-screen chart ==');
await pg.getByTestId('toggle-full').click(); await pg.waitForTimeout(300);
const wf = await W();
check('every panel hidden in full-screen', !(await box('panel-left')) && !(await box('panel-right')) && !(await box('panel-bottom')));
check('chart fills the window', wf.chart >= wf.win - 4 && wf.h >= wf.winH * 0.82, `${wf.chart}x${wf.h} of ${wf.win}x${wf.winH}`);
check('chart still has its data and newest bar in view', await pg.evaluate(() => { const h = window.__smtChart; const y = h.lastBarY(); return h.bars() > 0 && y != null && y > 0 && y < h.paneHeight(); }));
await shot(pg, '03-full-screen-chart');
await pg.keyboard.press('Escape'); await pg.waitForTimeout(300);
check('Esc restores the panels', !!(await box('panel-left')) && !!(await box('panel-right')) && !!(await box('panel-bottom')));

console.log('== 3. resize panels by dragging their borders ==');
const drag = async (id, dx, dy) => { const s = await pg.getByTestId(id).boundingBox(); const x = s.x + s.width / 2, y = s.y + s.height / 2;
  await pg.mouse.move(x, y); await pg.mouse.down(); await pg.mouse.move(x + dx / 2, y + dy / 2, { steps: 4 }); await pg.mouse.move(x + dx, y + dy, { steps: 4 }); await pg.mouse.up(); await pg.waitForTimeout(200); };
await drag('split-market-watch-width', 120, 0);
await drag('split-decision-panel-width', -90, 0);
await drag('split-toolbox-height', 0, -110);
const L = (await box('panel-left')).width, R = (await box('panel-right')).width, Bh = (await box('panel-bottom')).height;
check('Market Watch widened by the drag', Math.abs(L - 420) <= 3, `${L}px`);
check('Decision panel widened independently', Math.abs(R - 420) <= 3, `${R}px`);
check('Toolbox made taller', Math.abs(Bh - 360) <= 3, `${Bh}px`);
await shot(pg, '04-resized-panels');

console.log('== 4. workspace persists across a reload ==');
await pg.getByTestId('toggle-right').click();
await pg.getByRole('tab', { name: /Account Information/ }).click();
await pg.reload({ waitUntil: 'networkidle' }); await ready(pg);
check('widths and heights restored', (await box('panel-left'))?.width === L && (await box('panel-bottom'))?.height === Bh, `left ${(await box('panel-left'))?.width} bottom ${(await box('panel-bottom'))?.height}`);
check('hidden panel stays hidden', !(await box('panel-right')));
check('selected Toolbox tab restored', (await pg.getByRole('tab', { selected: true }).innerText()).startsWith('Account Information'));
await pg.getByTestId('toggle-right').click(); await pg.waitForTimeout(200);
check('re-shown panel kept its dragged width', (await box('panel-right'))?.width === R);
await pg.getByTestId('reset-layout').click(); await pg.waitForTimeout(300);
check('reset layout restores the defaults', (await box('panel-left'))?.width === 300 && (await box('panel-right'))?.width === 330 && (await box('panel-bottom'))?.height === 250);

console.log('== 5. open a signal: originating engine and strategy ==');
const all = await api('/api/terminal/signals?bucket=all');
const sig = all.rows.find((s) => s.bucket === 'EXPIRED') || all.rows[0];
const det = await api(`/api/terminal/signals/${encodeURIComponent(sig.signal_id)}`);
await pg.getByRole('tab', { name: /Trade History/ }).click();
await pg.getByRole('button', { name: /expired & rejected signals/ }).click();
await pg.locator('[data-testid=signal-table] tr.row', { hasText: sig.signal_id }).first().click();
await pg.getByTestId('signal-headline').waitFor();
const field = async (k) => (await pg.locator(`[data-testid=signal-origin] [data-field=${k}]`).innerText()).trim();
check('signal id shown', (await field('signal_id')).startsWith(sig.signal_id));
check('originating engine shown with its source field', (await field('originating_engine')).startsWith(String(det.origin.originating_engine.value)), await field('originating_engine'));
check('strategy name is the engine\'s word or UNKNOWN, never invented', (await field('strategy_name')).startsWith(String(det.origin.strategy_name.value)), await field('strategy_name'));
check('strategy version is the engine\'s word or UNKNOWN', (await field('strategy_version')).startsWith(String(det.origin.strategy_version.value)), await field('strategy_version'));
console.log('== 9. a signal is not shown as a broker execution ==');
const head = await pg.getByTestId('signal-headline').innerText();
check('headline says recommendation unless a broker row is linked', det.is_broker_execution ? head.includes('BROKER EXECUTION') : head.includes('RECOMMENDATION') && !head.includes('BROKER EXECUTION'), head.replace(/\n/g, ' | '));
const stages = await pg.$$eval('ol.stages li', (els) => Object.fromEntries(els.map((e) => [e.dataset.stage, e.dataset.state])));
check('five stages kept apart (generated / approved / submitted / filled / closed)', ['generated', 'council', 'user', 'submitted', 'filled', 'closed'].every((k) => k in stages), JSON.stringify(stages));
check('lifecycle states equal the adapter\'s', JSON.stringify(stages) === JSON.stringify(Object.fromEntries(det.lifecycle.map((s) => [s.key, s.state]))));
await shot(pg, '05-signal-information');
await pg.keyboard.press('Escape');
await pg.getByRole('tab', { name: /Active Signals/ }).click();
check('Active Signals is labelled as recommendations, not broker orders', (await pg.locator('.wall.signal').first().innerText()).includes('Not broker orders'));
await pg.getByRole('tab', { name: /Open Positions/ }).click();
check('Open Positions is labelled as broker records, not signals', (await pg.locator('.wall.broker').first().innerText()).includes('BROKER'));

console.log('== 6/7/8. accounts: only connected ones, switch, figures are the selected account\'s ==');
const acc = await api('/api/terminal/accounts');
const money = (v) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
if (!acc.accounts.length) { console.log('  NOTE no broker account connected — account checks skipped'); }
else {
  await pg.getByRole('tab', { name: /Account Information/ }).click();
  for (const a of acc.accounts.slice(0, 2)) {
    await pg.getByTestId('account-selector').locator('button.acct-btn').click();
    check(`selector lists exactly the ${acc.accounts.length} connected account(s)`, (await pg.getByTestId('account-option').count()) === acc.accounts.length);
    await pg.getByTestId('account-option').nth(acc.accounts.indexOf(a)).click();
    const d = await api(`/api/terminal/account?id=${a.id}`);
    await pg.waitForFunction((t) => document.querySelector('[data-testid=sb-balance]')?.textContent?.startsWith(t), a.balance == null ? 'NOT AVAILABLE' : money(a.balance), { timeout: 15000 });
    const eq = await pg.getByTestId('sb-equity').innerText();
    check(`${a.environment} ${a.login_masked ?? 'account'}: balance and equity on screen are this account's`, eq.startsWith(a.equity == null ? 'NOT AVAILABLE' : money(a.equity)), `equity ${eq}`);
    const info = pg.getByTestId('account-info');
    for (const k of ['used_margin', 'margin_level']) if (a[k] == null) check(`${a.environment}: ${k} not reported -> NOT AVAILABLE (not calculated)`, (await info.locator(`[data-field=${k}] .v`).innerText()) === 'NOT AVAILABLE');
    check(`${a.environment}: DEMO/LIVE badge matches the broker row`, (await pg.getByTestId('statusbar').locator('.env').innerText()).includes(a.environment === 'UNKNOWN' ? 'UNKNOWN' : a.environment));
    await pg.getByRole('tab', { name: /Open Positions/ }).click();
    await pg.waitForFunction((n) => document.querySelectorAll('[data-testid=broker-positions] tbody tr td.mono').length >= 0 && !document.querySelector('[data-testid=broker-positions]')?.textContent?.includes('loading'), d.positions.length);
    const rows = await pg.$$eval('[data-testid=broker-positions] tbody tr', (els) => els.map((e) => e.children[1]?.textContent).filter((x) => x && x.trim()));
    check(`${a.environment}: open positions are this account's only`, JSON.stringify(rows) === JSON.stringify(d.positions.map((p) => p.symbol)), JSON.stringify(rows));
    await pg.getByRole('tab', { name: /Pending Orders/ }).click();
    const orows = await pg.$$eval('[data-testid=broker-orders] tbody tr', (els) => els.map((e) => e.children[1]?.textContent).filter((x) => x && x.trim()));
    check(`${a.environment}: pending orders are this account's only`, JSON.stringify(orows) === JSON.stringify(d.orders.map((p) => p.symbol)), JSON.stringify(orows));
    await pg.getByRole('tab', { name: /Account Information/ }).click();
    await shot(pg, `06-account-${a.environment.toLowerCase()}-${acc.accounts.indexOf(a)}`);
  }
  if (acc.accounts.length < 2) console.log('  NOTE only one connected account — switching between two could not be demonstrated here');
}

console.log('== Smart Money Concepts overlays (display only) ==');
const smc = () => pg.evaluate(() => window.__smtChart.smc());
const FEATS = ['sr', 'fvg', 'bos', 'choch', 'ob', 'liq', 'idm'];
const settle = (fn, arg) => pg.waitForFunction(fn, arg, { timeout: 15000 });
await pg.getByRole('button', { name: 'M15', exact: true }).click(); await ready(pg);
const dec0 = await api('/api/terminal/decision?symbol=GOLD'); const price0 = await pg.getByTestId('header-price').innerText();
check('every study is off by default', Object.values((await smc()).counts).every((n) => n === 0));
let indep = true; const seen = {};
for (const f of FEATS) {
  await pg.getByTestId(`smc-${f}`).click();
  await settle((x) => window.__smtChart.smc().counts[x] > 0, f).catch(() => {});
  const c = (await smc()).counts; seen[f] = c[f];
  if (!(c[f] > 0) || FEATS.some((o) => o !== f && c[o] !== 0)) indep = false;
  await pg.getByTestId(`smc-${f}`).click();
  await settle((x) => window.__smtChart.smc().counts[x] === 0, f);
}
check('1. each overlay switches on and off by itself', indep, JSON.stringify(seen));
await pg.getByTestId('smc-show-all').click(); await settle(() => Object.values(window.__smtChart.smc().counts).filter((n) => n > 0).length >= 6);
const allOn = await smc();
check('2. several overlays operate at once', Object.values(allOn.counts).filter((n) => n > 0).length >= 6, JSON.stringify(allOn.counts));
check('7. the chart stays responsive (overlay paint time)', allOn.drawMs < 25, `${allOn.drawMs.toFixed(1)} ms`);
await pg.getByTestId('smc-tf-ob').selectOption('1h'); await settle(() => window.__smtChart.smc().tfs.includes('1h'));
check('3a. a higher-timeframe study loads its own timeframe beside the chart\'s', (await smc()).tfs === '15m,1h', (await smc()).tfs);
await pg.getByRole('button', { name: 'H1', exact: true }).click(); await ready(pg); await settle(() => window.__smtChart.smc().tfs === '1h');
check('3b. switching the chart timeframe re-analyses on the new timeframe', (await smc()).tfs === '1h' && Object.values((await smc()).counts).some((n) => n > 0));
await pg.getByRole('button', { name: 'M15', exact: true }).click(); await ready(pg);
const bull = await (async () => { await pg.getByTestId('smc-side').selectOption('bull'); await pg.waitForTimeout(300); return (await smc()).counts; })();
check('bullish-only draws fewer structures than both sides', bull.fvg <= allOn.counts.fvg && bull.bos <= allOn.counts.bos && (bull.fvg + bull.bos + bull.ob) < (allOn.counts.fvg + allOn.counts.bos + allOn.counts.ob));
await pg.getByTestId('smc-side').selectOption('both');
const dec1 = await api('/api/terminal/decision?symbol=GOLD');
check('6. SignalMesh decision, levels and price are untouched by the overlays', ['engine_status', 'summary', 'entry', 'sl', 'tp1', 'tp2', 'grade', 'score'].every((k) => JSON.stringify(dec0[k]) === JSON.stringify(dec1[k])) && JSON.stringify(dec0.levels) === JSON.stringify(dec1.levels) && (await pg.getByTestId('header-price').innerText()) === price0);
await pg.getByTestId('smc-method').click(); await pg.getByTestId('smc-method-panel').waitFor();
check('the method and calculation times are shown', (await pg.getByTestId('smc-method-panel').innerText()).includes('no lookahead') && (await pg.locator('[data-testid=smc-method-panel] tbody tr').count()) >= 1);
await shot(pg, '06c-smc-method'); await pg.locator('[data-testid=smc-method-panel] button').first().click();
await shot(pg, '06d-smc-all-overlays');
await pg.reload({ waitUntil: 'networkidle' }); await ready(pg);
await settle(() => Object.values(window.__smtChart.smc().counts).filter((n) => n > 0).length >= 6);
check('8. overlay choices survive a reload', (await pg.getByTestId('smc-ob').getAttribute('aria-pressed')) === 'true' && (await pg.getByTestId('smc-tf-ob').inputValue()) === '1h');
await pg.getByTestId('smc-reset').click(); await settle(() => Object.values(window.__smtChart.smc().counts).every((n) => n === 0));
check('reset switches every study off', (await pg.getByTestId('smc-fvg').getAttribute('aria-pressed')) === 'false');

console.log('== narrow desktop window ==');
await pg.setViewportSize({ width: 930, height: 620 }); await pg.waitForTimeout(400);
const nw = await W();
check('chart keeps at least 320px in a 930px window with every panel open', nw.chart >= 320, `${nw.chart}px`);
check('chart keeps at least 160px of height in a 620px-high window', nw.h >= 160, `${nw.h}px`);
check('no sideways page scroll in a narrow window', (await pg.evaluate(() => document.documentElement.scrollWidth)) <= 930);
await shot(pg, '06b-narrow-window');
await pg.setViewportSize({ width: 1600, height: 900 }); await pg.waitForTimeout(300);

console.log('== chart tools ==');
await pg.getByTestId('chart-fit').click(); await pg.waitForTimeout(300);
const fitv = await pg.evaluate(() => { const h = window.__smtChart; const r = h.range(); return { from: r.from, to: r.to, n: h.bars() }; });
check('fit shows every loaded bar', fitv.from <= 1 && fitv.to >= fitv.n - 2, JSON.stringify(fitv));
await pg.getByTestId('chart-indicators').click(); await pg.locator('.menu label').first().click(); await pg.waitForTimeout(200);
check('an indicator from the registry is drawn', (await pg.evaluate(() => window.__smtChart.studies().length)) === 1);
await pg.locator('.menu label').first().click(); await pg.keyboard.press('Escape');
check('and removed again (off by default)', (await pg.evaluate(() => window.__smtChart.studies().length)) === 0);

console.log('== forecast journal (terminal study, own store) ==');
const jv = await api('/api/terminal/journal?limit=300');
await pg.evaluate(() => { const w = JSON.parse(localStorage.getItem('smt_workspace_v2') || '{}'); if (w.bottom) { w.full = false; w.bottom.open = true; w.bottom.h = 420; localStorage.setItem('smt_workspace_v2', JSON.stringify(w)); } });
await pg.reload({ waitUntil: 'networkidle' }); await ready(pg);
await pg.getByRole('tab', { name: /Forecast Journal/ }).click();
await pg.getByTestId('journal').waitFor();
const jwall = await pg.locator('.wall.study').innerText();
check('the journal is labelled a terminal study, not SignalMesh, with hypothetical levels', jwall.includes('NOT SIGNALMESH') && jwall.includes('HYPOTHETICAL ANALYSIS LEVEL') && jwall.includes('Not SignalMesh signals, not broker orders'));
check('the method is shown: how forecasts are recorded and scored', (await pg.locator('[data-testid=journal-method] li').count()) === jv.rules.length && jv.rules.length >= 10);
if (jv.state !== 'READY') {
  check('no journal file configured is said plainly', (await pg.getByTestId('journal-state').innerText()).includes('NOT CONFIGURED'));
} else {
  check('the store is the terminal\'s own and append-only', jv.store.append_only === true && (await pg.getByTestId('journal-store').innerText()).includes('YES'));
  if (!jv.rows.length) {
    check('an empty journal says 0 forecasts and UNKNOWN, never a number', (await pg.getByTestId('journal-empty').innerText()).startsWith('0 forecasts') && (await pg.getByTestId('journal-stats').innerText()).includes('UNKNOWN'));
  } else {
    const now = await api('/api/terminal/journal?limit=300');
    check('every recorded forecast is listed', Math.abs((await pg.locator('[data-testid=journal-rows] tbody tr.row').count()) - now.rows.length) <= 6, `${now.rows.length} rows`);
    check('hit rates are shown per module / symbol / timeframe with the sample size', (await pg.locator('[data-testid=journal-stats] tbody tr').count()) === now.stats.length && now.stats.every((g) => /LUCK|SMALL SAMPLE|JUDGEABLE|NO FINISHED/.test(g.sample)));
    check('Gold and Silver are separate rows, never pooled', new Set(now.stats.map((g) => `${g.module}|${g.symbol}|${g.timeframe}|${g.origin}`)).size === now.stats.length);
    check('losing forecasts are in the record', now.rows.some((r) => r.result.includes('SL')) || now.rows.every((r) => !r.finished), now.rows.filter((r) => r.result.includes('SL')).length + ' SL');
    check('fixture forecasts name the fixture module (never shown as a study)', !(await api('/api/terminal/health')).provider.is_fixture || now.rows.every((r) => ['fixture-demo', 'daily-forecast'].includes(r.module)));
    await pg.locator('[data-testid=journal-rows] tbody tr.row').first().click();
    check('a row opens its id and outcome history', (await pg.getByTestId('journal-detail').innerText()).includes('F-'));
  }
}
await shot(pg, '06b-forecast-journal');
check('the journal has no write route', (await fetch(BASE + '/api/terminal/journal', { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: '{}' })).status === 405);

console.log('== forecasting studies in the indicators menu (terminal studies, display only) ==');
await pg.evaluate(() => { const w = JSON.parse(localStorage.getItem('smt_workspace_v2') || '{}'); w.full = false; if (w.bottom) w.bottom.open = false; w.indicators = []; localStorage.setItem('smt_workspace_v2', JSON.stringify(w)); });
await pg.reload({ waitUntil: 'networkidle' }); await ready(pg);
check('forecasting studies are off by default: no line, no report', (await pg.evaluate(() => window.__smtChart.forecast().lines)) === 0 && (await pg.getByTestId('study-report').count()) === 0);
const indBtn = () => pg.getByTestId('chart-indicators').click();
const menuOpen = async () => { if (!(await pg.getByTestId('indicator-menu').count())) await indBtn(); await pg.getByTestId('indicator-menu').waitFor(); };
const menuShut = async () => { if (await pg.getByTestId('indicator-menu').count()) await pg.keyboard.press('Escape'); await pg.getByTestId('indicator-menu').waitFor({ state: 'detached' }); await pg.waitForTimeout(200); };
await menuOpen();
const menuText = await pg.getByTestId('indicator-menu').innerText();
check('the indicators menu lists the forecasting studies', menuText.includes('Daily forecast') && menuText.includes('Asset ranking table') && menuText.includes('HYPOTHETICAL'));
await pg.getByTestId('ind-fc-daily').check(); await pg.getByTestId('ind-fc-ranking').check();
await menuShut(); await pg.getByTestId('fc-ranking').waitFor(); await pg.waitForTimeout(600);
const fcd = await api('/api/terminal/forecast/daily?symbol=' + (await pg.evaluate(() => window.__smtChart.symbol())));
const rk = await api('/api/terminal/forecast/ranking');
const repText = await pg.getByTestId('study-report').innerText();
check('the report is labelled a terminal study, not SignalMesh', repText.includes('TERMINAL STUDY · NOT SIGNALMESH'));
if (fcd.state === 'OK') {
  check('two forecast lines are drawn on the chart (top and bottom)', (await pg.evaluate(() => window.__smtChart.forecast().lines)) >= 2);
  check('the report shows the adapter\'s top and bottom', (await pg.getByTestId('fc-top').innerText()) === fcd.top.toFixed(fcd.decimals) && (await pg.getByTestId('fc-bottom').innerText()) === fcd.bottom.toFixed(fcd.decimals));
  check('confidence reads UNKNOWN until the journal has evidence', /CONFIDENCE\s+UNKNOWN/.test(repText) || fcd.journal.some((g) => g.finished >= 20));
  check('a scenario is shown only when the range is full, with hypothetical levels', fcd.scenarios.length ? (await pg.getByTestId('fc-scenario').first().innerText()).includes('HYPOTHETICAL ANALYSIS LEVEL') : (await pg.getByTestId('fc-no-scenario').innerText()).includes('NOT AVAILABLE'));
  check('longer outlooks without enough history read UNKNOWN', Object.values(fcd.outlooks).filter((o) => o.state !== 'OK').length === (await pg.locator('[data-testid=fc-outlooks] b', { hasText: 'UNKNOWN' }).count()));
  await menuOpen(); await pg.getByTestId('fc-side').selectOption('top'); await menuShut(); await pg.waitForTimeout(300);
  check('"top only" draws one forecast line', (await pg.evaluate(() => window.__smtChart.forecast().lines)) === 1 + 4 * fcd.scenarios.length);
  await menuOpen(); await pg.getByTestId('fc-side').selectOption('both'); await pg.getByTestId('fc-history').check(); await menuShut(); await pg.waitForTimeout(300);
  check('"history" adds the finished days\' lines', (await pg.evaluate(() => window.__smtChart.forecast().history)) >= 1);
} else {
  check('a daily forecast that cannot be calculated says NOT AVAILABLE and draws nothing', (await pg.getByTestId('fc-daily-state').innerText()).includes('NOT AVAILABLE') && (await pg.evaluate(() => window.__smtChart.forecast().lines)) === 0);
}
check('the ranking table lists every instrument once, with a GO TRADE line', (await pg.locator('[data-testid=fc-ranking] tbody tr').count()) === rk.rows.length && (await pg.getByTestId('fc-go').innerText()).startsWith('GO TRADE:'));
await pg.getByTestId('fc-method').click(); await pg.getByTestId('fc-method-panel').waitFor();
check('the method panel says how, from which closed bars, and when', (await pg.getByTestId('fc-method-panel').innerText()).includes('CLOSED candles') && (await pg.locator('[data-testid=fc-method-panel] .kv .k').count()) >= 10);
await shot(pg, '06c-forecasting-studies-method');
await pg.locator('[data-testid=fc-method-panel] button').first().click();
await shot(pg, '06d-forecasting-studies');
await pg.reload({ waitUntil: 'networkidle' }); await ready(pg); await pg.getByTestId('fc-ranking').waitFor();
check('the studies are remembered in the workspace after a reload', (await pg.getByTestId('study-report').count()) === 1);
await pg.getByTestId('fc-report-toggle').click();
check('the report folds away and the lines stay', (await pg.getByTestId('fc-ranking').count()) === 0 && (fcd.state !== 'OK' || (await pg.evaluate(() => window.__smtChart.forecast().lines)) >= 2));
await pg.getByTestId('fc-report-toggle').click();
await menuOpen(); await pg.getByTestId('ind-fc-daily').uncheck(); await pg.getByTestId('ind-fc-ranking').uncheck(); await menuShut(); await pg.waitForTimeout(300);
check('switched off again: nothing is left on the chart', (await pg.evaluate(() => window.__smtChart.forecast().lines)) === 0 && (await pg.getByTestId('study-report').count()) === 0);

console.log('== phone layout ==');
const phone = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, isMobile: true, hasTouch: true });
const mp = await phone.newPage();
if (process.env.TERM_KEY) await mp.setExtraHTTPHeaders(headers);
await mp.goto(BASE + '/', { waitUntil: 'networkidle' }); await ready(mp);
const m = await mp.evaluate(() => ({ chart: window.__smtChart.paneWidth(), h: window.__smtChart.paneHeight(), win: window.innerWidth, winH: window.innerHeight, scroll: document.documentElement.scrollWidth }));
check('phone: chart spans the screen width', m.chart >= m.win - 2, `${m.chart}px of ${m.win}px`);
check('phone: chart is the main area', m.h >= m.winH * 0.5, `${m.h}px of ${m.winH}px`);
check('phone: no sideways page scroll', m.scroll <= m.win);
await shot(mp, '07-phone-chart');
for (const v of ['quotes', 'signal', 'trade', 'account']) { await mp.getByTestId(`nav-${v}`).tap(); await mp.waitForTimeout(400); await shot(mp, `08-phone-${v}`); }
check('phone: Account view shows the broker account panel', (await mp.getByTestId('account-info').count()) === 1 || (await mp.locator('.wall.broker').count()) === 1);
await mp.getByTestId('nav-quotes').tap(); await mp.locator('.watch tbody tr.row').first().tap(); await ready(mp);
check('phone: tapping a quote opens its chart', (await mp.getByTestId('chart').count()) === 1);

console.log(fails ? `${fails} FAIL` : 'workspace acceptance: all checks passed');
await b.close();
process.exit(fails ? 1 : 0);
