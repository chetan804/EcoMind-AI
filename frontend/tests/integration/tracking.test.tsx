import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { errorReply, page, routeApi } from '../helpers/api-mock';
import { latestPositionsFixture, overviewFixture, trackedVehicle, trendFixture } from '../helpers/fixtures';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const id = (n: number) => `${String(n).repeat(8)}-${String(n).repeat(4)}-4${String(n).repeat(3)}-8${String(n).repeat(3)}-${String(n).repeat(12)}`;

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const manager = userWith(['analytics:read', 'fleet:read', 'fleet:manage', 'facilities:read', 'routes:read', 'routes:manage', 'collection:read', 'collection:manage', 'users:read']);
const simulator = userWith([...manager.permissions, 'fleet:simulate']);

const position = (over: Record<string, unknown> = {}) => ({
  latitude: '17.4', longitude: '78.5', recorded_at: '2026-10-21T08:00:00Z', received_at: '2026-10-21T08:00:01Z', source: 'gps_device', accuracy_m: '8', speed_kph: null, heading_deg: null,
  age_seconds: 5, collection_task_id: null, route_plan_id: null, ...over,
});
const vehicleRow = (n: number, over: Record<string, unknown> = {}) => trackedVehicle({ vehicle_id: id(n), registration_number: `TS09-000${n}`, ...over });
const facility = {
  id: id(4), code: 'DEP1', name: 'North Depot', facility_type: 'depot', status: 'active', address_line: null, city: 'Hyderabad', region: null, country_code: 'IN',
  latitude: '17.5', longitude: '78.5', daily_capacity_kg: '5000.000', contact_email: null, zone_id: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
};
const fleetVehicles = [1, 2, 3].map((n) => ({ id: id(n), registration_number: `TS09-000${n}`, vehicle_type: 'van', status: 'in_service', capacity_kg: '800.000', home_facility_id: id(4), active_task_count: 0 }));

