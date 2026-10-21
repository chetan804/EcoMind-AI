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

const balance = (points: number) => ({ user_id: id(9), points, earned_points: points, impact_weight_kg: '10.000', entries: 1, points_per_kg: 10, basis: 'Points per kilogram.' });
const catalogItem = (over: Record<string, unknown> = {}) => ({
  id: id(1), name: 'Reusable bottle', description: 'Steel, 500 ml', points_cost: 100, stock_remaining: 4, valid_until: null, remaining_for_you: null, available: true, unavailable_reason: null, ...over,
});
const redemption = (over: Record<string, unknown> = {}) => ({
  id: id(2), user_id: id(9), user_name: null, user_email: null, item_id: id(1), item_name: 'Reusable bottle', points_spent: 100, code: 'K7M2P-9XQ4T', status: 'pending',
  created_at: '2026-10-20T08:00:00Z', fulfilled_at: null, note: null, cancelled_at: null, cancel_reason: null, ...over,
});
const item = (over: Record<string, unknown> = {}) => ({
  id: id(1), name: 'Reusable bottle', description: null, points_cost: 100, stock: 4, max_per_user: null, active: true, valid_until: null, redeemed_count: 2, pending_count: 1,
  created_at: '2026-10-19T09:00:00Z', updated_at: '2026-10-19T09:00:00Z', ...over,
});

const citizen = userWith(['rewards:read_own', 'rewards:redeem'], { roles: ['citizen'] });
const manager = userWith(['rewards:manage'], { roles: ['manager'] });
const entries = { 'GET /api/v1/rewards/me/entries': page([]) };

