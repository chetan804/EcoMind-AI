import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { RouterProvider } from 'react-router/dom';
import { createTestRouter } from '@/app/router';
import type { SessionUser } from '@/services/session';
import { testUser } from './session';

export const userWith = (permissions: string[], overrides: Partial<SessionUser> = {}): SessionUser => ({
  ...testUser,
  roles: ['manager'],
  permissions,
  ...overrides,
});

/** Renders the real route table at `path` with a fresh query cache that never retries. */
export function renderAt(path: string): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createTestRouter([path])} />
    </QueryClientProvider>,
  );
}
