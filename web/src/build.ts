import type { BuildIdentity } from './api/types';

// injected by vite.config.ts at build time — the bundle's own identity, never typed
declare const __UI_BUILD__: { version: string; commit: string; build: number | null };
export const UI_BUILD = typeof __UI_BUILD__ !== 'undefined' ? __UI_BUILD__ : { version: 'UNKNOWN', commit: 'UNKNOWN', build: null };

/** The browser's bundle and the server's build must be the same build. */
export const uiMismatch = (server: BuildIdentity | undefined) =>
  !!server && server.commit !== 'UNKNOWN' && UI_BUILD.commit !== 'UNKNOWN' && (server.commit !== UI_BUILD.commit || server.version !== UI_BUILD.version);
export const buildWord = (b: { build: number | null; commit: string; dirty?: boolean }) => `build ${b.build ?? 'n/a'} · ${b.commit}${b.dirty ? ' +local changes' : ''}`;