describe('rewards catalogue (citizen)', () => {
  it('lists staff-entered rewards, marks the ones that cannot be redeemed, and says why', async () => {
    routeApi(fetchSpy, {
      ...entries,
      'GET /api/v1/rewards/me/balance': balance(150),
      'GET /api/v1/rewards/catalog': page([
        catalogItem(),
        catalogItem({ id: id(3), name: 'Tote bag', points_cost: 400 }),
        catalogItem({ id: id(4), name: 'Plant', points_cost: 20, stock_remaining: 0, available: false, unavailable_reason: 'out_of_stock' }),
        catalogItem({ id: id(5), name: 'Mug', points_cost: 10, remaining_for_you: 0, available: false, unavailable_reason: 'limit_reached' }),
      ]),
    }, citizen);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Redeem' }));
    const list = await screen.findByRole('list', { name: 'Rewards' });
    expect(within(list).getByRole('button', { name: 'Redeem Reusable bottle' })).toBeEnabled();
    expect(within(list).getAllByText('4 left')).toHaveLength(3); // not the sold-out one
    expect(within(list).getByRole('button', { name: 'Redeem Tote bag' })).toBeDisabled();
    expect(within(list).getByText('250 more points needed')).toBeInTheDocument();
    expect(within(list).getByRole('button', { name: 'Redeem Plant' })).toBeDisabled();
    expect(within(list).getByText('Out of stock')).toBeInTheDocument();
    expect(within(list).getByRole('button', { name: 'Redeem Mug' })).toBeDisabled();
    expect(within(list).getByText(/reached the limit/)).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Reward items' })).not.toBeInTheDocument();
  });

  it('shows an honest empty state instead of inventing rewards', async () => {
    routeApi(fetchSpy, { ...entries, 'GET /api/v1/rewards/me/balance': balance(0), 'GET /api/v1/rewards/catalog': page([]) }, citizen);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Redeem' }));
    expect(await screen.findByRole('heading', { name: 'No rewards are on offer yet' })).toBeInTheDocument();
  });

  it('redeems with a request id, then shows the claim code', async () => {
    const api = routeApi(fetchSpy, {
      ...entries,
      'GET /api/v1/rewards/me/balance': balance(150),
      'GET /api/v1/rewards/catalog': page([catalogItem()]),
      [`POST /api/v1/rewards/catalog/${id(1)}/redeem`]: redemption(),
    }, citizen);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Redeem' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Redeem Reusable bottle' }));
    const dialog = screen.getByRole('dialog', { name: 'Redeem Reusable bottle' });
    expect(within(dialog).getByText('Balance after: 50 points.')).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Redeem for 100 points' }));
    const done = await screen.findByRole('dialog', { name: 'Reward redeemed' });
    expect(within(done).getByLabelText('Claim code')).toHaveTextContent('K7M2P-9XQ4T');
    const post = api.calls.find((c) => c.key.startsWith('POST'));
    expect(post?.body).toEqual({ client_request_id: expect.stringMatching(/^[0-9a-f-]{36}$/) });
  });

  it('a retry after a failure repeats the same request id; a new dialog gets a new one', async () => {
    let attempt = 0;
    const api = routeApi(fetchSpy, {
      ...entries,
      'GET /api/v1/rewards/me/balance': balance(500),
      'GET /api/v1/rewards/catalog': page([catalogItem()]),
      [`POST /api/v1/rewards/catalog/${id(1)}/redeem`]: () => (++attempt === 1 ? errorReply(409, 'reward_unavailable', 'This reward is out of stock') : redemption()),
    }, citizen);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Redeem' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Redeem Reusable bottle' }));
    await userEvent.click(screen.getByRole('button', { name: 'Redeem for 100 points' }));
    expect(await screen.findByText('This reward is out of stock')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Redeem for 100 points' }));
    await screen.findByRole('dialog', { name: 'Reward redeemed' });
    await userEvent.click(screen.getByRole('button', { name: 'Done' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Redeem Reusable bottle' }));
    await userEvent.click(screen.getByRole('button', { name: 'Redeem for 100 points' }));
    await waitFor(() => expect(api.calls.filter((c) => c.key.startsWith('POST'))).toHaveLength(3));
    const ids = api.calls.filter((c) => c.key.startsWith('POST')).map((c) => (c.body as { client_request_id: string }).client_request_id);
    expect(ids[0]).toBe(ids[1]);
    expect(ids[2]).not.toBe(ids[0]);
  });

  it('lists own redemptions with codes and cancels a pending one with an optional reason', async () => {
    const api = routeApi(fetchSpy, {
      ...entries,
      'GET /api/v1/rewards/me/balance': balance(0),
      'GET /api/v1/rewards/me/redemptions': page([
        redemption(),
        redemption({ id: id(6), item_name: 'Old mug', status: 'cancelled', code: 'ZZZZZ-22222', cancel_reason: 'Out of stock after all', cancelled_at: '2026-10-20T09:00:00Z' }),
        redemption({ id: id(7), item_name: 'Seeds', status: 'fulfilled', code: 'AAAAA-33333', fulfilled_at: '2026-10-20T10:00:00Z' }),
      ]),
      [`POST /api/v1/rewards/me/redemptions/${id(2)}/cancel`]: redemption({ status: 'cancelled' }),
    }, citizen);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'My redemptions' }));
    const table = await screen.findByRole('table', { name: 'My redemptions' });
    expect(within(table).getByText('K7M2P-9XQ4T')).toBeInTheDocument();
    expect(within(table).getByText('AAAAA-33333')).toBeInTheDocument();
    expect(within(table).queryByText('ZZZZZ-22222')).not.toBeInTheDocument();
    expect(within(table).getByText('Out of stock after all')).toBeInTheDocument();
    expect(within(table).getAllByRole('button', { name: /Cancel redemption of/ })).toHaveLength(1);
    await userEvent.click(within(table).getByRole('button', { name: 'Cancel redemption of Reusable bottle' }));
    const dialog = screen.getByRole('dialog', { name: 'Cancel Reusable bottle' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel redemption' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.startsWith('POST'))).toBe(true));
    expect(api.calls.find((c) => c.key.startsWith('POST'))?.body).toEqual({});
  });
});