describe('fleet positions', () => {
  it('labels each vehicle from its report metadata and never places a vehicle that has not reported', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/fleet/vehicles': page(fleetVehicles),
        'GET /api/v1/facilities': page([facility]),
        'GET /api/v1/tracking/vehicles': latestPositionsFixture([
          vehicleRow(1, { status: 'live', position: position() }),
          vehicleRow(2, { status: 'stale', position: position({ age_seconds: 2000 }) }),
          vehicleRow(3),
          vehicleRow(1, { simulated: true, status: 'simulated', position: position({ source: 'simulator', latitude: '17.41' }) }),
        ]),
      },
      manager,
    );
    renderAt('/fleet');
    const table = await screen.findByRole('table', { name: 'Fleet vehicles' });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(within(rows[0]!).getByText('LIVE GPS')).toBeInTheDocument();
    expect(within(rows[0]!).getByText(/5 s ago/)).toBeInTheDocument();
    expect(within(rows[1]!).getByText('STALE')).toBeInTheDocument();
    expect(within(rows[1]!).getByText(/33 min ago/)).toBeInTheDocument();
    expect(within(rows[2]!).getByText('LOCATION UNAVAILABLE')).toBeInTheDocument();
    // Without a browser key the map is replaced by a labelled list; the list mirrors the map.
    const list = await screen.findByRole('table', { name: 'Fleet positions: locations' });
    expect(within(list).getByRole('rowheader', { name: 'TS09-0001' })).toBeInTheDocument();
    expect(within(list).getByRole('rowheader', { name: 'TS09-0001 (simulated)' })).toBeInTheDocument();
    expect(within(list).getByText('SIMULATED')).toBeInTheDocument();
    expect(within(list).queryByRole('rowheader', { name: 'TS09-0003' })).not.toBeInTheDocument();
    expect(within(list).getByRole('rowheader', { name: 'North Depot' })).toBeInTheDocument();
    expect(screen.getByText(/LOCATION UNAVAILABLE \(never reported\): TS09-0003/)).toBeInTheDocument();
    expect(api.calls.find((c) => c.key === 'GET /api/v1/tracking/vehicles')?.query.get('include_simulated')).toBe('true');
  });

  it('can hide the simulated layer and the facilities layer', async () => {
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/fleet/vehicles': page(fleetVehicles),
        'GET /api/v1/facilities': page([facility]),
        'GET /api/v1/tracking/vehicles': latestPositionsFixture([vehicleRow(1, { status: 'live', position: position() }), vehicleRow(1, { simulated: true, status: 'simulated', position: position({ source: 'simulator' }) })]),
      },
      manager,
    );
    renderAt('/fleet');
    const list = await screen.findByRole('table', { name: 'Fleet positions: locations' });
    expect(within(list).getByRole('rowheader', { name: 'TS09-0001 (simulated)' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Simulated vehicles' }));
    expect(within(await screen.findByRole('table', { name: 'Fleet positions: locations' })).queryByRole('rowheader', { name: 'TS09-0001 (simulated)' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Facilities and depots' }));
    expect(within(screen.getByRole('table', { name: 'Fleet positions: locations' })).queryByRole('rowheader', { name: 'North Depot' })).not.toBeInTheDocument();
  });

  it('tells the user when positions cannot be refreshed instead of silently showing old data', async () => {
    routeApi(
      fetchSpy,
      { 'GET /api/v1/fleet/vehicles': page(fleetVehicles), 'GET /api/v1/facilities': page([]), 'GET /api/v1/tracking/vehicles': errorReply(503, 'unavailable', 'down') },
      manager,
    );
    renderAt('/fleet');
    expect(await screen.findByText('Vehicle positions could not be refreshed')).toBeInTheDocument();
    expect(await screen.findAllByText('LOCATION UNAVAILABLE')).not.toHaveLength(0);
  });
});

describe('command center', () => {
  it('shows the fleet map for people who may read the fleet, and omits it otherwise', async () => {
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/analytics/overview': overviewFixture,
        'GET /api/v1/analytics/weekly-trend': trendFixture,
        'GET /api/v1/facilities': page([facility]),
        'GET /api/v1/tracking/vehicles': latestPositionsFixture([vehicleRow(1, { status: 'delayed', position: position({ age_seconds: 300 }) })]),
      },
      manager,
    );
    renderAt('/dashboard');
    const list = await screen.findByRole('table', { name: 'Fleet positions: locations' });
    expect(within(list).getByText('DELAYED')).toBeInTheDocument();
    expect(screen.getByText(/refreshed every 15 s/)).toBeInTheDocument();
  });

  it('leaves the map out for a role without fleet access', async () => {
    const api = routeApi(fetchSpy, { 'GET /api/v1/analytics/overview': overviewFixture, 'GET /api/v1/analytics/weekly-trend': trendFixture }, userWith(['analytics:read']));
    renderAt('/dashboard');
    await screen.findByRole('list', { name: 'Key metrics' });
    expect(screen.queryByRole('region', { name: /Fleet positions/ })).not.toBeInTheDocument();
    expect(api.unmatched).toEqual([]);
  });
});

