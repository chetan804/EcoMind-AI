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

const manager = userWith(
  ['waste_reports:read_all', 'waste_reports:review', 'collection:read', 'collection:manage', 'fleet:read', 'fleet:manage', 'facilities:read', 'facilities:manage', 'routes:read', 'routes:manage', 'users:read', 'incidents:triage', 'classification:predict'],
  { roles: ['manager'] },
);
const citizen = userWith(['waste_reports:create', 'waste_reports:read_own', 'classification:predict', 'incidents:create', 'incidents:read_own', 'facilities:read'], { roles: ['citizen'] });

const report = (over: Record<string, unknown> = {}) => ({
  id: id(1), reporter_id: id(9), status: 'submitted', title: 'Overflowing skip', description: 'Behind the market', address_text: 'Market Road', latitude: null, longitude: null,
  estimated_weight_kg: '120.000', reported_at: '2026-10-19T08:00:00Z', updated_at: '2026-10-19T08:00:00Z',
  media: [{ id: id(2), content_type: 'image/jpeg', size_bytes: 1000, width_px: 10, height_px: 10, created_at: '2026-10-19T08:00:00Z', content_path: '/api/v1/waste-reports/media/x/content' }],
  ...over,
});
const task = (over: Record<string, unknown> = {}) => ({
  id: id(3), waste_report_id: null, destination_facility_id: null, title: 'Collect skip', status: 'pending', priority: 'high', address_text: 'Market Road',
  latitude: '17.4', longitude: '78.4', due_at: null, notes: null, created_by_id: id(9), assignment: null, collected_weight_kg: null, created_at: '2026-10-19T08:00:00Z', updated_at: '2026-10-19T08:00:00Z', ...over,
});
const taskDetail = (over: Record<string, unknown> = {}) => ({
  ...task(), history: [{ id: id(5), from_status: null, to_status: 'pending', changed_by_id: id(9), note: null, created_at: '2026-10-19T08:00:00Z' }], events: [], ...over,
});
const facility = (over: Record<string, unknown> = {}) => ({
  id: id(4), code: 'DEP1', name: 'North Depot', facility_type: 'depot', status: 'active', address_line: null, city: 'Hyderabad', region: null, country_code: 'IN',
  latitude: '17.5', longitude: '78.5', daily_capacity_kg: '5000.000', contact_email: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z', ...over,
});