describe('rewards catalogue (staff)', () => {
  it('creates a reward with validated fields and sends empty stock as unlimited', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/rewards/ledger/summary': { entries: 0, users: 0, points_issued: 0, points_removed: 0, net_points: 0, impact_weight_kg: '0.000' },
      'GET /api/v1/rewards/ledger': page([]),
      'GET /api/v1/rewards/items': page([]),
      'POST /api/v1/rewards/items': item(),
    }, manager);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Reward items' }));
    // Staff run the catalogue but hold no points of their own: no spending tabs.
    expect(screen.queryByRole('tab', { name: 'Redeem' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'My redemptions' })).not.toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'No rewards yet' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'New reward' }));
    const dialog = screen.getByRole('dialog', { name: 'New reward' });
    const add = within(dialog).getByRole('button', { name: 'Add reward' });
    expect(add).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Reusable bottle');
    await userEvent.type(within(dialog).getByLabelText('Cost in points'), '0');
    expect(add).toBeDisabled();
    expect(within(dialog).getByText(/A whole number from 1 to 1,000,000/)).toBeInTheDocument();
    await userEvent.clear(within(dialog).getByLabelText('Cost in points'));
    await userEvent.type(within(dialog).getByLabelText('Cost in points'), '100');
    await userEvent.type(within(dialog).getByLabelText(/Limit per person/), '2.5');
    expect(add).toBeDisabled();
    await userEvent.clear(within(dialog).getByLabelText(/Limit per person/));
    await userEvent.type(within(dialog).getByLabelText(/Limit per person/), '2');
    await userEvent.click(add);
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/rewards/items')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/rewards/items')?.body).toEqual({
      name: 'Reusable bottle', description: null, points_cost: 100, stock: null, max_per_user: 2, valid_until: null, active: true,
    });
  });

  it('switches a reward off instead of deleting it', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/rewards/ledger/summary': { entries: 0, users: 0, points_issued: 0, points_removed: 0, net_points: 0, impact_weight_kg: '0.000' },
      'GET /api/v1/rewards/ledger': page([]),
      'GET /api/v1/rewards/items': page([item()]),
      [`PATCH /api/v1/rewards/items/${id(1)}`]: item({ active: false }),
    }, manager);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Reward items' }));
    const table = await screen.findByRole('table', { name: 'Reward items' });
    expect(within(table).getByText('2 (1 waiting)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
    await userEvent.click(within(table).getByRole('button', { name: 'Switch off Reusable bottle' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.startsWith('PATCH'))).toBe(true));
    expect(api.calls.find((c) => c.key.startsWith('PATCH'))?.body).toEqual({ active: false });
  });

  it('hands a reward over by claim code, and cancelling needs a reason', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/rewards/ledger/summary': { entries: 0, users: 0, points_issued: 0, points_removed: 0, net_points: 0, impact_weight_kg: '0.000' },
      'GET /api/v1/rewards/ledger': page([]),
      'GET /api/v1/rewards/redemptions': page([redemption({ user_name: 'Asha Rao', user_email: 'asha@example.org' })]),
      [`POST /api/v1/rewards/redemptions/${id(2)}/fulfil`]: redemption({ status: 'fulfilled' }),
      [`POST /api/v1/rewards/redemptions/${id(2)}/cancel`]: redemption({ status: 'cancelled' }),
    }, manager);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Redemption queue' }));
    const table = await screen.findByRole('table', { name: 'Redemptions' });
    expect(api.calls.find((c) => c.key === 'GET /api/v1/rewards/redemptions')?.query.get('status')).toBe('pending');
    expect(within(table).getByText('asha@example.org')).toBeInTheDocument();

    await userEvent.click(within(table).getByRole('button', { name: 'Cancel K7M2P-9XQ4T' }));
    const cancel = screen.getByRole('dialog', { name: 'Cancel Reusable bottle' });
    const confirm = within(cancel).getByRole('button', { name: 'Cancel redemption' });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(cancel).getByLabelText('Reason (required)'), 'Item recalled');
    await userEvent.click(confirm);
    await waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/cancel'))).toBe(true));
    expect(api.calls.find((c) => c.key.endsWith('/cancel'))?.body).toEqual({ reason: 'Item recalled' });

    await userEvent.click(await within(await screen.findByRole('table', { name: 'Redemptions' })).findByRole('button', { name: 'Mark K7M2P-9XQ4T handed over' }));
    const hand = screen.getByRole('dialog', { name: 'Hand over Reusable bottle' });
    await userEvent.type(within(hand).getByLabelText('Note (optional)'), 'At the depot');
    await userEvent.click(within(hand).getByRole('button', { name: 'Mark as handed over' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/fulfil'))).toBe(true));
    expect(api.calls.find((c) => c.key.endsWith('/fulfil'))?.body).toEqual({ note: 'At the depot' });
    expect(await screen.findByText('Marked as handed over')).toBeInTheDocument(); // toast
  });

  it('filters the queue by status and claim code', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/rewards/ledger/summary': { entries: 0, users: 0, points_issued: 0, points_removed: 0, net_points: 0, impact_weight_kg: '0.000' },
      'GET /api/v1/rewards/ledger': page([]),
      'GET /api/v1/rewards/redemptions': page([]),
    }, manager);
    renderAt('/rewards');
    await userEvent.click(await screen.findByRole('tab', { name: 'Redemption queue' }));
    expect(await screen.findByRole('heading', { name: 'Nothing to hand over' })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'fulfilled');
    await waitFor(() => expect(api.calls.at(-1)?.query.get('status')).toBe('fulfilled'));
    await userEvent.type(screen.getByLabelText('Claim code'), 'k7m2p');
    await waitFor(() => expect(api.calls.at(-1)?.query.get('code')).toBe('k7m2p'));
  });
});
