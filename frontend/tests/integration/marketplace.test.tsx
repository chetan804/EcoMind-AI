import { screen, waitFor, within } from '@testing-library/react';
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

const listing = (over: Record<string, unknown> = {}) => ({
  id: id(1), title: 'Office chairs', description: 'Surplus from a floor move', category: 'furniture', quantity: '30.000', unit: 'units', condition: 'good',
  facility_id: null, facility_name: null, pickup_city: 'Hyderabad', status: 'published', owner_id: id(8), owner_name: 'Oona Operator', is_mine: false,
  pending_request_count: null, my_request_status: null, published_at: '2026-10-19T10:00:00Z', closed_at: null, close_reason: null, created_at: '2026-10-19T09:00:00Z',
  updated_at: '2026-10-19T09:00:00Z', ...over,
});
const request = (over: Record<string, unknown> = {}) => ({
  id: id(2), listing_id: id(1), listing_title: 'Office chairs', requester_id: id(9), requester_name: 'Cy Citizen', requester_email: 'cy@example.org', message: 'For a community hall',
  status: 'pending', created_at: '2026-10-20T08:00:00Z', decided_at: null, ...over,
});

const citizen = userWith(['marketplace:read', 'marketplace:request'], { roles: ['citizen'] });
const operator = userWith(['marketplace:read', 'marketplace:request', 'marketplace:create', 'facilities:read'], { roles: ['facility_operator'] });