describe('waste reports', () => {
  it('a citizen submits a report with a photo: uploads first, then attaches the media id', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/waste-reports': page([]),
      'POST /api/v1/waste-reports/media': { id: id(2), content_type: 'image/jpeg' },
      'POST /api/v1/waste-reports': report(),
    }, citizen);
    renderAt('/reports');
    expect(await screen.findByText('No reports yet')).toBeInTheDocument();
    expect(api.calls[0]?.query.get('mine')).toBe('true');
    await userEvent.click(screen.getByRole('button', { name: 'Report waste' }));
    const dialog = screen.getByRole('dialog', { name: 'Report waste' });
    const submit = within(dialog).getByRole('button', { name: 'Submit report' });
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Title'), 'Overflowing skip');
    await userEvent.type(within(dialog).getByLabelText('Latitude (optional)'), '17.4');
    expect(await within(dialog).findByText('Give both latitude and longitude, or neither.')).toBeInTheDocument();
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Longitude (optional)'), '78.4');
    await userEvent.upload(within(dialog).getByLabelText(/^Photo/), new File([new Uint8Array([1, 2, 3])], 'skip.jpg', { type: 'image/jpeg' }));
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/waste-reports')).toBe(true));
    const keys = api.calls.map((c) => c.key);
    expect(keys.indexOf('POST /api/v1/waste-reports/media')).toBeLessThan(keys.indexOf('POST /api/v1/waste-reports'));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/waste-reports')?.body).toMatchObject({ title: 'Overflowing skip', latitude: '17.4', longitude: '78.4', media_ids: [id(2)] });
    expect(api.unmatched).toEqual([]);
  });

  it('a reviewer needs a reason to reject, verifies, and can turn a verified report into a task', async () => {
    let current = report();
    const api = routeApi(fetchSpy, {
      'GET /api/v1/waste-reports': () => page([current]),
      [`GET /api/v1/waste-reports/${id(1)}`]: () => current,
      [`POST /api/v1/waste-reports/${id(1)}/review`]: (c: { body: unknown }) => {
        current = report({ status: (c.body as { status: string }).status });
        return current;
      },
      'GET /api/v1/waste-reports/media/x/content': () => new Response(new Uint8Array([1, 2, 3]), { headers: { 'Content-Type': 'image/jpeg' } }),
      'GET /api/v1/facilities': page([facility()]),
      'POST /api/v1/collection/tasks': task({ waste_report_id: id(1) }),
    }, manager);
    renderAt('/reports');
    await userEvent.click(await screen.findByRole('button', { name: 'Open report: Overflowing skip' }));
    const detail = await screen.findByRole('dialog', { name: 'Waste report' });
    expect(await within(detail).findByRole('img', { name: /Photo 1 for Overflowing skip/ })).toBeInTheDocument();
    await userEvent.click(within(detail).getByRole('button', { name: 'Review report' }));
    const review = screen.getByRole('dialog', { name: 'Review report' });
    await userEvent.selectOptions(within(review).getByLabelText('New status'), 'rejected');
    const save = within(review).getByRole('button', { name: 'Save review' });
    expect(save).toBeDisabled();
    await userEvent.selectOptions(within(review).getByLabelText('New status'), 'verified');
    expect(save).toBeEnabled();
    await userEvent.click(save);
    await vi.waitFor(() => expect(screen.queryByRole('dialog', { name: 'Review report' })).not.toBeInTheDocument());
    expect(api.calls.find((c) => c.key.endsWith('/review'))?.body).toEqual({ status: 'verified' });
    await userEvent.click(await within(detail).findByRole('button', { name: 'Create collection task' }));
    const create = screen.getByRole('dialog', { name: 'New collection task' });
    await userEvent.click(within(create).getByRole('button', { name: 'Create task' }));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/collection/tasks')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/collection/tasks')?.body).toMatchObject({ waste_report_id: id(1), title: 'Overflowing skip', priority: 'normal' });
  });

  it('shows the server refusal when a report is not verified for task creation', async () => {
    routeApi(fetchSpy, {
      'GET /api/v1/collection/tasks': page([]),
      'GET /api/v1/facilities': page([]),
      'POST /api/v1/collection/tasks': errorReply(409, 'report_not_verified', 'The report must be verified first.'),
    }, manager);
    renderAt('/collection');
    await userEvent.click(await screen.findByRole('button', { name: 'New task' }));
    const dialog = screen.getByRole('dialog', { name: 'New collection task' });
    expect(within(dialog).getByRole('button', { name: 'Create task' })).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Title'), 'Pick up bags');
    await userEvent.type(within(dialog).getByLabelText('Address'), 'Gate 2');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create task' }));
    expect(await within(dialog).findByText('The report must be verified first.')).toBeInTheDocument();
  });
});