describe('route plan map', () => {
  const stops = [
    { sequence: 1, kind: 'task', collection_task_id: id(3), facility_id: null, label: 'Collect skip', latitude: '17.52', longitude: '78.52', leg_distance_km: '3.10' },
    { sequence: 2, kind: 'task', collection_task_id: id(6), facility_id: null, label: 'Collect bags', latitude: '17.54', longitude: '78.55', leg_distance_km: '3.50' },
  ];
  const plan = (over: Record<string, unknown> = {}) => ({
    id: id(5), name: 'Monday run', planned_date: '2030-01-07', status: 'published', vehicle_id: id(8), driver_id: null, start_facility_id: id(4), end_facility_id: null,
    total_distance_km: '9.00', optimizer: 'route-order 1.0.0', start_label: 'North Depot', start_latitude: '17.5', start_longitude: '78.5', return_leg_distance_km: '2.40',
    warnings: [], basis: 'Straight-line (haversine) distances.', stops, ...over,
  });
  const routeTracking = (over: Record<string, unknown> = {}) => ({
    route_plan_id: id(5), plan_status: 'published', vehicle_id: id(8), stops: stops.map((s) => ({ sequence: s.sequence, kind: 'task', label: s.label, latitude: s.latitude, longitude: s.longitude, task_id: s.collection_task_id, task_status: s.sequence === 1 ? 'completed' : 'assigned', completed: s.sequence === 1 })),
    completed_task_stops: 1, total_task_stops: 2, vehicle: null, path: [], path_simulated: false, path_truncated: false, basis: 'Stop states come from the collection tasks.', ...over,
  });
  const roadUnavailable = (reason: string) => ({ plan_id: id(5), available: false, provider: reason === 'not_configured' ? null : 'google_routes', reason, detail: null, encoded_polylines: [], distance_m: null, duration_s: null, traffic_aware: false, request_count: 0, basis: 'x' });
  const routes = (road: unknown, user = manager) =>
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/route-planning/plans': page([{ ...plan(), stops: undefined }]),
        [`GET /api/v1/route-planning/plans/${id(5)}`]: plan(),
        [`GET /api/v1/route-planning/plans/${id(5)}/road-route`]: road as never,
        [`GET /api/v1/tracking/route-plans/${id(5)}`]: routeTracking(),
        'GET /api/v1/tracking/config': { live_within_seconds: 120, stale_after_seconds: 900, retention_days: 90, simulator_enabled: true, max_events_per_minute: 30, road_routing_configured: false },
        [`POST /api/v1/tracking/simulation/vehicles/${id(8)}/locations`]: { duplicate: false, event: { id: id(9) } },
        [`DELETE /api/v1/tracking/simulation/vehicles/${id(8)}/locations`]: { removed: 2 },
      },
      user,
    );
  const open = async () => {
    renderAt('/routes');
    await userEvent.click(await screen.findByRole('button', { name: /Monday run/ }));
    return screen.findByRole('dialog', { name: 'Route plan' });
  };

  it('labels the straight-line fallback and the reason when no road route exists', async () => {
    routes(roadUnavailable('not_configured'));
    const dialog = await open();
    expect(await within(dialog).findByText('No road route: straight-line fallback')).toBeInTheDocument();
    expect(within(dialog).getByText(/Road routing is not configured on this server/)).toBeInTheDocument();
    expect(within(dialog).getByText(/not a driving route; the distances in the table are straight-line estimates/)).toBeInTheDocument();
    const list = await within(dialog).findByRole('table', { name: 'Route plan: locations' });
    expect(within(list).getByRole('rowheader', { name: 'Stop 1: Collect skip' })).toBeInTheDocument();
    expect(within(list).getByRole('rowheader', { name: 'Stop 2: Collect bags' })).toBeInTheDocument();
    expect(within(list).getByText('Completed (from the collection task)')).toBeInTheDocument();
    expect(within(dialog).getByText(/Straight lines between stops\. Not roads and not a driving route: 4 points/)).toBeInTheDocument();
    expect(within(dialog).getByText('Progress: 1 of 2 task stops completed (from collection task status).')).toBeInTheDocument();
  });

  it.each([
    ['quota_exceeded', /quota was exceeded/],
    ['timeout', /did not answer in time/],
    ['access_denied', /rejected the request/],
  ])('explains a provider failure (%s) and still shows the stops', async (reason, text) => {
    routes(roadUnavailable(reason));
    const dialog = await open();
    expect(await within(dialog).findByText(text)).toBeInTheDocument();
    expect(await within(dialog).findByRole('table', { name: 'Route plan: locations' })).toBeInTheDocument();
  });

  it('shows provider distance and duration only when the provider returned a road route, and re-asks only on request', async () => {
    const api = routes({
      plan_id: id(5), available: true, provider: 'google_routes', reason: null, detail: null, encoded_polylines: ['_p~iF~ps|U_ulLnnqC_mqNvxq`@'], distance_m: 12_400, duration_s: 1_500, traffic_aware: false, request_count: 1, basis: 'x',
    });
    const dialog = await open();
    expect(await within(dialog).findByText(/12\.4 km, about 25 min \(provider estimate, no live traffic\)/)).toBeInTheDocument();
    expect(within(dialog).queryByText('No road route: straight-line fallback')).not.toBeInTheDocument();
    expect(await within(dialog).findByText(/Planned route on roads \(routing provider, no live traffic\): 3 points/)).toBeInTheDocument();
    const roadCalls = () => api.calls.filter((c) => c.key.endsWith('/road-route')).length;
    expect(roadCalls()).toBe(1);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Recompute road route' }));
    await vi.waitFor(() => expect(roadCalls()).toBe(2));
    expect(within(dialog).getByText(/does not reorder stops/)).toBeInTheDocument();
  });

  it('does not offer the simulator without the simulate permission', async () => {
    routes(roadUnavailable('not_configured'));
    const dialog = await open();
    await within(dialog).findByRole('table', { name: 'Route plan: locations' });
    expect(within(dialog).queryByText(/Simulation \(demonstration only\)/)).not.toBeInTheDocument();
  });

  it('runs the simulator step by step through the separate endpoint, then resets it', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = routes(roadUnavailable('not_configured'), simulator);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderAt('/routes');
    await user.click(await screen.findByRole('button', { name: /Monday run/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Route plan' });
    expect(await within(dialog).findByText('Simulated positions are not real GPS')).toBeInTheDocument();
    expect(within(dialog).getByText(/straight lines between the stops/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Start simulation' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100);
    });
    const posts = api.calls.filter((c) => c.key === `POST /api/v1/tracking/simulation/vehicles/${id(8)}/locations`);
    expect(posts.length).toBeGreaterThanOrEqual(2);
    expect(posts[0]!.body).toMatchObject({ route_plan_id: id(5), latitude: '17.500000', longitude: '78.500000' });
    expect(api.calls.some((c) => c.key === 'POST /api/v1/tracking/vehicles/' + id(8) + '/locations')).toBe(false);
    await user.click(within(dialog).getByRole('button', { name: 'Pause' }));
    const countAtPause = api.calls.filter((c) => c.key.startsWith('POST /api/v1/tracking/simulation')).length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(api.calls.filter((c) => c.key.startsWith('POST /api/v1/tracking/simulation')).length).toBe(countAtPause);
    await user.click(within(dialog).getByRole('button', { name: 'Reset simulation' }));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.startsWith('DELETE /api/v1/tracking/simulation'))).toBe(true));
    expect(within(dialog).getByText(/Step 0 of/)).toBeInTheDocument();
  });
});

