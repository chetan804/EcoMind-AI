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

const category = { id: id(1), code: 'glass', name: 'Glass', description: null, is_active: true, guidance_count: 1 };
const facility = { id: id(4), code: 'MRF1', name: 'City MRF', facility_type: 'processing_center', status: 'active', address_line: null, city: null, region: null, country_code: null, latitude: null, longitude: null, daily_capacity_kg: null, contact_email: null, zone_id: null };
const guidance = (over: Record<string, unknown> = {}) => ({
  id: id(2), material_category_id: id(1), category_code: 'glass', category_name: 'Glass', disposal_method: 'recycle', title: 'Rinse glass jars', instructions: 'Remove lids and rinse.',
  preparation_notes: null, source_reference: null, has_source: false, is_active: true, updated_at: '2026-10-01T00:00:00Z', ...over,
});

describe('sorting guide', () => {
  it('shows guidance with its source status, and an honest empty state', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/sorting-guide/guidance': page([guidance(), guidance({ id: id(3), title: 'Bottle banks', has_source: true, source_reference: 'City waste bylaw 12' })]) }, userWith(['sorting_guide:read']));
    renderAt('/sorting-guide');
    const unsourced = await screen.findByRole('article', { name: 'Rinse glass jars' }).catch(() => null);
    expect(unsourced ?? (await screen.findByText('Rinse glass jars'))).toBeTruthy();
    expect(screen.getByText(/No source cited/)).toBeInTheDocument();
    expect(screen.getByText('Source: City waste bylaw 12')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add guidance' })).not.toBeInTheDocument();
  });

  it('says nothing is published instead of inventing rules', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/sorting-guide/guidance': page([]) }, userWith(['sorting_guide:read']));
    renderAt('/sorting-guide');
    expect(await screen.findByText('No sorting guidance published')).toBeInTheDocument();
    expect(screen.getByText(/none is assumed here/)).toBeInTheDocument();
  });

  it('a manager adds guidance with a source', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/sorting-guide/guidance': page([]),
      'GET /api/v1/sorting-guide/categories': page([category]),
      'POST /api/v1/sorting-guide/guidance': guidance(),
    }, userWith(['sorting_guide:read', 'sorting_guide:manage']));
    renderAt('/sorting-guide');
    await userEvent.click(await screen.findByRole('button', { name: 'Add guidance' }));
    const dialog = screen.getByRole('dialog', { name: 'Add sorting guidance' });
    const submit = within(dialog).getByRole('button', { name: 'Add guidance' });
    expect(submit).toBeDisabled();
    await userEvent.selectOptions(await within(dialog).findByLabelText('Material'), id(1));
    await userEvent.type(within(dialog).getByLabelText('Title'), 'Rinse glass jars');
    await userEvent.type(within(dialog).getByLabelText('Instructions'), 'Remove lids and rinse.');
    await userEvent.type(within(dialog).getByLabelText(/^Source/), 'City waste bylaw 12');
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/sorting-guide/guidance')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/sorting-guide/guidance')?.body).toMatchObject({ material_category_id: id(1), disposal_method: 'recycle', source_reference: 'City waste bylaw 12' });
  });
});

const entry = (over: Record<string, unknown> = {}) => ({
  id: id(5), user_id: id(9), entry_type: 'earned', points: 375, impact_weight_kg: '37.500', source_type: 'collection_task', source_id: id(3), reverses_entry_id: null, created_by_id: null,
  description: 'Collection completed', created_at: '2026-10-19T10:00:00Z', ...over,
});