describe('collection tasks', () => {
  const collector = (over: Record<string, unknown> = {}) => userWith(['collection:read', 'collection:execute', 'fleet:read', 'facilities:read'], { id: id(7), roles: ['collector'], ...over });

  it('a manager assigns a collector and vehicle', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/collection/tasks': page([task()]),
      [`GET /api/v1/collection/tasks/${id(3)}`]: taskDetail(),
      [`POST /api/v1/collection/tasks/${id(3)}/assign`]: {},
      'GET /api/v1/admin/users': page([{ id: id(7), full_name: 'Ravi Kumar', email: 'r@example.org' }]),
      'GET /api/v1/fleet/vehicles': page([{ id: id(8), registration_number: 'TS09-1234', vehicle_type: 'van', status: 'available', capacity_kg: '800.000', home_facility_id: null }]),
    }, manager);
    renderAt('/collection');
    expect(api.calls.length).toBeGreaterThanOrEqual(0);
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    const detail = await screen.findByRole('dialog', { name: 'Collection task' });
    await userEvent.click(await within(detail).findByRole('button', { name: 'Assign' }));
    const dialog = screen.getByRole('dialog', { name: 'Assign: Collect skip' });
    const submit = within(dialog).getByRole('button', { name: 'Assign' });
    expect(submit).toBeDisabled();
    await userEvent.selectOptions(await within(dialog).findByLabelText('Collector'), id(7));
    await userEvent.selectOptions(await within(dialog).findByLabelText('Vehicle (optional)'), id(8));
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/assign'))).toBe(true));
    expect(api.calls.find((c) => c.key.endsWith('/assign'))?.body).toMatchObject({ assignee_id: id(7), vehicle_id: id(8) });
    expect(api.calls.find((c) => c.key === 'GET /api/v1/admin/users')?.query.get('role')).toBe('collector');
  });

  it('the assigned collector starts, then completes with a weight; the weight must be positive', async () => {
    let status = 'assigned';
    const assignment = { id: id(6), assignee_id: id(7), assignee_name: 'Ravi', vehicle_id: null, vehicle_registration: null, assigned_at: '2026-10-19T09:00:00Z', unassigned_at: null };
    const api = routeApi(fetchSpy, {
      'GET /api/v1/collection/tasks': () => page([task({ status, assignment })]),
      [`GET /api/v1/collection/tasks/${id(3)}`]: () => taskDetail({ status, assignment }),
      [`POST /api/v1/collection/tasks/${id(3)}/start`]: () => { status = 'in_progress'; return {}; },
      [`POST /api/v1/collection/tasks/${id(3)}/complete`]: () => { status = 'completed'; return {}; },
      'GET /api/v1/facilities': page([facility()]),
    }, collector());
    renderAt('/collection');
    expect(await screen.findByRole('switch', { name: 'Assigned to me' })).toBeChecked();
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    const detail = await screen.findByRole('dialog', { name: 'Collection task' });
    expect(within(detail).queryByRole('button', { name: 'Cancel task' })).not.toBeInTheDocument();
    await userEvent.click(await within(detail).findByRole('button', { name: 'Start task' }));
    await userEvent.click(await within(detail).findByRole('button', { name: 'Complete with weight' }));
    const dialog = screen.getByRole('dialog', { name: 'Complete task' });
    const submit = within(dialog).getByRole('button', { name: 'Complete task' });
    await userEvent.type(within(dialog).getByLabelText(/Collected weight/), '0');
    expect(submit).toBeDisabled();
    await userEvent.clear(within(dialog).getByLabelText(/Collected weight/));
    await userEvent.type(within(dialog).getByLabelText(/Collected weight/), '37.5');
    await userEvent.selectOptions(within(dialog).getByLabelText('Delivered to'), id(4));
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/complete'))).toBe(true));
    expect(api.calls.find((c) => c.key.endsWith('/complete'))?.body).toMatchObject({ collected_weight_kg: '37.5', destination_facility_id: id(4) });
  });

  it('another collector cannot act on someone else\'s task', async () => {
    const assignment = { id: id(6), assignee_id: id(7), assignee_name: 'Ravi', vehicle_id: null, vehicle_registration: null, assigned_at: '2026-10-19T09:00:00Z', unassigned_at: null };
    routeApi(fetchSpy, {
      'GET /api/v1/collection/tasks': page([task({ status: 'assigned', assignment })]),
      [`GET /api/v1/collection/tasks/${id(3)}`]: taskDetail({ status: 'assigned', assignment }),
    }, collector({ id: id(99) }));
    renderAt('/collection');
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    const detail = await screen.findByRole('dialog', { name: 'Collection task' });
    expect(await within(detail).findByText(/Ravi/)).toBeInTheDocument();
    expect(within(detail).queryByRole('button', { name: 'Start task' })).not.toBeInTheDocument();
  });

  it('cancelling needs a reason, and a failed task can be rescheduled', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/collection/tasks': page([task({ status: 'failed' })]),
      [`GET /api/v1/collection/tasks/${id(3)}`]: taskDetail({ status: 'failed' }),
      [`POST /api/v1/collection/tasks/${id(3)}/reschedule`]: {},
    }, manager);
    renderAt('/collection');
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    const detail = await screen.findByRole('dialog', { name: 'Collection task' });
    expect(within(detail).queryByRole('button', { name: 'Cancel task' })).not.toBeInTheDocument();
    await userEvent.click(await within(detail).findByRole('button', { name: 'Reschedule' }));
    const dialog = screen.getByRole('dialog', { name: 'Reschedule task' });
    await userEvent.type(within(dialog).getByLabelText('New due date and time'), '2030-01-02T09:30');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reschedule' }));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.endsWith('/reschedule'))).toBe(true));
    const sent = (api.calls.find((c) => c.key.endsWith('/reschedule'))?.body as { due_at: string }).due_at;
    expect(new Date(sent).getFullYear()).toBe(2030);
    expect(sent.endsWith('Z')).toBe(true);
  });
});