describe('collection tracking', () => {
  const task = (over: Record<string, unknown> = {}) => ({
    id: id(3), waste_report_id: null, destination_facility_id: null, title: 'Collect skip', status: 'in_progress', priority: 'high', address_text: 'Market Road', latitude: '17.4', longitude: '78.4',
    due_at: null, notes: null, created_by_id: id(9), assignment: null, collected_weight_kg: null, created_at: '2026-10-19T08:00:00Z', updated_at: '2026-10-19T08:00:00Z', history: [], events: [], ...over,
  });
  const tracking = (over: Record<string, unknown> = {}) => ({
    task_id: id(3), title: 'Collect skip', status: 'in_progress', latitude: '17.4', longitude: '78.4', destination_facility_id: null, vehicle_id: id(8),
    vehicle: vehicleRow(8, { vehicle_id: id(8), status: 'live', position: position({ collection_task_id: id(3) }) }),
    path: [
      { latitude: '17.41', longitude: '78.41', recorded_at: '2026-10-21T07:58:00Z', source: 'gps_device' },
      { latitude: '17.405', longitude: '78.405', recorded_at: '2026-10-21T07:59:00Z', source: 'gps_device' },
    ], path_truncated: false, basis: 'The path is the recorded positions, not a navigation route.', ...over,
  });
  const setup = (trackingReply: unknown, user = manager) =>
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/collection/tasks': page([task()]),
        [`GET /api/v1/collection/tasks/${id(3)}`]: task({ assignment: { id: id(7), assignee_id: id(9), assignee_name: 'Asha', vehicle_id: id(8), vehicle_registration: 'TS09-0008', assigned_at: '2026-10-19T09:00:00Z', unassigned_at: null } }),
        [`GET /api/v1/tracking/collections/${id(3)}`]: trackingReply as never,
      },
      user,
    );

  it('shows vehicle status, the recorded path and the basis for a collection task', async () => {
    setup(tracking());
    renderAt('/collection');
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    const detail = await screen.findByRole('dialog', { name: 'Collection task' });
    const section = await within(detail).findByRole('region', { name: 'Location and tracking' });
    expect((await within(section).findAllByText('LIVE GPS')).length).toBeGreaterThan(0);
    expect(within(section).getByText(/Recorded vehicle path for this task: 2 points/)).toBeInTheDocument();
    expect(within(section).getByText('The path is the recorded positions, not a navigation route.')).toBeInTheDocument();
    expect(within(section).getByRole('rowheader', { name: 'Collect skip' })).toBeInTheDocument();
  });

  it('says plainly that no positions are linked yet', async () => {
    setup(tracking({ path: [], vehicle: vehicleRow(8, { vehicle_id: id(8), status: 'stale', position: position({ age_seconds: 4000 }) }) }));
    renderAt('/collection');
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    const detail = await screen.findByRole('dialog', { name: 'Collection task' });
    expect(await within(detail).findByText(/No positions have been linked to this task yet/)).toBeInTheDocument();
    expect(within(detail).getAllByText('STALE').length).toBeGreaterThan(0);
  });

  it('does not request tracking for someone who cannot manage or work the task', async () => {
    const api = setup(tracking(), userWith(['collection:read']));
    renderAt('/collection');
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    await screen.findByRole('dialog', { name: 'Collection task' });
    expect(screen.queryByRole('region', { name: 'Location and tracking' })).not.toBeInTheDocument();
    expect(api.calls.some((c) => c.key.includes('/tracking/'))).toBe(false);
  });
});