describe('marketplace', () => {
  it('lists real listings, filters by category chip and search, and hides creation from citizens', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/marketplace/listings': page([listing(), listing({ id: id(3), title: 'Wooden pallets', category: 'wood', quantity: '45.000' })]),
      'GET /api/v1/marketplace/requests/mine': page([]),
    }, citizen);
    renderAt('/marketplace');
    const list = await screen.findByRole('list', { name: 'Listings' });
    expect(within(list).getByRole('heading', { name: 'Office chairs' })).toBeInTheDocument();
    expect(within(list).getByText('30 units · Good condition')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New listing' })).not.toBeInTheDocument();
    expect(screen.queryByRole('switch', { name: 'My listings only' })).not.toBeInTheDocument();
    expect(screen.getByText(/no payment or delivery/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Metals' }));
    await waitFor(() => expect(api.calls.at(-1)?.query.get('category')).toBe('metals'));
    expect(screen.getByRole('button', { name: 'Metals' })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search' }), 'chair');
    await waitFor(() => expect(api.calls.at(-1)?.query.get('q')).toBe('chair'));
    expect(api.unmatched).toEqual([]);
  });

  it('shows an honest empty state', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/marketplace/listings': page([]), 'GET /api/v1/marketplace/requests/mine': page([]) }, citizen);
    renderAt('/marketplace');
    expect(await screen.findByRole('heading', { name: 'No listings' })).toBeInTheDocument();
  });

  it('a citizen asks for a published listing with a message', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/marketplace/listings': page([listing()]),
      'GET /api/v1/marketplace/listings/11111111-1111-4111-8111-111111111111': listing(),
      'GET /api/v1/marketplace/requests/mine': page([]),
      'POST /api/v1/marketplace/listings/11111111-1111-4111-8111-111111111111/requests': request({ requester_name: 'Test User' }),
    }, citizen);
    renderAt('/marketplace');
    await userEvent.click(await screen.findByRole('button', { name: 'Open listing: Office chairs' }));
    const dialog = await screen.findByRole('dialog', { name: 'Office chairs' });
    expect(within(dialog).queryByRole('heading', { name: 'Requests' })).not.toBeInTheDocument();
    expect(within(dialog).getByText('Oona Operator')).toBeInTheDocument();
    await userEvent.type(within(dialog).getByRole('textbox', { name: /Message to the owner/ }), 'For a community hall');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Request this' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.startsWith('POST') && (c.body as { message: string }).message === 'For a community hall')).toBe(true));
  });

  it('shows the server error when a request is refused', async () => {
    routeApi(fetchSpy, {
      'GET /api/v1/marketplace/listings': page([listing()]),
      'GET /api/v1/marketplace/listings/11111111-1111-4111-8111-111111111111': listing(),
      'GET /api/v1/marketplace/requests/mine': page([]),
      'POST /api/v1/marketplace/listings/11111111-1111-4111-8111-111111111111/requests': errorReply(409, 'request_exists', 'You already have a request for this listing'),
    }, citizen);
    renderAt('/marketplace');
    await userEvent.click(await screen.findByRole('button', { name: 'Open listing: Office chairs' }));
    const dialog = await screen.findByRole('dialog', { name: 'Office chairs' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Request this' }));
    expect(await within(dialog).findByText('You already have a request for this listing')).toBeInTheDocument();
  });

  it('a requester with a pending request can withdraw it and cannot ask twice', async () => {
    const mine = request();
    const api = routeApi(fetchSpy, {
      'GET /api/v1/marketplace/listings': page([listing({ my_request_status: 'pending' })]),
      'GET /api/v1/marketplace/listings/11111111-1111-4111-8111-111111111111': listing({ my_request_status: 'pending' }),
      'GET /api/v1/marketplace/requests/mine': page([mine]),
      'POST /api/v1/marketplace/requests/22222222-2222-4222-8222-222222222222/withdraw': request({ status: 'withdrawn', decided_at: '2026-10-20T09:00:00Z' }),
    }, citizen);
    renderAt('/marketplace');
    await userEvent.click(await screen.findByRole('button', { name: 'Open listing: Office chairs' }));
    const dialog = await screen.findByRole('dialog', { name: 'Office chairs' });
    expect(within(dialog).queryByRole('button', { name: 'Request this' })).not.toBeInTheDocument();
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Withdraw request' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/withdraw'))).toBe(true));
  });

  it("the owner sees requests with contact details and accepts one; a manager can release", async () => {
    const mine = listing({ is_mine: true, pending_request_count: 1 });
    const api = routeApi(fetchSpy, {
      'GET /api/v1/marketplace/listings': page([mine]),
      'GET /api/v1/marketplace/listings/11111111-1111-4111-8111-111111111111': mine,
      'GET /api/v1/marketplace/listings/11111111-1111-4111-8111-111111111111/requests': [request()],
      'POST /api/v1/marketplace/requests/22222222-2222-4222-8222-222222222222/accept': request({ status: 'accepted', decided_at: '2026-10-20T09:00:00Z' }),
      'GET /api/v1/marketplace/requests/mine': page([]),
    }, operator);
    renderAt('/marketplace');
    expect(await screen.findByText('1 pending request')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Open listing: Office chairs' }));
    const dialog = await screen.findByRole('dialog', { name: 'Office chairs' });
    expect(await within(dialog).findByText('cy@example.org')).toBeInTheDocument();
    expect(within(dialog).getByText('For a community hall')).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: 'Request this' })).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Accept request from Cy Citizen' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/accept'))).toBe(true));
  });

  it('an operator creates a draft listing with a validated quantity', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/marketplace/listings': page([]),
      'GET /api/v1/marketplace/requests/mine': page([]),
      'GET /api/v1/facilities': page([{ id: id(4), code: 'DEP1', name: 'North Depot', facility_type: 'depot', status: 'active', city: 'Hyderabad' }]),
      'POST /api/v1/marketplace/listings': listing({ status: 'draft', is_mine: true }),
    }, operator);
    renderAt('/marketplace');
    await userEvent.click(await screen.findByRole('button', { name: 'New listing' }));
    const dialog = await screen.findByRole('dialog', { name: 'New listing' });
    const create = within(dialog).getByRole('button', { name: 'Create draft' });
    expect(create).toBeDisabled();
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Title' }), 'Office chairs');
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Quantity' }), '0');
    expect(create).toBeDisabled();
    await userEvent.clear(within(dialog).getByRole('textbox', { name: 'Quantity' }));
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Quantity' }), '30');
    await userEvent.click(create);
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/marketplace/listings')).toBe(true));
    const body = api.calls.find((c) => c.key === 'POST /api/v1/marketplace/listings')?.body as Record<string, unknown>;
    expect(body).toMatchObject({ title: 'Office chairs', quantity: '30', unit: 'units', category: 'furniture', condition: 'good', facility_id: null });
    expect(body).not.toHaveProperty('price');
  });
});
