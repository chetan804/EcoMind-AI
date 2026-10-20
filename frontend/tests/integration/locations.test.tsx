import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { errorReply, page, routeApi } from '../helpers/api-mock';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const id = (n: number) => `${String(n).repeat(8)}-${String(n).repeat(4)}-4${String(n).repeat(3)}-8${String(n).repeat(3)}-${String(n).repeat(12)}`;

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

const zone = (over: Record<string, unknown> = {}) => ({
  id: id(5), code: 'Z-1', name: 'Zone 1 - Commercial', zone_type: 'commercial', description: 'Dense retail', is_active: true, facility_count: 2, ...over,
});
const manager = userWith(['facilities:read', 'facilities:manage'], { roles: ['manager'] });
const citizen = userWith(['facilities:read'], { roles: ['citizen'] });

describe('locations and zones', () => {
  it('lists zones with their facility counts, says there is no map, and hides management from read-only roles', async () => {
    const api = routeApi(fetchSpy, { 'GET /api/v1/zones': page([zone(), zone({ id: id(6), code: 'Z-2', name: 'Old Town', is_active: false, facility_count: 0 })]) }, citizen);
    renderAt('/locations');
    const table = await screen.findByRole('table', { name: 'Zones' });
    expect(within(table).getByText('Zone 1 - Commercial')).toBeInTheDocument();
    expect(within(table).getByText('Retired')).toBeInTheDocument();
    expect(screen.getByText(/no map boundaries/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add zone' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Edit / })).not.toBeInTheDocument();
    expect(api.unmatched).toEqual([]);
  });

  it('shows the facilities of a zone fetched by zone id', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/zones': page([zone()]),
      'GET /api/v1/facilities': page([{ id: id(4), code: 'DEP1', name: 'North Depot', facility_type: 'depot', status: 'active', city: 'Hyderabad', latitude: '17.4', longitude: '78.4' }]),
    }, citizen);
    renderAt('/locations');
    await userEvent.click(await screen.findByRole('button', { name: 'Show facilities in Zone 1 - Commercial' }));
    expect(await screen.findByRole('table', { name: 'Facilities in Zone 1 - Commercial' })).toBeInTheDocument();
    expect(api.calls.some((c) => c.key === 'GET /api/v1/facilities' && c.query.get('zone_id') === id(5))).toBe(true);
  });

  it('a manager adds a zone and sees the server message for a duplicate code', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/zones': page([]),
      'POST /api/v1/zones': errorReply(409, 'zone_code_taken', 'A zone with code Z-1 already exists'),
    }, manager);
    renderAt('/locations');
    await userEvent.click(await screen.findByRole('button', { name: 'Add zone' }));
    const dialog = screen.getByRole('dialog', { name: 'Add zone' });
    const submit = within(dialog).getByRole('button', { name: 'Add zone' });
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Code'), 'Z-1');
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Zone 1');
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'industrial');
    await userEvent.click(submit);
    expect(await within(dialog).findByText(/already exists/)).toBeInTheDocument();
    expect(api.calls.find((c) => c.key === 'POST /api/v1/zones')?.body).toMatchObject({ code: 'Z-1', name: 'Zone 1', zone_type: 'industrial', description: null });
  });

  it('a manager retires a zone: only changed-capable fields are sent and the code is immutable', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/zones': page([zone()]),
      [`PATCH /api/v1/zones/${id(5)}`]: zone({ is_active: false }),
    }, manager);
    renderAt('/locations');
    await userEvent.click(await screen.findByRole('button', { name: 'Edit Zone 1 - Commercial' }));
    const dialog = screen.getByRole('dialog', { name: 'Edit Zone 1 - Commercial' });
    expect(within(dialog).queryByLabelText('Code')).not.toBeInTheDocument();
    await userEvent.selectOptions(within(dialog).getByLabelText('Status'), 'false');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.startsWith('PATCH'))).toBe(true));
    const body = api.calls.find((c) => c.key.startsWith('PATCH'))?.body;
    expect(body).toMatchObject({ is_active: false });
    expect(body).not.toHaveProperty('code');
  });

  it('shows an explicit forbidden page without facilities:read', async () => {
    routeApi(fetchSpy, {}, userWith([]));
    renderAt('/locations');
    expect(await screen.findByRole('heading', { name: 'You do not have access to this page' })).toBeInTheDocument();
  });
});