describe('rewards', () => {
  it('a resident sees their balance and basis, with no ledger tab', async () => {
    routeApi(fetchSpy, {
      'GET /api/v1/rewards/me/balance': { user_id: id(9), points: 375, earned_points: 375, impact_weight_kg: '37.500', entries: 1, points_per_kg: 10, basis: 'Points are awarded per kilogram of verified collection.' },
      'GET /api/v1/rewards/me/entries': page([entry()]),
    }, userWith(['rewards:read_own']));
    renderAt('/rewards');
    expect(await screen.findByText('375')).toBeInTheDocument();
    expect(screen.getByText('Points are awarded per kilogram of verified collection.')).toBeInTheDocument();
    expect(screen.getByText('+375')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Ledger' })).not.toBeInTheDocument();
    expect(screen.getByText(/Staff decide what they can be spent on/)).toBeInTheDocument();
  });

  it('a manager adjusts points with bounds, and reverses an entry with a reason', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/rewards/ledger/summary': { entries: 1, users: 1, points_issued: 375, points_removed: 0, net_points: 375, impact_weight_kg: '37.500' },
      'GET /api/v1/rewards/ledger': page([entry()]),
      'GET /api/v1/admin/users': page([{ id: id(9), full_name: 'Asha Rao', email: 'asha@example.org' }]),
      'POST /api/v1/rewards/adjustments': entry({ entry_type: 'adjustment', points: -50 }),
      [`POST /api/v1/rewards/entries/${id(5)}/reverse`]: entry({ entry_type: 'reversal', points: -375 }),
    }, userWith(['rewards:manage']));
    renderAt('/rewards');
    expect(await screen.findByRole('table', { name: 'Ledger entries' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Adjust points' }));
    const dialog = screen.getByRole('dialog', { name: 'Adjust points' });
    const submit = within(dialog).getByRole('button', { name: 'Record adjustment' });
    await userEvent.selectOptions(await within(dialog).findByLabelText('Person'), id(9));
    await userEvent.type(within(dialog).getByLabelText(/^Points/), '100001');
    await userEvent.type(within(dialog).getByLabelText('Reason'), 'Correction');
    expect(submit).toBeDisabled();
    expect(within(dialog).getByText(/up to 100,000 either way/)).toBeInTheDocument();
    await userEvent.clear(within(dialog).getByLabelText(/^Points/));
    await userEvent.type(within(dialog).getByLabelText(/^Points/), '-50');
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/rewards/adjustments')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/rewards/adjustments')?.body).toEqual({ user_id: id(9), points: -50, description: 'Correction' });

    await userEvent.click(screen.getByRole('button', { name: 'Reverse entry of +375 points' }));
    const reverse = screen.getByRole('dialog', { name: 'Reverse ledger entry' });
    const confirm = within(reverse).getByRole('button', { name: 'Reverse entry' });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(reverse).getByLabelText('Reason (required)'), 'Duplicate award');
    await userEvent.click(confirm);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/reverse'))).toBe(true));
    expect(api.calls.find((c) => c.key.endsWith('/reverse'))?.body).toEqual({ reason: 'Duplicate award' });
  });
});

const record = (over: Record<string, unknown> = {}) => ({
  id: id(6), facility_id: id(4), material_category_id: id(1), collection_task_id: null, recovery_method: 'recycled', input_weight_kg: '100.000', recovered_weight_kg: '80.000',
  processed_at: '2026-10-18T10:00:00Z', verification_status: 'pending', verified_at: null, notes: null, ...over,
});
const recoveryUser = userWith(['circular_economy:read', 'circular_economy:manage', 'circular_economy:verify', 'facilities:read', 'sorting_guide:read']);

describe('material recovery', () => {
  const baseRoutes = {
    'GET /api/v1/circular-economy/recovery-records/summary': { verified_records: 2, input_weight_kg: '200.000', recovered_weight_kg: '150.000', recovery_rate: '0.75', pending_records: 1, rejected_records: 0, by_category: [], by_method: [], basis: 'Verified records only.' },
    'GET /api/v1/facilities': page([facility]),
    'GET /api/v1/sorting-guide/categories': page([category]),
  };

  it('shows the verified recovery rate and says when it is unavailable', async () => {
    routeApi(fetchSpy, { ...baseRoutes, 'GET /api/v1/circular-economy/recovery-records': page([record()]) }, recoveryUser);
    renderAt('/recovery');
    expect(await screen.findByText('75.0%')).toBeInTheDocument();
    expect(screen.getByText('Verified records only.')).toBeInTheDocument();
    expect(within(await screen.findByRole('table', { name: 'Recovery records' })).getByText('City MRF')).toBeInTheDocument();
  });

  it('shows "Not available" when there is no verified input', async () => {
    routeApi(fetchSpy, {
      ...baseRoutes,
      'GET /api/v1/circular-economy/recovery-records/summary': { verified_records: 0, input_weight_kg: '0', recovered_weight_kg: '0', recovery_rate: null, pending_records: 0, rejected_records: 0, by_category: [], by_method: [] },
      'GET /api/v1/circular-economy/recovery-records': page([]),
    }, recoveryUser);
    renderAt('/recovery');
    expect(await screen.findByText('Not available')).toBeInTheDocument();
  });

  it('refuses recovered weight above the processed weight, and surfaces self-verification refusal', async () => {
    const api = routeApi(fetchSpy, {
      ...baseRoutes,
      'GET /api/v1/circular-economy/recovery-records': page([record()]),
      'POST /api/v1/circular-economy/recovery-records': record(),
      [`POST /api/v1/circular-economy/recovery-records/${id(6)}/verify`]: errorReply(403, 'self_verification_forbidden', 'You cannot verify a record you created.'),
    }, recoveryUser);
    renderAt('/recovery');
    await userEvent.click(await screen.findByRole('button', { name: 'Record recovery' }));
    const dialog = screen.getByRole('dialog', { name: 'Record recovery' });
    await userEvent.selectOptions(await within(dialog).findByLabelText('Facility'), id(4));
    await userEvent.selectOptions(await within(dialog).findByLabelText('Material'), id(1));
    await userEvent.type(within(dialog).getByLabelText('Processed on'), '2026-10-18T10:00');
    await userEvent.type(within(dialog).getByLabelText('Weight processed (kg)'), '50');
    await userEvent.type(within(dialog).getByLabelText('Weight recovered (kg)'), '60');
    const submit = within(dialog).getByRole('button', { name: 'Record recovery' });
    expect(submit).toBeDisabled();
    expect(within(dialog).getByText(/cannot be negative or more than the weight processed/)).toBeInTheDocument();
    await userEvent.clear(within(dialog).getByLabelText('Weight recovered (kg)'));
    await userEvent.type(within(dialog).getByLabelText('Weight recovered (kg)'), '40');
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/circular-economy/recovery-records')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/circular-economy/recovery-records')?.body).toMatchObject({ input_weight_kg: '50', recovered_weight_kg: '40', facility_id: id(4) });

    await userEvent.click(await screen.findByRole('button', { name: /^Verify record: Glass/ }));
    const verify = screen.getByRole('dialog', { name: 'Verify recovery record' });
    await userEvent.click(within(verify).getByRole('button', { name: 'Save decision' }));
    expect(await within(verify).findByText('You cannot verify a record you created.')).toBeInTheDocument();
  });
});

