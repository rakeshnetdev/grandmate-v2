/**
 * Test render helper.
 *
 * Wraps a subject in the same providers the application uses, so a test exercises the
 * real context rather than an approximation of it. Retries are disabled: retrying a
 * deliberately-failing request only makes the suite slow.
 */
import { QueryClient } from '@tanstack/react-query';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';

import { AppProviders } from '@/app/providers/AppProviders';

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Initial history entries for the router. */
  routes?: string[];
}

export function renderWithProviders(
  ui: ReactElement,
  { routes = ['/'], ...options }: RenderWithProvidersOptions = {},
): RenderResult {
  const client = createTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <AppProviders client={client}>
        <MemoryRouter initialEntries={routes}>{children}</MemoryRouter>
      </AppProviders>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}
