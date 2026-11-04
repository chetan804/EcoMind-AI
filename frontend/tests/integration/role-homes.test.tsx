import { cleanup, screen, waitFor, within } from '@testing-library/react';
import roles from '../fixtures/role-permissions.json';
import { errorReply, page, routeApi } from '../helpers/api-mock';
import { overviewFixture } from '../helpers/fixtures';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

/**
 * What each of the five roles gets after signing in. The permissions come from the backend's own
 * catalog (`tests/fixtures/role-permissions.json`, checked by `scripts/quality/export_role_permissions.py`),
 * so a role that gains or loses a grant changes these tests. The server enforces access; this only
 * checks that the interface offers each person what they may use, and makes no request they may not.
 */
const fetchSpy = vi.fn();
const id = (n: number) => `${String(n).repeat(8)}-${String(n).repeat(4)}-4${String(n).repeat(3)}-8${String(n).repeat(3)}-${String(n).repeat(12)}`;

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

const roleUser = (role: keyof typeof roles) => userWith(roles[role], { roles: [role] });
const task = (over: Record<string, unknown> = {}) => ({
  id: id(3), waste_report_id: null, destination_facility_id: null, title: 'Collect skip', status: 'assigned', priority: 'high', address_text: 'Market Road',
  latitude: '17.4', longitude: '78.4', due_at: null, notes: null, created_by_id: id(9), assignment: null, collected_weight_kg: null,
  created_at: '2026-10-19T08:00:00Z', updated_at: '2026-10-19T08:00:00Z', ...over,
});
const apiPaths = (calls: { key: string }[]) => calls.map((c) => c.key.replace(/^GET /, ''));
const navLinks = () => within(screen.getByRole('navigation', { name: 'Main' })).queryAllByRole('link').map((a) => a.textContent ?? '');
const homeLink = (name: string) => within(screen.getByRole('main')).queryByRole('link', { name });

