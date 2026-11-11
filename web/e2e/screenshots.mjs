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
const layout = (bottom) => pg.evaluate((h) => localStorage.setItem('smt_workspace_v2', JSON.stringify({ v: 2, left: { open: true, w: 300 }, right: { open: true, w: 330 }, bottom: { open: true, h }, full: false, tab: 'Active Signals', bars: 500, indicators: [], chart: { ladder: true, markers: true, history: false, expired: false, volume: true, log: false, magnet: false }, account: '' })), bottom);

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
