// END-TO-END: switch GOLD -> BTC -> SILVER -> GOLD in the real UI and prove every displayed price
// belongs to the selected symbol. Run against an adapter (fixture or real):
//   TERM_URL=http://127.0.0.1:8090 node e2e/switch.mjs
// Needs Playwright with Chromium (CI installs it; locally: npx playwright install chromium).
// PLAYWRIGHT_MODULE lets a preinstalled Playwright be used (e.g. /opt/node-tools/node_modules/playwright/index.mjs)
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = (process.env.TERM_URL || 'http://127.0.0.1:8090').replace(/\/$/, '');
const headers = process.env.TERM_KEY ? { 'X-Terminal-Key': process.env.TERM_KEY } : {};
const api = async (p) => (await fetch(BASE + p, { headers })).json();
const b = await chromium.launch();
const pg = await b.newPage({ viewport: { width: 1600, height: 900 } });
if (process.env.TERM_KEY) await pg.setExtraHTTPHeaders(headers);
let fails = 0;
const check = (label, want, got) => { const ok = JSON.stringify(want) === JSON.stringify(got); console.log(`  ${ok ? 'OK  ' : 'FAIL'} ${label}: want=${JSON.stringify(want)} got=${JSON.stringify(got)}`); if (!ok) fails++; };
await pg.goto(BASE + '/', { waitUntil: 'networkidle' });
const inst = await api('/api/terminal/instruments');
const order = ['GOLD', 'BTC', 'SILVER', 'GOLD'].filter((s) => inst.watch.includes(s));
for (const sym of order) {
  await pg.locator('.watch tbody tr.row', { hasText: sym }).first().click();
  await pg.waitForFunction((s) => document.querySelector('.pricebox')?.getAttribute('data-symbol') === s && document.querySelector('[data-testid=header-price]')?.textContent !== '…'
    && window.__smtChart?.symbol() === s && window.__smtChart?.range() != null, sym, { timeout: 20000 });
  const d = await api(`/api/terminal/decision?symbol=${sym}`);
  const want = d.price.last_closed_1m?.price;
  const shown = Number(await pg.locator('[data-testid=header-price]').textContent());
  check(`${sym}: header price = engine newest 1m close`, Number(want.toFixed(d.decimals)), shown);
  check(`${sym}: chart header names the symbol`, true, (await pg.locator('.chart-head').innerText()).startsWith(sym));
  check(`${sym}: decision panel names the symbol`, true, (await pg.locator('.panel .section-title').first().innerText()).includes(sym));
  // the view lands on the newest candle: it is inside the visible range, about two thirds across
  const v = await pg.evaluate(() => { const h = window.__smtChart; const r = h.range(); return { from: r?.from, to: r?.to, n: h.bars(), sym: h.symbol() }; });
  const pos = v.n && v.to > v.from ? (v.n - 1 - v.from) / (v.to - v.from) : -1;
  check(`${sym}: chart data is the symbol's`, sym, v.sym);
  check(`${sym}: newest bar visible, placed at 55–80% of the width (got ${(pos * 100).toFixed(0)}%)`, true, pos >= 0.55 && pos <= 0.8);
  // ... and inside the visible PRICE range: its close is drawn within the pane (the ETH-axis-under-SOL bug)
  const yv = await pg.evaluate(() => { const h = window.__smtChart; return { y: h.lastBarY(), hgt: h.paneHeight(), auto: h.autoScale() }; });
  check(`${sym}: price axis auto-scales to the symbol`, true, yv.auto === true);
  check(`${sym}: newest candle drawn inside the pane (y=${yv.y == null ? 'off' : Math.round(yv.y)} of ${yv.hgt})`, true, yv.y != null && yv.y > 0 && yv.y < yv.hgt);
  // simulate the user dragging the price axis (manual scale) before the next switch
  await pg.evaluate(() => window.__smtChart.manualScale());
  // the chart's newest bar belongs to the same symbol (its close is the symbol's 15m close)
  const c = await api(`/api/terminal/candles?symbol=${sym}&tf=15m&n=400`);
  if (c.count) {
    const head = await pg.locator('.chart-head').innerText();
    check(`${sym}: chart last bar = engine newest 15m close`, true, head.includes(Number(c.last_bar.price).toFixed(c.decimals)));
  }
}
await pg.getByRole('button', { name: '1H', exact: true }).click();
await pg.waitForFunction(() => window.__smtChart?.bars() > 0 && window.__smtChart?.range() != null && document.querySelector('.chart-head')?.innerText.includes('1H'), null, { timeout: 20000 });
const v2 = await pg.evaluate(() => { const h = window.__smtChart; const r = h.range(); return { from: r.from, to: r.to, n: h.bars() }; });
const pos2 = (v2.n - 1 - v2.from) / (v2.to - v2.from);
check(`1H switch: newest bar visible at 55–80% (got ${(pos2 * 100).toFixed(0)}%)`, true, pos2 >= 0.55 && pos2 <= 0.8);
console.log(fails ? `${fails} FAIL` : 'all symbol switches consistent');
await b.close();
process.exit(fails ? 1 : 0);
