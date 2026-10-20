import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router/dom';
import { createTestRouter } from '@/app/router';

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url === '/health'
          ? Response.json({ status: 'ok' })
          : Response.json({ status: 'ready', checks: { database: { status: 'ok' } } }),
      ),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createTestRouter([path])} />
    </QueryClientProvider>,
  );
}

describe('application routing', () => {
  it('redirects / to the system status page inside the app layout', async () => {
    renderAt('/');
    expect(await screen.findByRole('heading', { name: 'System status' })).toBeInTheDocument();
    expect(screen.getByText('EcoMind AI')).toBeInTheDocument();
  });

  it('renders a not-found page for unknown routes', async () => {
    renderAt('/does/not/exist');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
