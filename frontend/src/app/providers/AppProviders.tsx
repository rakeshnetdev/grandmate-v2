/**
 * Application-wide providers.
 *
 * Kept in one component so tests can wrap a subject in the same context the app uses,
 * rather than assembling providers ad hoc in each test file.
 */
import type { QueryClient } from '@tanstack/react-query';
import { QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useState } from 'react';

import { createQueryClient } from './queryClient';

interface AppProvidersProps {
  children: ReactNode;
  /** Override the client. Tests pass one with retries disabled. */
  client?: QueryClient;
}

export function AppProviders({ children, client }: AppProvidersProps) {
  // useState rather than a module-level constant: a module-level client would be shared
  // across test files and leak cached data between them.
  const [queryClient] = useState(() => client ?? createQueryClient());

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
