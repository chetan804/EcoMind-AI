import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { errorReply, routeApi } from '../helpers/api-mock';
import { forecastFixture, forecastPointsFixture, historyFixture, platformSeries, referenceSeries } from '../helpers/fixtures';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const runner = userWith(['forecasting:read', 'forecasting:run']);
const reader = userWith(['forecasting:read']);

const base = (latest: unknown = { series: platformSeries, generated_at: null, model_name: null, model_version: null, points: [] }) => ({
  'GET /api/v1/forecasting/series': [platformSeries, referenceSeries],
  'GET /api/v1/forecasting/series/history': ({ query }: { query: URLSearchParams }) =>
    historyFixture(query.get('series') === referenceSeries.ref ? referenceSeries : platformSeries),
  'GET /api/v1/forecasting/forecasts/latest': latest,
});

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

describe('forecasting page', () => {
  it('labels the data source and says when no forecast has been saved', async () => {
    routeApi(fetchSpy, base(), reader);
    renderAt('/forecasts');
    expect(await screen.findByText('Platform data')).toBeInTheDocument();
    expect(await screen.findByText('No forecast has been saved for this series yet.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Run forecast' })).not.toBeInTheDocument();
    expect(await screen.findByRole('img', { name: /Series history and forecast/ })).toBeInTheDocument();
  });

  it('marks public reference series with their provenance', async () => {
    routeApi(fetchSpy, base(), reader);
    renderAt('/forecasts');
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Series' }), 'reference:austin');
    expect(await screen.findByText('Public reference data')).toBeInTheDocument();
    expect(screen.getByText(/https:\/\/example.org\/austin \(CC0\)/)).toBeInTheDocument();
  });

  it('shows the latest saved forecast with its model and generation date', async () => {
    routeApi(
      fetchSpy,
      base({ series: platformSeries, generated_at: '2026-10-19T00:00:00Z', model_name: 'holt_winters', model_version: 'ts-1.0.0', points: forecastPointsFixture }),
      reader,
    );
    renderAt('/forecasts');
    const table = await screen.findByRole('table', { name: 'Forecast values' });
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    expect(within(table).getByText('42.5')).toBeInTheDocument();
    expect(screen.getByText(/by holt_winters ts-1.0.0/)).toBeInTheDocument();
  });

  it('runs a forecast with the chosen horizon and shows the backtest against the naive baseline', async () => {
    const api = routeApi(fetchSpy, { ...base(), 'POST /api/v1/forecasting/forecasts': forecastFixture(true) }, runner);
    renderAt('/forecasts');
    await userEvent.selectOptions(await screen.findByLabelText('Weeks ahead'), '8');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Save this forecast' }));
    await userEvent.click(screen.getByRole('button', { name: 'Run forecast' }));
    expect(await screen.findByText('Beats the naive baseline')).toBeInTheDocument();
    expect(screen.getByText(/ratio 0.840; below 1 is better/)).toBeInTheDocument();
    expect(screen.getByText('Weekly totals only; holidays are not modelled.')).toBeInTheDocument();
    expect(api.calls.find((c) => c.key.startsWith('POST'))?.body).toEqual({ series: 'platform:collected_weight_kg', horizon_weeks: 8, save: false });
  });

  it('does not present a forecast as good when it fails to beat the baseline', async () => {
    const worse = forecastFixture(false);
    worse.backtest.mae_vs_naive = 1.2;
    routeApi(fetchSpy, { ...base(), 'POST /api/v1/forecasting/forecasts': worse }, runner);
    renderAt('/forecasts');
    await userEvent.click(await screen.findByRole('button', { name: 'Run forecast' }));
    expect(await screen.findByText('Does not beat the naive baseline')).toBeInTheDocument();
  });

  it('says so when there was too little history to backtest', async () => {
    routeApi(fetchSpy, { ...base(), 'POST /api/v1/forecasting/forecasts': forecastFixture(null) }, runner);
    renderAt('/forecasts');
    await userEvent.click(await screen.findByRole('button', { name: 'Run forecast' }));
    expect(await screen.findByText(/not enough history to backtest/)).toBeInTheDocument();
  });

  it('shows the server reason when the series has too little history', async () => {
    routeApi(
      fetchSpy,
      { ...base(), 'POST /api/v1/forecasting/forecasts': errorReply(422, 'insufficient_history', 'At least 26 weeks of history are required.') },
      runner,
    );
    renderAt('/forecasts');
    await userEvent.click(await screen.findByRole('button', { name: 'Run forecast' }));
    expect(await screen.findByText(/At least 26 weeks/)).toBeInTheDocument();
  });
});
