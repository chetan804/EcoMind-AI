import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router/dom';
import { createTestRouter } from '@/app/router';
import { resetSession, signInViaRefresh } from '../helpers/session';

const fetchMock = vi.fn();

beforeEach(() => {
  resetSession();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createTestRouter([path]);
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const healthyBackend = (url: string) =>
  Response.json(
    url === '/health' ? { status: 'ok' } : { status: 'ready', checks: { database: { status: 'ok' } } },
  );

describe('application routing (signed in)', () => {
  beforeEach(() => signInViaRefresh(fetchMock, undefined, healthyBackend));

  it('renders the system status page inside the app shell', async () => {
    renderAt('/settings/system-status');
    expect(await screen.findByRole('heading', { name: 'System status' })).toBeInTheDocument();
    expect(screen.getByText('EcoMind AI')).toBeInTheDocument();
  });

  it('renders a not-found page for unknown routes', async () => {
    renderAt('/does/not/exist');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});

describe('application routing (signed out)', () => {
  it('sends an anonymous visitor from a protected page to sign-in, remembering the page', async () => {
    const router = renderAt('/settings/system-status?tab=1');
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/sign-in');
    expect(router.state.location.state).toEqual({ from: '/settings/system-status?tab=1' });
    expect(fetchMock).not.toHaveBeenCalled(); // no hint, so no pointless refresh request
  });

  it('does not reveal whether an unknown route exists to anonymous visitors', async () => {
    const router = renderAt('/does/not/exist');
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/sign-in');
  });

  it('keeps public pages public', async () => {
    renderAt('/');
    expect(await screen.findByRole('heading', { level: 1, name: /Waste Management/ })).toBeInTheDocument();
  });
});

describe('application routing (stale session hint)', () => {
  it('falls back to sign-in when the refresh cookie is no longer valid', async () => {
    window.localStorage.setItem('ecomind.session-hint', '1');
    fetchMock.mockResolvedValue(
      Response.json({ error: { code: 'invalid_refresh_token', message: 'x', details: null, request_id: 'r' } }, { status: 401 }),
    );
    const router = renderAt('/dashboard');
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/sign-in');
    expect(window.localStorage.getItem('ecomind.session-hint')).toBeNull(); // hint cleared
  });
});
