// THE STANDARD SCREENSHOT SET, taken from a RUNNING terminal — the real application, whatever it
// is connected to. Each picture shows the version, commit, environment and data kind in the
// toolbar, and the same facts are in the file name and in manifest.txt.
//   TERM_URL=http://127.0.0.1:8090 [TERM_KEY=<read key>] OUT=dir node e2e/screenshots.mjs
// Read-only: it opens pages and clicks tabs. On the box use scripts/screenshots.sh.
import { mkdirSync, writeFileSync } from 'node:fs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = (process.env.TERM_URL || 'http://127.0.0.1:8090').replace(/\/$/, '');
const headers = process.env.TERM_KEY ? { 'X-Terminal-Key': process.env.TERM_KEY } : {};
const health = await (await fetch(BASE + '/api/terminal/health', { headers })).json();
const b = health.build;
const tag = `v${b.version}-${b.commit}-${b.environment}-${b.data.replace(/\s+/g, '_')}`.toLowerCase();
const OUT = `${process.env.OUT || 'screenshots'}/${tag}`;
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, extraHTTPHeaders: headers });
const pg = await ctx.newPage();
const taken = [];
const shot = async (page, name, what) => { await page.screenshot({ path: `${OUT}/${name}.png` }); taken.push(`${name}.png — ${what}`); console.log(`  saved ${OUT}/${name}.png`); };
const ready = (page) => page.waitForFunction(() => window.__smtChart?.range() != null && document.querySelector('[data-testid=version]')?.textContent !== '…', null, { timeout: 45000 });
const layout = (bottom) => pg.evaluate((h) => localStorage.setItem('smt_workspace_v2', JSON.stringify({ v: 2, left: { open: true, w: 300 }, right: { open: true, w: 330 }, bottom: { open: true, h }, full: false, tab: 'Active Signals', bars: 500, indicators: [], fc: { side: 'both', history: false, report: true }, chart: { ladder: true, markers: true, history: false, expired: false, volume: true, log: false, magnet: false }, account: '' })), bottom);

await pg.goto(BASE + '/', { waitUntil: 'networkidle' });
await layout(250); await pg.reload({ waitUntil: 'networkidle' }); await ready(pg); await pg.waitForTimeout(800);
const shown = { version: await pg.getByTestId('version').innerText(), env: await pg.getByTestId('environment').innerText(), build: await pg.getByTestId('build-commit').innerText() };
await shot(pg, '01-desktop', 'full desktop workspace');
// CHART BEHAVIOUR ON THIS RUNNING TERMINAL (whatever data it is connected to): each line is a real interaction in a real browser
const ui = [];
const uiCheck = async (name, fn) => { let ok = false, why = ''; try { ok = !!(await fn()); } catch (e) { why = ' — ' + String(e).slice(0, 120); } ui.push(`${ok ? 'PASS' : 'FAIL'} ${name}${why}`); console.log(`  UI ${ok ? 'PASS' : 'FAIL'} ${name}${why}`); };
const box = await pg.locator('.chart-body').boundingBox();
const cx = box.x + box.width * 0.45, cy = box.y + box.height * 0.45;
const rng = () => pg.evaluate(() => { const r = window.__smtChart.range(); return { from: r.from, to: r.to }; });
await uiCheck('crosshair: moving over a bar shows its time and O / H / L / C', async () => { await pg.mouse.move(cx, cy); await pg.waitForTimeout(400); const t = await pg.getByTestId('ohlc').innerText(); return /O\s*[\d.]+/.test(t) && /C\s*[\d.]+/.test(t) && t.includes('→'); });
await uiCheck('zoom: the mouse wheel changes how many bars are visible', async () => { const a = await rng(); await pg.mouse.move(cx, cy); await pg.mouse.wheel(0, -600); await pg.waitForTimeout(500); const b2 = await rng(); return Math.abs((b2.to - b2.from) - (a.to - a.from)) > 1; });
await uiCheck('scroll: dragging the chart moves it through time', async () => { const a = await rng(); await pg.mouse.move(cx, cy); await pg.mouse.down(); await pg.mouse.move(cx + 260, cy, { steps: 8 }); await pg.mouse.up(); await pg.waitForTimeout(500); const b2 = await rng(); return Math.abs(b2.from - a.from) > 1; });
await uiCheck('"latest" brings the newest candle back into view', async () => { await pg.getByText('latest', { exact: false }).first().click(); await pg.waitForTimeout(500); const r = await rng(); const n = await pg.evaluate(() => window.__smtChart.bars()); return r.to >= n - 1; });
await uiCheck('full screen: the chart takes the whole width, and Escape returns the panels', async () => { const w0 = await pg.evaluate(() => window.__smtChart.paneWidth()); await pg.getByTestId('toggle-full').click(); await pg.waitForTimeout(600); const w1 = await pg.evaluate(() => window.__smtChart.paneWidth()); await pg.keyboard.press('Escape'); await pg.waitForTimeout(600); const w2 = await pg.evaluate(() => window.__smtChart.paneWidth()); return w1 > w0 * 1.3 && Math.abs(w2 - w0) < 8; });
await uiCheck('the newest candle is drawn inside the visible price range', async () => { const y = await pg.evaluate(() => window.__smtChart.lastBarY()); const h = await pg.evaluate(() => window.__smtChart.paneHeight()); return y != null && y > 0 && y < h; });

