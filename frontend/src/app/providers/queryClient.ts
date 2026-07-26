import { QueryClient } from '@tanstack/react-query';

/**
 * Build a query client with the application's defaults.
 *
 * Lives in its own module rather than alongside `AppProviders` so that file exports only
 * components — which is what keeps React Fast Refresh working during development.
 *
 * Exported so tests can construct a fresh client per test.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Analysis results are immutable once computed, so refetching on window focus is
        // pure noise for most of this application's data.
        refetchOnWindowFocus: false,
        retry: 1,
        staleTime: 5_000,
      },
    },
  });
}
