/**
 * Vitest global setup.
 *
 * Adds jest-dom matchers and clears React Testing Library state between tests so one
 * test's DOM cannot influence the next.
 */
import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
