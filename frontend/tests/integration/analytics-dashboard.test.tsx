import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { errorReply, routeApi } from '../helpers/api-mock';
import { overviewFixture, trendFixture } from '../helpers/fixtures';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const manager = userWith(['analytics:read']);

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

describe('operations dashboard', () => {
  it('shows server-computed figures, and says plainly that there is no recovery rate yet', async () => {
    const api = routeApi(
      fetchSpy,
      { 'GET /api/v1/analytics/overview': overviewFixture, 'GET /api/v1/analytics/weekly-trend': trendFixture },
      manager,
    );
    renderAt('/dashboard');
    const kpis = await screen.findByRole('list', { name: 'Key metrics' });
    expect(within(kpis).getByText('37.5 kg')).toBeInTheDocument();
    expect(within(kpis).getByText('3')).toBeInTheDocument();
    expect(within(kpis).getByText('1 overdue')).toBeInTheDocument();
    expect(within(kpis).getByText('n/a')).toBeInTheDocument();
    expect(within(kpis).getByText('No verified records yet')).toBeInTheDocument();
    expect(await screen.findByRole('img', { name: /Weekly collected weight/ })).toBeInTheDocument();
    expect(api.calls.map((c) => c.key).sort()).toEqual(['GET /api/v1/analytics/overview', 'GET /api/v1/analytics/weekly-trend']);
    expect(api.calls.find((c) => c.key.endsWith('/overview'))?.query.get('window_days')).toBe('30');
    expect(document.body.textContent).not.toMatch(/demonstration data/i);
    expect(api.unmatched).toEqual([]);
  });

  it('reports a failed request with its reason and recovers on retry', async () => {
    let fail = true;
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/analytics/overview': () => (fail ? errorReply(500, 'internal_error', 'The server hiccuped.') : overviewFixture),
        'GET /api/v1/analytics/weekly-trend': trendFixture,
      },
      manager,
    );
    renderAt('/dashboard');
    expect(await screen.findByText('Could not load the operations overview')).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('list', { name: 'Key metrics' })).toBeInTheDocument();
  });
});

describe('executive analytics page', () => {
  it('requests the chosen window and renders breakdowns and the weekly table', async () => {
    const api = routeApi(
      fetchSpy,
      { 'GET /api/v1/analytics/overview': overviewFixture, 'GET /api/v1/analytics/weekly-trend': trendFixture },
      manager,
    );
    renderAt('/analytics');
    expect(await screen.findByRole('heading', { level: 1, name: 'Executive analytics' })).toBeInTheDocument();
    const fleet = await screen.findByRole('list', { name: 'Vehicles by status' });
    expect(within(fleet).getByText('Available')).toBeInTheDocument();
    const table = await screen.findByRole('table', { name: 'Weekly activity' });
    expect(within(table).getAllByRole('row')).toHaveLength(4);
    expect(screen.getByText(/open \(1 critical\)/)).toBeInTheDocument();
    expect(screen.getByText(/not confirmed incidents/)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('Reporting window'), '90');
    await vi.waitFor(() => expect(api.calls.some((c) => c.query.get('window_days') === '90')).toBe(true));
  });

  it('is forbidden without analytics:read and makes no analytics request', async () => {
    const api = routeApi(fetchSpy, {}, userWith(['collection:read']));
    renderAt('/analytics');
    expect(await screen.findByRole('heading', { name: 'You do not have access to this page' })).toBeInTheDocument();
    expect(api.calls).toEqual([]);
  });
});