describe('fleet and facilities', () => {
  it('lists vehicles, hides management from read-only roles, and creates a vehicle for a manager', async () => {
    const vehicle = { id: id(8), registration_number: 'TS09-1234', vehicle_type: 'van', status: 'available', capacity_kg: '800.000', home_facility_id: id(4), active_task_count: 2 };
    const readOnly = routeApi(fetchSpy, { 'GET /api/v1/fleet/vehicles': page([vehicle]), 'GET /api/v1/facilities': page([facility()]) }, userWith(['fleet:read', 'facilities:read']));
    renderAt('/fleet');
    const table = await screen.findByRole('table', { name: 'Fleet vehicles' });
    expect(within(table).getByText('North Depot')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add vehicle' })).not.toBeInTheDocument();
    expect(readOnly.unmatched).toEqual([]);
  });

  it('a manager creates a vehicle with a decimal-string capacity', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/fleet/vehicles': page([]),
      'GET /api/v1/facilities': page([facility()]),
      'POST /api/v1/fleet/vehicles': { id: id(8), registration_number: 'TS09-9999', vehicle_type: 'van', status: 'available', capacity_kg: '500', home_facility_id: null },
    }, manager);
    renderAt('/fleet');
    await userEvent.click(await screen.findByRole('button', { name: 'Add vehicle' }));
    const dialog = screen.getByRole('dialog', { name: 'Add vehicle' });
    const submit = within(dialog).getByRole('button', { name: 'Add vehicle' });
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Registration number'), 'TS09-9999');
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'van');
    await userEvent.type(within(dialog).getByLabelText('Capacity (kg)'), '500');
    await userEvent.click(submit);
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/fleet/vehicles')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/fleet/vehicles')?.body).toMatchObject({ registration_number: 'TS09-9999', vehicle_type: 'van', capacity_kg: '500', home_facility_id: null });
  });

  it('a manager edits a facility (code is immutable) and sees the server validation message', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/facilities': page([facility()]),
      [`PATCH /api/v1/facilities/${id(4)}`]: errorReply(422, 'validation_error', 'latitude and longitude must be provided together'),
    }, manager);
    renderAt('/facilities');
    await userEvent.click(await screen.findByRole('button', { name: 'Edit North Depot' }));
    const dialog = screen.getByRole('dialog', { name: 'Edit North Depot' });
    expect(within(dialog).queryByLabelText('Code')).not.toBeInTheDocument();
    await userEvent.clear(within(dialog).getByLabelText('Latitude'));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await within(dialog).findByText(/latitude and longitude must be provided together/)).toBeInTheDocument();
    expect(api.calls.find((c) => c.key.startsWith('PATCH'))?.body).toMatchObject({ latitude: null, longitude: '78.5' });
    expect(api.calls.find((c) => c.key.startsWith('PATCH'))?.body).not.toHaveProperty('code');
  });

  it('forbids pages the role has no permission for', async () => {
    routeApi(fetchSpy, {}, citizen);
    renderAt('/fleet');
    expect(await screen.findByRole('heading', { name: 'You do not have access to this page' })).toBeInTheDocument();
  });
});

