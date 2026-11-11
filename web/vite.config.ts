import { execSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// THE UI BUNDLE'S OWN BUILD IDENTITY. In the image it is ../build.json (computed from the git
// checkout by the Dockerfile's `meta` stage); in development it is read from git here. The
// terminal compares it with the adapter's and warns when the browser holds an older bundle.
function buildIdentity() {
  const read = (p: string) => (existsSync(p) ? readFileSync(p, 'utf8') : '');
  const version = read('../VERSION').trim() || 'UNKNOWN';
  try { const j = JSON.parse(read('../build.json')); return { version, commit: j.commit || 'UNKNOWN', build: j.build ?? null }; } catch { /* not an image build */ }
  const git = (a: string) => { try { return execSync(`git ${a}`, { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); } catch { return ''; } };
  const count = git('rev-parse --is-shallow-repository') === 'true' ? '' : git('rev-list --count HEAD');
  return { version, commit: git('rev-parse --short=7 HEAD') || 'UNKNOWN', build: count ? Number(count) : null };
}

// Dev: the UI talks to the adapter on :8090. Prod: the adapter serves dist/.
export default defineConfig({
  // RELATIVE asset paths: the same build works at https://host/ and at https://host/terminal/
  base: './',
  plugins: [react()],
  define: { __UI_BUILD__: JSON.stringify(buildIdentity()) },
  server: {
    port: 5173,
    proxy: { '/api/terminal': { target: process.env.SMT_DEV_ADAPTER || 'http://127.0.0.1:8090', changeOrigin: true } },
  },
  build: { outDir: 'dist', sourcemap: false },
});
