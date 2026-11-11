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
  `built        ${b.built_at ?? 'UNKNOWN'}`, `deployed     ${b.started_at}`, `toolbar read ${shown.version} · ${shown.env} · ${shown.build}`, '', ...taken, ''].join('\n'));
console.log(`\n${taken.length} screenshots of SignalMesh Terminal ${b.label} · ${b.commit} · ${b.environment} · ${b.data}\n-> ${OUT}/ (manifest.txt lists them)`);
await browser.close();