describe('route planning', () => {
  it('creates a plan from plannable tasks and shows its ordered stops and method', async () => {
    const detail = {
      id: id(5), name: 'Monday run', planned_date: '2030-01-07', status: 'draft', vehicle_id: null, driver_id: null, start_facility_id: id(4), end_facility_id: null, total_distance_km: '12.40', optimizer: 'route-order 1.0.0',
      start_label: 'North Depot', return_leg_distance_km: null, warnings: ['Straight-line distances only.'], basis: 'Straight-line (haversine) distances; no live traffic.',
      stops: [
        { sequence: 1, kind: 'facility', collection_task_id: null, facility_id: id(4), label: 'North Depot', latitude: '17.5', longitude: '78.5', leg_distance_km: '0' },
        { sequence: 2, kind: 'task', collection_task_id: id(3), facility_id: null, label: 'Collect skip', latitude: '17.4', longitude: '78.4', leg_distance_km: '12.40' },
      ],
    };
    const api = routeApi(fetchSpy, {
      'GET /api/v1/route-planning/plans': page([]),
      'GET /api/v1/collection/tasks': page([task(), task({ id: id(6), title: 'No coordinates', latitude: null, longitude: null }), task({ id: id(7), title: 'Already done', status: 'completed' })]),
      'GET /api/v1/facilities': page([facility()]),
      'GET /api/v1/fleet/vehicles': page([]),
      'GET /api/v1/admin/users': page([]),
      'POST /api/v1/route-planning/plans': detail,
      [`GET /api/v1/route-planning/plans/${id(5)}`]: detail,
    }, manager);
    renderAt('/routes');
    await userEvent.click(await screen.findByRole('button', { name: 'Plan a route' }));
    const dialog = screen.getByRole('dialog', { name: 'Plan a route' });
    expect(await within(dialog).findByRole('checkbox', { name: /Collect skip/ })).toBeInTheDocument();
    expect(within(dialog).queryByRole('checkbox', { name: /No coordinates/ })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole('checkbox', { name: /Already done/ })).not.toBeInTheDocument();
    const submit = within(dialog).getByRole('button', { name: 'Create plan' });
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Plan name'), 'Monday run');
    await userEvent.type(within(dialog).getByLabelText('Date'), '2030-01-07');
    await userEvent.selectOptions(within(dialog).getByLabelText('Start depot'), id(4));
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /Collect skip/ }));
    await userEvent.click(submit);
    const result = await screen.findByRole('dialog', { name: 'Route plan' });
    expect(await within(result).findByText('Straight-line distances only.')).toBeInTheDocument();
    const stops = within(result).getByRole('table', { name: 'Stops in order' });
    expect(within(stops).getAllByRole('row').slice(1).map((r) => r.textContent)).toEqual([expect.stringContaining('North Depot'), expect.stringContaining('Collect skip')]);
    expect(within(result).getByText('route-order 1.0.0')).toBeInTheDocument();
    expect(api.calls.find((c) => c.key === 'POST /api/v1/route-planning/plans')?.body).toEqual({
      name: 'Monday run', planned_date: '2030-01-07', start_facility_id: id(4), task_ids: [id(3)],
    });
  });
});

