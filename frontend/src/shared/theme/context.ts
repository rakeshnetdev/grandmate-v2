import { createContext } from 'react';

import type { Theme } from './ThemeProvider';

export interface ThemeContextValue {
  theme: Theme;
  /** Resolved value actually applied — `system` never appears here, only what it
   * currently resolves to, for anything that needs a concrete light/dark rather than
   * the stored preference (e.g. picking a syntax-highlight palette). */
  resolvedTheme: 'light' | 'dark';
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);
