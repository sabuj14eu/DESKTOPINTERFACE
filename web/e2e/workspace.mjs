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

console.log('== chart tools ==');
await pg.getByTestId('chart-fit').click(); await pg.waitForTimeout(300);
const fitv = await pg.evaluate(() => { const h = window.__smtChart; const r = h.range(); return { from: r.from, to: r.to, n: h.bars() }; });
check('fit shows every loaded bar', fitv.from <= 1 && fitv.to >= fitv.n - 2, JSON.stringify(fitv));
await pg.getByTestId('chart-indicators').click(); await pg.locator('.menu label').first().click(); await pg.waitForTimeout(200);
check('an indicator from the registry is drawn', (await pg.evaluate(() => window.__smtChart.studies().length)) === 1);
await pg.locator('.menu label').first().click(); await pg.keyboard.press('Escape');
check('and removed again (off by default)', (await pg.evaluate(() => window.__smtChart.studies().length)) === 0);

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
