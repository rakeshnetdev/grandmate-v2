import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind class names, resolving conflicts in favour of the last one.
 *
 * `clsx` handles conditionals; `twMerge` resolves genuine Tailwind conflicts so that
 * `cn('p-2', 'p-4')` yields `p-4` rather than both. This is the standard shadcn/ui
 * helper and every UI primitive uses it.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
