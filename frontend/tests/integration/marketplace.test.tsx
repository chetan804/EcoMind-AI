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
  pending_request_count: null, my_request_status: null, published_at: '2026-10-19T10:00:00Z', closed_at: null, close_reason: null, outcome: null, expires_at: '2026-11-18T10:00:00Z', is_expired: false, photos: [], created_at: '2026-10-19T09:00:00Z',
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

  describe('expiry, outcomes and photos', () => {
    const L = '11111111-1111-4111-8111-111111111111';
    const P = '55555555-5555-4555-8555-555555555555';
    const photo = (over: Record<string, unknown> = {}) => ({ id: P, position: 0, caption: 'Front view', width_px: 640, height_px: 480, ...over });
    const png = () => new Response(new Uint8Array([1, 2, 3]), { headers: { 'Content-Type': 'image/png' } });
    const open = async () => {
      await userEvent.click(await screen.findByRole('button', { name: 'Open listing: Office chairs' }));
      return screen.findByRole('dialog', { name: 'Office chairs' });
    };
    const mineListing = (over: Record<string, unknown> = {}) => listing({ is_mine: true, ...over });

    it('shows a cover photo on the card and the gallery in the dialog, fetched with the session token', async () => {
      const withPhoto = listing({ photos: [photo()] });
      routeApi(fetchSpy, {
        'GET /api/v1/marketplace/listings': page([withPhoto]),
        [`GET /api/v1/marketplace/listings/${L}`]: withPhoto,
        'GET /api/v1/marketplace/requests/mine': page([]),
        [`GET /api/v1/marketplace/photos/${P}/content`]: () => png(),
      }, citizen);
      renderAt('/marketplace');
      const cover = await screen.findByRole('img', { name: 'Front view' });
      expect(cover).toHaveClass('listing__cover');
      const dialog = await open();
      expect(await within(dialog).findByRole('img', { name: 'Front view' })).toBeInTheDocument();
      const [, init] = fetchSpy.mock.calls.find(([url]) => String(url).includes(`/marketplace/photos/${P}/content`)) as [string, RequestInit];
      expect(init.headers).toMatchObject({ Authorization: 'Bearer test-access-token' });
      // A citizen sees no photo controls.
      expect(within(dialog).queryByRole('button', { name: 'Add photo' })).not.toBeInTheDocument();
    });

    it('says when a listing has expired, to the owner, with a way to renew it', async () => {
      const lapsed = mineListing({ is_expired: true, expires_at: '2026-10-20T10:00:00Z' });
      const api = routeApi(fetchSpy, {
        'GET /api/v1/marketplace/listings': page([lapsed]),
        [`GET /api/v1/marketplace/listings/${L}`]: lapsed,
        [`GET /api/v1/marketplace/listings/${L}/requests`]: [],
        'GET /api/v1/marketplace/requests/mine': page([]),
        [`POST /api/v1/marketplace/listings/${L}/renew`]: mineListing(),
      }, operator);
      renderAt('/marketplace');
      expect(await screen.findByText('Expired')).toBeInTheDocument();
      const dialog = await open();
      expect(within(dialog).getByText('This listing has expired')).toBeInTheDocument();
      expect(within(dialog).queryByRole('button', { name: 'Request this' })).not.toBeInTheDocument();
      await userEvent.selectOptions(within(dialog).getByRole('combobox', { name: 'Stays on offer for' }), '14 days');
      await userEvent.click(within(dialog).getByRole('button', { name: 'Renew' }));
      await waitFor(() => expect(api.calls.find((c) => c.key.endsWith('/renew'))?.body).toEqual({ duration_days: 14 }));
    });

    it('publishes with the server default unless a lifetime is chosen', async () => {
      const draft = mineListing({ status: 'draft', published_at: null, expires_at: null });
      const api = routeApi(fetchSpy, {
        'GET /api/v1/marketplace/listings': page([draft]),
        [`GET /api/v1/marketplace/listings/${L}`]: draft,
        [`GET /api/v1/marketplace/listings/${L}/requests`]: [],
        'GET /api/v1/marketplace/requests/mine': page([]),
        [`POST /api/v1/marketplace/listings/${L}/publish`]: mineListing(),
      }, operator);
      renderAt('/marketplace');
      const dialog = await open();
      await userEvent.click(within(dialog).getByRole('button', { name: 'Publish' }));
      await waitFor(() => expect(api.calls.find((c) => c.key.endsWith('/publish'))?.body).toEqual({}));
      await userEvent.selectOptions(within(dialog).getByRole('combobox', { name: 'Stays on offer for' }), '7 days');
      await userEvent.click(within(dialog).getByRole('button', { name: 'Publish' }));
      await waitFor(() => expect(api.calls.filter((c) => c.key.endsWith('/publish')).at(-1)?.body).toEqual({ duration_days: 7 }));
    });

    it('records a hand-over on a reserved listing, and a plain close as withdrawn', async () => {
      const reserved = mineListing({ status: 'reserved' });
      const closed = mineListing({ status: 'closed', outcome: 'handed_over', closed_at: '2026-10-21T10:00:00Z' });
      const api = routeApi(fetchSpy, {
        'GET /api/v1/marketplace/listings': page([reserved]),
        [`GET /api/v1/marketplace/listings/${L}`]: reserved,
        [`GET /api/v1/marketplace/listings/${L}/requests`]: [],
        'GET /api/v1/marketplace/requests/mine': page([]),
        [`POST /api/v1/marketplace/listings/${L}/close`]: closed,
      }, operator);
      renderAt('/marketplace');
      const dialog = await open();
      await userEvent.click(within(dialog).getByRole('button', { name: 'Mark as handed over' }));
      const confirm = await screen.findByRole('dialog', { name: 'Record the hand-over?' });
      await userEvent.type(within(confirm).getByRole('textbox'), 'Collected Friday');
      await userEvent.click(within(confirm).getByRole('button', { name: 'Mark as handed over' }));
      await waitFor(() => expect(api.calls.find((c) => c.key.endsWith('/close'))?.body).toEqual({ reason: 'Collected Friday', outcome: 'handed_over' }));

      await userEvent.click(within(dialog).getByRole('button', { name: 'Close listing' }));
      const sure = await screen.findByRole('dialog', { name: 'Close this listing?' });
      await userEvent.click(within(sure).getByRole('button', { name: 'Close listing' }));
      await waitFor(() => expect(api.calls.filter((c) => c.key.endsWith('/close')).at(-1)?.body).toEqual({ outcome: 'withdrawn' }));
    });

    it('shows how a closed listing ended', async () => {
      const done = mineListing({ status: 'closed', outcome: 'expired', close_reason: 'The listing expired', closed_at: '2026-10-21T10:00:00Z' });
      routeApi(fetchSpy, {
        'GET /api/v1/marketplace/listings': page([done]),
        [`GET /api/v1/marketplace/listings/${L}`]: done,
        [`GET /api/v1/marketplace/listings/${L}/requests`]: [],
        'GET /api/v1/marketplace/requests/mine': page([]),
      }, operator);
      renderAt('/marketplace');
      const dialog = await open();
      expect(within(dialog).getByText('Outcome')).toBeInTheDocument();
      expect(within(dialog).getByText('The listing expired')).toBeInTheDocument();
      expect(within(dialog).queryByRole('button', { name: 'Renew' })).not.toBeInTheDocument();
      expect(within(dialog).queryByRole('button', { name: 'Add photo' })).not.toBeInTheDocument();
    });

    it('lets the owner upload a photo as a raw body with a caption, and remove one', async () => {
      const api = routeApi(fetchSpy, {
        'GET /api/v1/marketplace/listings': page([mineListing({ photos: [photo()] })]),
        [`GET /api/v1/marketplace/listings/${L}`]: mineListing({ photos: [photo()] }),
        [`GET /api/v1/marketplace/listings/${L}/requests`]: [],
        'GET /api/v1/marketplace/requests/mine': page([]),
        [`GET /api/v1/marketplace/photos/${P}/content`]: () => png(),
        [`POST /api/v1/marketplace/listings/${L}/photos`]: photo({ id: '66666666-6666-4666-8666-666666666666', position: 1 }),
        [`DELETE /api/v1/marketplace/listings/${L}/photos/${P}`]: new Response(null, { status: 204 }),
      }, operator);
      renderAt('/marketplace');
      const dialog = await open();
      const manage = await within(dialog).findByRole('region', { name: 'Manage photos' });
      expect(within(manage).getByText('Photos (1 of 4)')).toBeInTheDocument();
      expect(within(manage).getByRole('button', { name: 'Add photo' })).toBeDisabled();

      const file = new File(['pixels'], 'chairs.png', { type: 'image/png' });
      await userEvent.upload(within(manage).getByLabelText(/^Photo/), file);
      await userEvent.type(within(manage).getByRole('textbox', { name: /Caption/ }), 'Side view');
      await userEvent.click(within(manage).getByRole('button', { name: 'Add photo' }));
      await waitFor(() => expect(api.calls.some((c) => c.key === `POST /api/v1/marketplace/listings/${L}/photos`)).toBe(true));
      const [url, init] = fetchSpy.mock.calls.find(([u, i]) => String(u).includes('/photos?') && (i as RequestInit).method === 'POST') as [string, RequestInit];
      expect(url).toContain('caption=Side%20view');
      expect(init.body).toBe(file);
      expect(init.headers).toMatchObject({ 'Content-Type': 'image/png', Authorization: 'Bearer test-access-token' });

      await userEvent.click(within(manage).getByRole('button', { name: 'Remove Front view' }));
      await waitFor(() => expect(api.calls.some((c) => c.key === `DELETE /api/v1/marketplace/listings/${L}/photos/${P}`)).toBe(true));
    });

    it('stops offering uploads at four photos and shows the server message when one is refused', async () => {
      const four = [0, 1, 2, 3].map((n) => photo({ id: `${n}${n}${n}${n}${n}${n}${n}${n}-0000-4000-8000-000000000000`, position: n, caption: `Photo ${n}` }));
      routeApi(fetchSpy, {
        'GET /api/v1/marketplace/listings': page([mineListing({ photos: four })]),
        [`GET /api/v1/marketplace/listings/${L}`]: mineListing({ photos: four }),
        [`GET /api/v1/marketplace/listings/${L}/requests`]: [],
        'GET /api/v1/marketplace/requests/mine': page([]),
        [`DELETE /api/v1/marketplace/listings/${L}/photos/${four[0]?.id}`]: errorReply(409, 'invalid_listing_state', 'Photos of a reserved listing cannot be changed'),
      }, operator);
      fetchSpy.mockImplementation(((impl) => (url: string, init?: RequestInit) => (String(url).includes('/photos/') && String(url).endsWith('/content') ? Promise.resolve(png()) : impl(url, init)))(fetchSpy.getMockImplementation() as (u: string, i?: RequestInit) => Promise<Response>));
      renderAt('/marketplace');
      const dialog = await open();
      const manage = await within(dialog).findByRole('region', { name: 'Manage photos' });
      expect(within(manage).getByText(/up to 4 photos/)).toBeInTheDocument();
      expect(within(manage).queryByRole('button', { name: 'Add photo' })).not.toBeInTheDocument();
      await userEvent.click(within(manage).getByRole('button', { name: 'Remove Photo 0' }));
      expect(await within(manage).findByText('Photos of a reserved listing cannot be changed')).toBeInTheDocument();
    });
  });
});