const passport = (over: Record<string, unknown> = {}) => ({
  id: id(7), passport_code: 'MP-ABC1234567', material_category_id: id(1), status: 'active', description: 'Glass batch', weight_kg: '120.000', origin_collection_task_id: null,
  recovery_record_id: null, current_facility_id: null, created_at: '2026-10-17T10:00:00Z', ...over,
});
const events = (types: string[]) => types.map((t, i) => ({ id: id(i + 1), sequence: i + 1, event_type: t, occurred_at: `2026-10-17T1${i}:00:00Z`, from_facility_id: null, to_facility_id: t === 'received' ? id(4) : null, notes: null }));
const passportUser = userWith(['passports:read', 'passports:manage', 'facilities:read', 'sorting_guide:read', 'circular_economy:read']);

describe('chain-of-custody passports', () => {
  const routes = (detail: unknown) => ({
    'GET /api/v1/material-passports': page([passport()]),
    [`GET /api/v1/material-passports/${id(7)}`]: detail,
    'GET /api/v1/facilities': page([facility]),
    'GET /api/v1/sorting-guide/categories': page([category]),
    'GET /api/v1/circular-economy/recovery-records': page([]),
  });

  it('offers only the custody events the state machine allows next', async () => {
    routeApi(fetchSpy, routes({ ...passport(), events: events(['created', 'collected']) }), passportUser);
    renderAt('/passports');
    await userEvent.click(await screen.findByRole('button', { name: 'Open passport MP-ABC1234567' }));
    const dialog = await screen.findByRole('dialog', { name: 'Passport' });
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Record custody event' }));
    const form = screen.getByRole('dialog', { name: 'Record custody event' });
    const options = within(within(form).getByLabelText('Event')).getAllByRole('option').map((o) => o.getAttribute('value'));
    expect(options).toEqual(['transferred', 'received']);
    expect(within(form).queryByLabelText('Event')?.getAttribute('value')).toBeDefined();
  });

  it('requires a destination facility for a received event and sends it', async () => {
    const api = routeApi(fetchSpy, { ...routes({ ...passport(), events: events(['created', 'collected']) }), [`POST /api/v1/material-passports/${id(7)}/events`]: {} }, passportUser);
    renderAt('/passports');
    await userEvent.click(await screen.findByRole('button', { name: 'Open passport MP-ABC1234567' }));
    const dialog = await screen.findByRole('dialog', { name: 'Passport' });
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Record custody event' }));
    const form = screen.getByRole('dialog', { name: 'Record custody event' });
    await userEvent.selectOptions(within(form).getByLabelText('Event'), 'received');
    const submit = within(form).getByRole('button', { name: 'Record event' });
    expect(submit).toBeDisabled();
    await userEvent.selectOptions(await within(form).findByLabelText('To facility'), id(4));
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/events'))).toBe(true));
    expect(api.calls.find((c) => c.key.endsWith('/events'))?.body).toMatchObject({ event_type: 'received', to_facility_id: id(4) });
  });

  it('a closed passport takes no more events; the integrity check reports problems honestly', async () => {
    routeApi(fetchSpy, {
      ...routes({ ...passport({ status: 'recovered' }), events: events(['created', 'received', 'processed', 'verified']) }),
      [`GET /api/v1/material-passports/${id(7)}/integrity`]: { passport_code: 'MP-ABC1234567', valid: false, events: 4, problems: ['Event 3 is out of time order.'], basis: 'Consistency check only, not cryptographic proof.' },
    }, passportUser);
    renderAt('/passports');
    await userEvent.click(await screen.findByRole('button', { name: 'Open passport MP-ABC1234567' }));
    const dialog = await screen.findByRole('dialog', { name: 'Passport' });
    expect(within(dialog).queryByRole('button', { name: 'Record custody event' })).not.toBeInTheDocument();
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Check integrity' }));
    expect(await within(dialog).findByText('Chain has problems')).toBeInTheDocument();
    expect(within(dialog).getByText('Event 3 is out of time order.')).toBeInTheDocument();
    expect(within(dialog).getByText(/not cryptographic proof/)).toBeInTheDocument();
  });
});
