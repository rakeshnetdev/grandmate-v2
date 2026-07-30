/**
 * Light/dark switch. Always toggles between the two explicit states based on what's
 * currently resolved — a user who has never touched it is on `'system'`, and their
 * first click locks in the opposite of whatever `'system'` was currently resolving to
 * (the intuitive "flip it" behaviour), not a three-way cycle through `'system'` again.
 */
import { Moon, Sun } from 'lucide-react';

import { Button } from '@/shared/components/ui/button';

import { useTheme } from './useTheme';

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={resolvedTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
    >
      {resolvedTheme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
