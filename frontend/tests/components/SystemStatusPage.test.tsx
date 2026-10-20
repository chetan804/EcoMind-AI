import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { SystemStatusPage } from '@/features/settings';

function mockApi(handlers: Record<string, () => Response | Error>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const result = handlers[url]?.() ?? new Response('not found', { status: 404 });
      return result instanceof Error ? Promise.reject(result) : Promise.resolve(result);
    }),
  );
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SystemStatusPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('SystemStatusPage', () => {
  it('shows a running API with ready dependencies', async () => {
    mockApi({
      '/health': () => Response.json({ status: 'ok' }),
      '/ready': () =>
        Response.json({ status: 'ready', checks: { database: { status: 'ok' }, migrations: { status: 'ok' } } }),
    });
    renderPage();
    expect(await screen.findByText('Running')).toBeInTheDocument();
    expect(await screen.findByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('database')).toBeInTheDocument();
    expect(screen.getByText('migrations')).toBeInTheDocument();
  });

  it('renders the 503 readiness report as "Not ready" with the failing check', async () => {
    mockApi({
      '/health': () => Response.json({ status: 'ok' }),
      '/ready': () =>
        Response.json(
          {
            status: 'not_ready',
            checks: {
              database: { status: 'ok' },
              migrations: { status: 'failed', detail: 'schema revision is none, expected 0001' },
            },
          },
          { status: 503 },
        ),
    });
    renderPage();
    expect(await screen.findByText('Not ready')).toBeInTheDocument();
    expect(screen.getByText(/schema revision is none/)).toBeInTheDocument();
  });

  it('shows a safe message when the API cannot be reached', async () => {
    mockApi({ '/health': () => new TypeError('Failed to fetch'), '/ready': () => new TypeError('Failed to fetch') });
    renderPage();
    expect(await screen.findByText('Unreachable')).toBeInTheDocument();
    expect((await screen.findAllByText(/cannot reach the server/i)).length).toBeGreaterThan(0);
  });
});