describe('collector location sharing', () => {
  const me = userWith(['collection:read', 'collection:execute', 'fleet:track']);
  const assigned = (assigneeId: string, status = 'in_progress') => ({
    id: id(3), waste_report_id: null, destination_facility_id: null, title: 'Collect skip', status, priority: 'high', address_text: 'Market Road', latitude: '17.4', longitude: '78.4',
    due_at: null, notes: null, created_by_id: id(9), collected_weight_kg: null, created_at: '2026-10-19T08:00:00Z', updated_at: '2026-10-19T08:00:00Z', history: [], events: [],
    assignment: { id: id(7), assignee_id: assigneeId, assignee_name: 'Asha', vehicle_id: id(8), vehicle_registration: 'TS09-0008', assigned_at: '2026-10-19T09:00:00Z', unassigned_at: null },
  });
  type Watch = { ok: (p: unknown) => void; fail: (e: unknown) => void };
  let watch: Watch | null = null;
  const clearWatch = vi.fn();
  const watchPosition = vi.fn((ok: Watch['ok'], fail: Watch['fail']) => {
    watch = { ok, fail };
    return 7;
  });
  const fix = (over: Record<string, unknown> = {}) => ({ timestamp: Date.parse('2026-10-21T08:00:00Z'), coords: { latitude: 17.38512345, longitude: 78.48671234, accuracy: 9.4, speed: null, heading: null, ...over } });
  const setup = (taskReply: unknown, post: unknown = { duplicate: false, event: { id: id(9) } }) => {
    watch = null;
    clearWatch.mockClear();
    watchPosition.mockClear();
    Object.defineProperty(navigator, 'geolocation', { value: { watchPosition, clearWatch }, configurable: true });
    return routeApi(
      fetchSpy,
      {
        'GET /api/v1/collection/tasks': page([{ ...(taskReply as object), history: undefined, events: undefined }]),
        [`GET /api/v1/collection/tasks/${id(3)}`]: taskReply as never,
        [`GET /api/v1/tracking/collections/${id(3)}`]: { task_id: id(3), title: 'x', status: 'in_progress', latitude: '17.4', longitude: '78.4', destination_facility_id: null, vehicle_id: id(8), vehicle: null, path: [], path_truncated: false, basis: 'b' },
        [`POST /api/v1/tracking/vehicles/${id(8)}/locations`]: post as never,
      },
      me,
    );
  };
  const openTask = async () => {
    renderAt('/collection');
    await userEvent.click(await screen.findByRole('button', { name: 'Open task: Collect skip' }));
    return screen.findByRole('dialog', { name: 'Collection task' });
  };

  it('asks the browser for a position only after the button is pressed, then reports it as a mobile-client position', async () => {
    const api = setup(assigned(me.id));
    const dialog = await openTask();
    const share = await within(dialog).findByRole('button', { name: 'Share my position' });
    expect(watchPosition).not.toHaveBeenCalled();
    await userEvent.click(share);
    expect(watchPosition).toHaveBeenCalledTimes(1);
    act(() => watch!.ok(fix()));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === `POST /api/v1/tracking/vehicles/${id(8)}/locations`)).toBe(true));
    const body = api.calls.find((c) => c.key.startsWith('POST /api/v1/tracking/vehicles'))!.body as Record<string, unknown>;
    expect(body).toMatchObject({ latitude: '17.385123', longitude: '78.486712', source: 'mobile_client', accuracy_m: '9.40', collection_task_id: id(3), recorded_at: '2026-10-21T08:00:00.000Z' });
    // The device measured no speed or heading, so none is invented.
    expect(body).not.toHaveProperty('speed_kph');
    expect(body).not.toHaveProperty('heading_deg');
    expect(await within(dialog).findByText(/1 report sent/)).toBeInTheDocument();
    // A second fix within the interval is not sent.
    act(() => watch!.ok(fix({ latitude: 17.39 })));
    expect(api.calls.filter((c) => c.key.startsWith('POST /api/v1/tracking/vehicles'))).toHaveLength(1);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Stop sharing' }));
    expect(clearWatch).toHaveBeenCalledWith(7);
  });

  it('converts measured speed from m/s to km/h and passes heading through', async () => {
    const api = setup(assigned(me.id));
    const dialog = await openTask();
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Share my position' }));
    act(() => watch!.ok(fix({ speed: 10, heading: 450 })));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.startsWith('POST /api/v1/tracking/vehicles'))).toBe(true));
    expect(api.calls.find((c) => c.key.startsWith('POST /api/v1/tracking/vehicles'))!.body).toMatchObject({ speed_kph: '36.00', heading_deg: '90.00' });
  });

  it('explains a denied permission and sends nothing', async () => {
    const api = setup(assigned(me.id));
    const dialog = await openTask();
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Share my position' }));
    act(() => watch!.fail({ code: 1, PERMISSION_DENIED: 1 }));
    expect(await within(dialog).findByText(/Location permission was denied/)).toBeInTheDocument();
    expect(api.calls.some((c) => c.key.startsWith('POST /api/v1/tracking/vehicles'))).toBe(false);
    expect(within(dialog).getByRole('button', { name: 'Share my position' })).toBeEnabled();
  });

  it('shows the server reason when a report is rejected', async () => {
    setup(assigned(me.id), errorReply(429, 'rate_limited', 'Too many position reports'));
    const dialog = await openTask();
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Share my position' }));
    act(() => watch!.ok(fix()));
    expect(await within(dialog).findByText('Too many position reports')).toBeInTheDocument();
  });

  it('is offered only to the assignee while the task is in progress', async () => {
    setup(assigned(id(2)));
    const dialog = await openTask();
    await within(dialog).findByRole('heading', { name: 'Collect skip' });
    expect(within(dialog).queryByRole('button', { name: 'Share my position' })).not.toBeInTheDocument();
  });
});
