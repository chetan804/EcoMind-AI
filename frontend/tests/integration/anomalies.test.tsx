import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { errorReply, page, routeApi } from '../helpers/api-mock';
import { alertFixture, platformSeries, referenceSeries } from '../helpers/fixtures';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const manager = userWith(['anomalies:read', 'anomalies:manage', 'forecasting:read']);
const viewer = userWith(['anomalies:read']);

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

describe('anomalies page', () => {
  it('describes alerts as suspected, defaults to open platform data and offers lifecycle actions to managers', async () => {
    const api = routeApi(fetchSpy, { 'GET /api/v1/anomalies': page([alertFixture()]) }, manager);
    renderAt('/anomalies');
    expect(await screen.findByText(/not confirmed incidents/)).toBeInTheDocument();
    const row = (await screen.findByText('Collected weight was far above the recent pattern.')).closest('tr') as HTMLElement;
    expect(within(row).getByText('Critical')).toBeInTheDocument();
    expect(within(row).getByText('400 kg')).toBeInTheDocument();
    for (const name of [/^Acknowledge:/, /^Resolve:/, /^Mark as false positive:/]) {
      expect(within(row).getByRole('button', { name })).toBeInTheDocument();
    }
    const q = api.calls[0]?.query;
    expect(q?.get('status')).toBe('open');
    expect(q?.get('data_kind')).toBe('platform');
  });

  it('gives read-only users no actions and no scan button', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/anomalies': page([alertFixture()]) }, viewer);
    renderAt('/anomalies');
    await screen.findByText('Collected weight was far above the recent pattern.');
    expect(screen.queryByRole('button', { name: /Acknowledge|Resolve|false positive|Scan/ })).not.toBeInTheDocument();
  });

  it('offers only transitions the lifecycle allows', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/anomalies': page([alertFixture({ status: 'acknowledged' }), alertFixture({ id: '66666666-6666-4666-8666-666666666666', status: 'resolved' })]) }, manager);
    renderAt('/anomalies');
    const rows = await screen.findAllByRole('row');
    const acknowledged = rows.find((r) => within(r).queryByText('Acknowledged')) as HTMLElement;
    expect(within(acknowledged).queryByRole('button', { name: /^Acknowledge:/ })).not.toBeInTheDocument();
    expect(within(acknowledged).getByRole('button', { name: /^Resolve:/ })).toBeInTheDocument();
    const resolved = rows.find((r) => within(r).queryByText('Resolved')) as HTMLElement;
    expect(within(resolved).queryByRole('button')).not.toBeInTheDocument();
  });

  it('acknowledges with a note and reloads the list', async () => {
    let status = 'open';
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/anomalies': () => page([alertFixture({ status })]),
        'POST /api/v1/anomalies/22222222-2222-4222-8222-222222222222/acknowledge': () => {
          status = 'acknowledged';
          return alertFixture({ status });
        },
      },
      manager,
    );
    renderAt('/anomalies');
    await userEvent.click(await screen.findByRole('button', { name: /^Acknowledge:/ }));
    const dialog = screen.getByRole('dialog', { name: 'Acknowledge' });
    await userEvent.type(within(dialog).getByLabelText('Note (optional)'), 'Checking with the depot');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Acknowledge' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.calls.find((c) => c.key.endsWith('/acknowledge'))?.body).toEqual({ note: 'Checking with the depot' });
    expect(await within(screen.getByRole('table', { name: 'Suspected anomalies' })).findByText('Acknowledged')).toBeInTheDocument();
  });

  it('shows the server reason when a transition is refused', async () => {
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/anomalies': page([alertFixture()]),
        'POST /api/v1/anomalies/22222222-2222-4222-8222-222222222222/resolve': errorReply(409, 'invalid_alert_transition', 'This alert has already been closed.'),
      },
      manager,
    );
    renderAt('/anomalies');
    await userEvent.click(await screen.findByRole('button', { name: /^Resolve:/ }));
    await userEvent.click(within(screen.getByRole('dialog', { name: 'Resolve' })).getByRole('button', { name: 'Resolve' }));
    expect(await screen.findByText(/already been closed/)).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: 'Resolve' })).toBeInTheDocument();
  });

  it('scans a chosen series and reports what it found, with the caveat', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/anomalies': page([]),
        'GET /api/v1/forecasting/series': [platformSeries, referenceSeries],
        'POST /api/v1/anomalies/scan': {
          series: 'reference:austin',
          data_kind: 'public_reference',
          detector: 'robust-z',
          weeks_scanned: 26,
          weeks_considered: 26,
          flagged: 2,
          created: 1,
          already_recorded: 1,
          alerts: [],
          caveat: 'Flags are suspected anomalies, not confirmed incidents.',
        },
      },
      manager,
    );
    renderAt('/anomalies');
    expect(await screen.findByText('No suspected anomalies match these filters')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Scan a series' }));
    const dialog = screen.getByRole('dialog', { name: 'Scan a series' });
    const select = await within(dialog).findByRole('combobox', { name: 'Series' });
    await within(dialog).findByRole('option', { name: 'Austin curbside (public reference)' });
    await userEvent.selectOptions(select, 'reference:austin');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Run scan' }));
    expect(await within(dialog).findByText(/2 flagged, 1 new, 1 already recorded/)).toBeInTheDocument();
    expect(api.calls.find((c) => c.key === 'POST /api/v1/anomalies/scan')?.body).toEqual({ series: 'reference:austin', lookback_weeks: 26 });
  });
});
