/**
 * Vitest global setup.
 *
 * Adds jest-dom matchers and clears React Testing Library state between tests so one
 * test's DOM cannot influence the next.
 */
import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';

// jsdom has never implemented `matchMedia` — anything reading `prefers-color-scheme`
// (Phase 16a's `ThemeProvider`) needs it to exist at all, even as a "no preference"
// stub. A minimal `MediaQueryList`-shaped object, not a real implementation: no test
// here needs it to actually track OS theme changes, just to not throw.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// This runtime's Node has a native `localStorage` global active without a
// `--localstorage-file` path, which shadows jsdom's own and throws on every method
// (`getItem`/`setItem`/`removeItem`/`clear` all "is not a function") — nothing to do
// with jsdom or any code under test. Stubbed fresh per test (not a one-time module-level
// assignment) so state never leaks from one test into the next, same as `cleanup()`
// resets the DOM. Any component reading `localStorage` at mount (Phase 16a's
// `ThemeProvider`) needs this in place before it renders, hence `beforeEach`, not
// `afterEach`.
function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => store.clear(),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
  } as Storage;
}

beforeEach(() => {
  vi.stubGlobal('localStorage', createMemoryStorage());
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