describe('role homes', () => {
  it('citizen: plain home, no data requests, no operational links', async () => {
    const api = routeApi(fetchSpy, {}, roleUser('citizen'));
    renderAt('/dashboard');
    expect(await screen.findByRole('heading', { level: 1, name: /Good (morning|afternoon|evening)/ })).toBeInTheDocument();
    expect(homeLink('Classify an item')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'My open tasks' })).not.toBeInTheDocument();
    for (const hidden of ['Collections', 'Analytics', 'User management', 'Review queue', 'Recovery']) {
      expect(navLinks()).not.toContain(hidden);
    }
    expect(api.calls).toEqual([]);
  });

  it('collector: own tasks card, mine=true, no analytics, no manager links', async () => {
    const api = routeApi(fetchSpy, { 'GET /api/v1/collection/tasks': page([task({ title: 'Pick-up at Market Road' })]) }, roleUser('collector'));
    renderAt('/dashboard');
    expect(await screen.findByRole('heading', { name: 'My open tasks' })).toBeInTheDocument();
    expect(await screen.findByText('Pick-up at Market Road')).toBeInTheDocument();
    expect(api.calls).toHaveLength(1);
    expect(api.calls[0]?.query.get('mine')).toBe('true');
    expect(apiPaths(api.calls).some((p) => p.includes('/analytics'))).toBe(false);
    expect(homeLink('Routes')).toBeInTheDocument();
    for (const hidden of ['Analytics', 'Forecasting', 'Anomalies', 'Review queue', 'Recovery']) {
      expect(navLinks()).not.toContain(hidden);
    }
  });

  it('collector: shows only assigned and in-progress tasks, never someone else\'s or finished ones', async () => {
    routeApi(fetchSpy, {
      'GET /api/v1/collection/tasks': page([
        task({ id: id(1), title: 'Assigned to me', status: 'assigned' }),
        task({ id: id(2), title: 'Underway', status: 'in_progress' }),
        task({ id: id(4), title: 'Already done', status: 'completed' }),
        task({ id: id(5), title: 'Waiting for a vehicle', status: 'pending' }),
      ]),
    }, roleUser('collector'));
    renderAt('/dashboard');
    expect(await screen.findByText('Assigned to me')).toBeInTheDocument();
    expect(screen.getByText('Underway')).toBeInTheDocument();
    expect(screen.queryByText('Already done')).not.toBeInTheDocument();
    expect(screen.queryByText('Waiting for a vehicle')).not.toBeInTheDocument();
  });

  it('collector: empty state', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/collection/tasks': page([]) }, roleUser('collector'));
    renderAt('/dashboard');
    expect(await screen.findByText('No tasks are assigned to you right now.')).toBeInTheDocument();
  });

  it('collector: loading state, then the list', async () => {
    let release: (value: Response) => void = () => undefined;
    routeApi(fetchSpy, {}, roleUser('collector'));
    const answer = fetchSpy.getMockImplementation() as (url: string, init?: RequestInit) => Promise<Response>;
    fetchSpy.mockImplementation((url: string, init?: RequestInit) =>
      String(url).includes('/collection/tasks') ? new Promise<Response>((resolve) => { release = resolve; }) : answer(url, init),
    );
    renderAt('/dashboard');
    expect(await screen.findByRole('heading', { name: 'My open tasks' })).toBeInTheDocument();
    expect(screen.queryByText('No tasks are assigned to you right now.')).not.toBeInTheDocument();
    release(Response.json(page([task({ title: 'Late arrival' })])));
    expect(await screen.findByText('Late arrival')).toBeInTheDocument();
  });

  it('collector: an API failure is shown, not hidden or replaced by an empty list', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/collection/tasks': errorReply(500, 'internal_error', 'Something went wrong') }, roleUser('collector'));
    renderAt('/dashboard');
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('No tasks are assigned to you right now.')).not.toBeInTheDocument();
  });

  it('facility operator: plain links to recovery work, no tasks card, no data or analytics requests', async () => {
    const api = routeApi(fetchSpy, {}, roleUser('facility_operator'));
    renderAt('/dashboard');
    expect(await screen.findByRole('heading', { level: 1, name: /Good (morning|afternoon|evening)/ })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'My open tasks' })).not.toBeInTheDocument();
    for (const shown of ['Recovery', 'Traceability', 'Review queue']) expect(homeLink(shown)).toBeInTheDocument();
    expect(navLinks()).not.toContain('Analytics');
    expect(api.calls).toEqual([]);
  });

  it('manager: operations overview from analytics, and no user-management access', async () => {
    const api = routeApi(fetchSpy, {}, roleUser('manager'));
    renderAt('/dashboard');
    await waitFor(() => expect(apiPaths(api.calls).length + api.unmatched.length).toBeGreaterThan(0));
    expect([...apiPaths(api.calls), ...api.unmatched].some((p) => p.includes('/analytics/overview'))).toBe(true);
    expect(screen.queryByRole('heading', { name: 'My open tasks' })).not.toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Analytics' })).toBeInTheDocument();
    expect(roles.manager).not.toContain('users:manage');
    expect([...api.unmatched].some((p) => p.includes('/access-requests'))).toBe(false);
  });

  it('the overview says so when the data is generated demonstration data, and only then', async () => {
    const withFlag = (flag: boolean) => ({ ...overviewFixture, contains_demonstration_data: flag });
    routeApi(fetchSpy, { 'GET /api/v1/analytics/overview': withFlag(true) }, roleUser('manager'));
    renderAt('/dashboard');
    expect(await screen.findByText('Demonstration data, not live')).toBeInTheDocument();
    expect(screen.getByText(/describe that sample, not real operations/)).toBeInTheDocument();
    cleanup();
    resetSession();
    routeApi(fetchSpy, { 'GET /api/v1/analytics/overview': withFlag(false) }, roleUser('manager'));
    renderAt('/dashboard');
    expect(await screen.findByText('Collected, 30 days')).toBeInTheDocument();
    expect(screen.queryByText('Demonstration data, not live')).not.toBeInTheDocument();
  });

  it('administrator: operations overview, and may read the role-request queue', async () => {
    const api = routeApi(fetchSpy, {}, roleUser('administrator'));
    renderAt('/dashboard');
    expect(await screen.findByRole('link', { name: 'Analytics' })).toBeInTheDocument();
    await waitFor(() => expect([...apiPaths(api.calls), ...api.unmatched].some((p) => p.includes('/analytics/overview'))).toBe(true));
    expect(roles.administrator).toContain('users:manage');
  });
});