await pg.getByTestId('toggle-full').click(); await pg.waitForTimeout(600);
await shot(pg, '02-full-screen-chart', 'full-screen chart');
await pg.keyboard.press('Escape');
await layout(520); await pg.reload({ waitUntil: 'networkidle' }); await ready(pg);
for (const [n, tab, what] of [['03-account-information', 'Account Information', 'Account Information (broker-reported values)'], ['04-active-signals', 'Active Signals', 'Active Signals (SignalMesh recommendations)'],
  ['05-trade-history', 'Trade History', 'Trade History (broker trades)'], ['06-open-positions', 'Open Positions', 'Open Positions (broker)'], ['07-pending-orders', 'Pending Orders', 'Pending Orders (broker)']]) {
  await pg.getByRole('tab', { name: new RegExp('^' + tab) }).click(); await pg.waitForTimeout(1500); await shot(pg, n, what);
}
await pg.getByRole('tab', { name: /^Forecast Journal/ }).click(); await pg.getByTestId('journal').waitFor(); await pg.waitForTimeout(1500);
await shot(pg, '12-forecast-journal', 'Forecast Journal (terminal study: the record, hit rates with sample size)');
await pg.locator('[data-testid=journal-method] summary').click(); await pg.waitForTimeout(400);
await shot(pg, '13-forecast-journal-method', 'how forecasts are recorded and scored');
await pg.getByTestId('toggle-bottom').click(); await pg.getByTestId('smc-show-all').click();
await pg.waitForFunction(() => Object.values(window.__smtChart.smc().counts).some((n) => n > 0), null, { timeout: 20000 }).catch(() => {}); await pg.waitForTimeout(1200);
await shot(pg, '10-smart-money-concepts', 'Smart Money Concepts overlays, all on (display-only studies)');
await pg.getByTestId('smc-method').click(); await pg.getByTestId('smc-method-panel').waitFor(); await pg.waitForTimeout(500);
await shot(pg, '11-smc-method-and-calculation-times', 'how the overlays are calculated, and when');
await pg.locator('[data-testid=smc-method-panel] button').first().click(); await pg.getByTestId('smc-reset').click(); await pg.getByTestId('toggle-bottom').click();
// forecasting studies: switched on through the saved workspace (exactly what ticking them in the indicators menu stores)
const studies = (inds, bottomOpen, tab) => pg.evaluate(([i, o, t]) => { const w = JSON.parse(localStorage.getItem('smt_workspace_v2') || '{}'); w.indicators = i; w.fc = { side: 'both', history: true, report: true }; w.full = false; w.bottom = { open: o, h: 520 }; w.tab = t; localStorage.setItem('smt_workspace_v2', JSON.stringify(w)); }, [inds, bottomOpen, tab]);
await studies(['fc-daily', 'fc-ranking'], false, 'Forecast Journal'); await pg.reload({ waitUntil: 'networkidle' }); await ready(pg);
await pg.getByTestId('fc-ranking').waitFor({ timeout: 90000 }).catch(() => {}); await pg.waitForTimeout(2500);
await shot(pg, '14-forecasting-studies', 'Daily forecast top / bottom lines and the asset ranking table, with the report (display-only terminal studies)');
await pg.getByTestId('fc-method').click(); await pg.getByTestId('fc-method-panel').waitFor(); await pg.waitForTimeout(400);
await shot(pg, '15-forecasting-studies-method', 'how the forecasting studies are calculated, from which closed bars, and when');
await pg.locator('[data-testid=fc-method-panel] button').first().click();
await studies(['st-fib', 'st-avwap', 'st-wolfe', 'st-elliott', 'st-vp'], false, 'Forecast Journal'); await pg.reload({ waitUntil: 'networkidle' }); await ready(pg);
await pg.getByTestId('st-report').waitFor({ timeout: 90000 }).catch(() => {}); await pg.waitForTimeout(2500);
await shot(pg, '17-pattern-studies-report', 'Fibonacci extension, anchored VWAP, Wolfe wave, Elliott wave and volume profile, with their tables (display-only terminal studies; Wolfe and Elliott are recorded in the Forecast Journal)');
await pg.getByTestId('fc-report-toggle').click().catch(() => {}); await pg.waitForTimeout(600);
await shot(pg, '18-pattern-studies-chart', 'the same five studies drawn on the chart, tables folded away');
await pg.getByTestId('fc-report-toggle').click().catch(() => {});
// GOLD and SILVER on M15, H1, H4, D1 with the five pattern studies on, tables folded: what the acceptance matrix checked, as pictures
await pg.getByTestId('fc-report-toggle').click().catch(() => {}); await pg.waitForTimeout(400);      // fold the tables: the chart is the subject
const symOpts = await pg.locator('select[aria-label=Symbol] option').allInnerTexts();
for (const sym of ['GOLD', 'SILVER'].filter((x) => symOpts.some((o) => o.trim() === x))) {
  await pg.locator('select[aria-label=Symbol]').selectOption(sym);
  for (const [label, tfv] of [['M15', '15m'], ['H1', '1h'], ['H4', '4h'], ['D1', '1d']]) {
    const btn = pg.getByRole('button', { name: label, exact: true }).first();
    if (!(await btn.count())) continue;
    await btn.click();
    await pg.waitForFunction((s) => window.__smtChart?.symbol() === s && window.__smtChart?.range() != null, sym, { timeout: 30000 }).catch(() => {});
    await pg.waitForTimeout(2500);
    const d = await pg.evaluate(() => window.__smtChart.patterns());
    await shot(pg, `19-${sym.toLowerCase()}-${tfv}-pattern-studies`, `${sym} ${label}: the five pattern studies on the chart (drawn shapes: ${Object.entries(d).map(([k, v]) => `${k.slice(3)} ${v}`).join(', ')})`);
    if (sym === 'GOLD' && tfv === '15m') {
      await pg.getByTestId('fc-report-toggle').click().catch(() => {}); await pg.waitForTimeout(700);
      await uiCheck('Elliott report: PIVOTS, COUNT and TRADE SETUP are three separate lines (or the count reads UNKNOWN)', async () => { const t = await pg.getByTestId('st-elliott-report').innerText(); return t.includes('UNKNOWN') || (t.includes('PIVOTS') && t.includes('COUNT') && t.includes('TRADE SETUP') && (t.includes('PARTIAL COUNT') || t.includes('COMPLETE IMPULSE'))); });
      await shot(pg, '20-gold-15m-pattern-report', 'GOLD M15: the pattern study tables, with the Elliott status lines and the journal record');
      await pg.getByTestId('fc-report-toggle').click().catch(() => {});
    }
  }
}
await pg.getByRole('button', { name: 'M15', exact: true }).first().click().catch(() => {});
await pg.getByTestId('fc-report-toggle').click().catch(() => {});
await studies([], true, 'Forecast Journal'); await pg.reload({ waitUntil: 'networkidle' }); await ready(pg); await pg.getByTestId('journal').waitFor(); await pg.waitForTimeout(1500);
await shot(pg, '16-forecast-journal-with-records', 'Forecast Journal once the daily-forecast study is recording');
await pg.getByTestId('version-badge').click(); await pg.getByTestId('about').waitFor(); await pg.waitForTimeout(700);
await shot(pg, '08-version-and-release-history', 'build details and release history');
await pg.keyboard.press('Escape');
const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, extraHTTPHeaders: headers });
const mp = await phone.newPage();
await mp.goto(BASE + '/', { waitUntil: 'networkidle' }); await ready(mp); await mp.waitForTimeout(600);
await shot(mp, '09-phone-chart', 'phone layout, chart view');
writeFileSync(`${OUT}/manifest.txt`, [
  `SignalMesh Terminal screenshots — taken ${new Date().toISOString()} from ${BASE}`,
  `REAL APPLICATION: these are pictures of the running terminal at that address, not a mock-up.`,
  `version      ${b.version}`, `build        ${b.build ?? 'n/a'}`, `git commit   ${b.commit}${b.dirty ? ' (+ uncommitted local changes)' : ''}`,
  `environment  ${b.environment}`, `DATA         ${b.data}${b.data === 'TEST FIXTURES' ? '  <-- recorded test fixtures, NOT a market, NOT your account' : ''}`,
  `built        ${b.built_at ?? 'UNKNOWN'}`, `deployed     ${b.started_at}`, `toolbar read ${shown.version} · ${shown.env} · ${shown.build}`, '', 'CHART BEHAVIOUR CHECKS (this running terminal, real browser):', ...ui.map((x) => '  ' + x), '', ...taken, ''].join('\n'));
console.log(`\n${taken.length} screenshots of SignalMesh Terminal ${b.label} · ${b.commit} · ${b.environment} · ${b.data}\n-> ${OUT}/ (manifest.txt lists them)`);
await browser.close();