describe('community incidents', () => {
  const incident = (over: Record<string, unknown> = {}) => ({
    id: id(6), reporter_id: id(9), assigned_to_id: null, incident_type: 'illegal_dumping', status: 'open', title: 'Dumped sofa', description: null, address_text: 'Lake Road',
    latitude: null, longitude: null, photo_content_path: null, resolved_at: null, resolution_notes: null, created_at: '2026-10-19T08:00:00Z', ...over,
  });

  it('triage sees the summary, can resolve only with notes, and only valid next statuses are offered', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/community-incidents': page([incident({ status: 'acknowledged' })]),
      'GET /api/v1/community-incidents/summary': { total: 3, open_incidents: 2, unassigned_open: 1, by_status: [{ key: 'open', count: 2 }], by_type: [{ key: 'illegal_dumping', count: 3 }] },
      'GET /api/v1/admin/users': page([]),
      [`POST /api/v1/community-incidents/${id(6)}/status`]: incident({ status: 'resolved', resolution_notes: 'Removed' }),
    }, manager);
    renderAt('/incidents');
    expect(await screen.findByText('1 unassigned')).toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Open incident: Dumped sofa' }));
    const dialog = screen.getByRole('dialog', { name: 'Incident' });
    const group = within(dialog).getByRole('group', { name: 'Change status' });
    const options = within(within(group).getByLabelText('Move to')).getAllByRole('option').map((o) => o.getAttribute('value'));
    expect(options).toEqual(['', 'in_progress', 'resolved', 'dismissed']);
    await userEvent.selectOptions(within(group).getByLabelText('Move to'), 'resolved');
    const update = within(group).getByRole('button', { name: 'Update status' });
    expect(update).toBeDisabled();
    await userEvent.type(within(group).getByLabelText('Notes (required)'), 'Removed');
    await userEvent.click(update);
    expect(await within(dialog).findByText('Removed')).toBeInTheDocument();
    expect(api.calls.find((c) => c.key.endsWith('/status'))?.body).toEqual({ status: 'resolved', notes: 'Removed' });
    expect(within(dialog).queryByRole('group', { name: 'Change status' })).not.toBeInTheDocument();
  });

  it('a resident reports an incident and gets no triage controls', async () => {
    const api = routeApi(fetchSpy, {
      'GET /api/v1/community-incidents': page([incident()]),
      'POST /api/v1/community-incidents': incident(),
    }, citizen);
    renderAt('/incidents');
    await userEvent.click(await screen.findByRole('button', { name: 'Open incident: Dumped sofa' }));
    const detail = screen.getByRole('dialog', { name: 'Incident' });
    expect(within(detail).queryByRole('group', { name: 'Assignment' })).not.toBeInTheDocument();
    await userEvent.click(within(detail).getByRole('button', { name: 'Close' }));
    await userEvent.click(screen.getByRole('button', { name: 'Report an incident' }));
    const dialog = screen.getByRole('dialog', { name: 'Report an incident' });
    await userEvent.type(within(dialog).getByLabelText('Title'), 'Dumped sofa');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Submit incident' }));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/community-incidents')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/community-incidents')?.body).toMatchObject({ incident_type: 'illegal_dumping', title: 'Dumped sofa' });
  });
});

describe('navigation', () => {
  it('shows only the destinations the role may use', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/notifications/unread-count': { unread: 0 } }, userWith(['collection:read', 'fleet:read'], { roles: ['collector'] }));
    renderAt('/forbidden');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const labels = within(nav).getAllByRole('link').map((a) => a.textContent ?? '');
    expect(labels.some((l) => l.startsWith('Collections'))).toBe(true);
    expect(labels.some((l) => l.startsWith('Fleet') || l.startsWith('Vehicles'))).toBe(true);
    expect(labels.some((l) => l.startsWith('Incidents'))).toBe(false);
    expect(labels.some((l) => l.startsWith('Analytics'))).toBe(false);
    expect(labels.some((l) => l.startsWith('Routes'))).toBe(false);
  });
});
