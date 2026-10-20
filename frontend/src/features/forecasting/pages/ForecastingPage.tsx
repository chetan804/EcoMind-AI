import { useMemo, useState } from 'react';
import { TrendChart } from '@/components/data-display/TrendChart';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Input';
import { Checkbox } from '@/components/ui/Choice';
import { Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDate, formatNumber } from '@/utils/format';
import type { Forecast, SeriesInfo } from '../api/forecasting-api';
import { useHistory, useLatestForecast, useRunForecast, useSeriesList } from '../hooks/useForecasting';
import '../forecasting.css';

const HISTORY_WEEKS_SHOWN = 52;
const shortDate = (value: string) => formatDate(value).replace(/ \d{4}$/, '');

function DataKindBadge({ series }: { series: SeriesInfo }) {
  return series.data_kind === 'platform' ? (
    <Badge tone="success">Platform data</Badge>
  ) : (
    <Badge tone="warning">Public reference data</Badge>
  );
}

export function ForecastingPage() {
  const { can } = useAuth();
  const seriesList = useSeriesList();
  const [chosen, setChosen] = useState('');
  const [horizon, setHorizon] = useState(4);
  const [save, setSave] = useState(true);
  const run = useRunForecast();
  const [result, setResult] = useState<Forecast | null>(null);

  const first = seriesList.data?.[0]?.ref ?? '';
  const series = chosen || first;
  const history = useHistory(series);
  const latest = useLatestForecast(series);
  const info = seriesList.data?.find((s) => s.ref === series);

  const forecastPoints = useMemo(() => {
    if (result && result.series.ref === series) return result.points;
    return latest.data?.points ?? [];
  }, [result, latest.data, series]);

  const chart = useMemo(() => {
    const hist = (history.data?.points ?? []).slice(-HISTORY_WEEKS_SHOWN);
    const labels = [...hist.map((p) => shortDate(p.period_start)), ...forecastPoints.map((p) => shortDate(p.period_start))];
    const pad = (values: number[], before: number): Array<number | null> => [...Array<null>(before).fill(null), ...values];
    const h = hist.length;
    return {
      labels,
      series: [
        {
          id: 'observed',
          label: 'Observed',
          color: 'var(--color-teal)',
          area: true,
          values: [...hist.map((p) => p.value), ...Array<null>(forecastPoints.length).fill(null)],
        },
        { id: 'predicted', label: 'Forecast', color: 'var(--color-warning)', dashed: true, values: pad(forecastPoints.map((p) => p.predicted), h) },
        { id: 'upper', label: 'Upper bound', color: 'var(--color-text-muted)', dashed: true, values: pad(forecastPoints.map((p) => p.upper), h) },
        { id: 'lower', label: 'Lower bound', color: 'var(--color-text-muted)', dashed: true, values: pad(forecastPoints.map((p) => p.lower), h) },
      ],
    };
  }, [history.data, forecastPoints]);

  return (
    <section aria-labelledby="forecast-title" className="stack">
      <PageHeader
        title="Collection volume forecasting"
        titleId="forecast-title"
        subtitle="Weekly volume forecasts, always shown with their backtest against a naive baseline"
      />
      <QueryBoundary query={seriesList} label="forecast series">
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No series available" description="Series appear once collections have been recorded or reference data is loaded." />
          ) : (
            <>
              <Card aria-labelledby="fc-controls">
                <CardHeader title="Series" titleId="fc-controls" />
                <div className="filter-bar">
                  <Field label="Series">
                    {(control) => (
                      <Select
                        {...control}
                        value={series}
                        onChange={(e) => {
                          setChosen(e.target.value);
                          setResult(null);
                          run.reset();
                        }}
                      >
                        {list.map((s) => (
                          <option key={s.ref} value={s.ref}>
                            {s.name}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  <Field label="Weeks ahead">
                    {(control) => (
                      <Select {...control} value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
                        {[1, 2, 4, 8, 12].map((w) => (
                          <option key={w} value={w}>{`${w} week${w === 1 ? '' : 's'}`}</option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  {can('forecasting:run') && (
                    <>
                      <Checkbox label="Save this forecast" checked={save} onChange={(e) => setSave(e.target.checked)} />
                      <Button
                        loading={run.isPending}
                        onClick={() => run.mutate({ series, horizon_weeks: horizon, save }, { onSuccess: setResult })}
                      >
                        Run forecast
                      </Button>
                    </>
                  )}
                </div>
                {info && (
                  <div className="forecast-meta">
                    <DataKindBadge series={info} />
                    <span>{info.label}</span>
                    <span className="muted">
                      {info.points} {info.granularity} points, {formatDate(info.first_period)} to {formatDate(info.last_period)}
                      {info.interpolated_points > 0 && `, ${info.interpolated_points} interpolated`}; unit: {info.unit}
                    </span>
                  </div>
                )}
                {info?.provenance && (
                  <p className="muted">
                    Source: {info.provenance.source_url} ({info.provenance.licence_note}). {info.provenance.processing_note}
                  </p>
                )}
                {run.isError && <Alert tone="danger">{getErrorMessage(run.error)}</Alert>}
              </Card>

              <Card aria-labelledby="fc-chart">
                <CardHeader title="History and forecast" titleId="fc-chart" />
                <QueryBoundary query={history} label="the series history">
                  {() => (
                    <TrendChart
                      ariaLabel="Series history and forecast"
                      unit={info?.unit ?? ''}
                      xLabels={chart.labels}
                      series={chart.series}
                      emptyMessage="This series has no data."
                    />
                  )}
                </QueryBoundary>
                {forecastPoints.length === 0 && !latest.isPending && (
                  <p className="muted">No forecast has been saved for this series yet.</p>
                )}
              </Card>

              {forecastPoints.length > 0 && (
                <Card aria-labelledby="fc-table">
                  <CardHeader title={result ? 'Forecast just run' : 'Latest saved forecast'} titleId="fc-table" />
                  <Table caption="Forecast values" captionHidden>
                    <thead>
                      <tr>
                        <th scope="col">Week starting</th>
                        <th scope="col">Forecast ({info?.unit})</th>
                        <th scope="col">Lower</th>
                        <th scope="col">Upper</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecastPoints.map((p) => (
                        <tr key={p.period_start}>
                          <th scope="row">{formatDate(p.period_start)}</th>
                          <td>{formatNumber(p.predicted)}</td>
                          <td>{formatNumber(p.lower)}</td>
                          <td>{formatNumber(p.upper)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                  {!result && latest.data?.generated_at && (
                    <p className="muted">
                      Generated {formatDate(latest.data.generated_at)} by {latest.data.model_name} {latest.data.model_version}.
                    </p>
                  )}
                </Card>
              )}

              {result && result.series.ref === series && <Evidence forecast={result} />}
            </>
          )
        }
      </QueryBoundary>
    </section>
  );
}

function Evidence({ forecast }: { forecast: Forecast }) {
  const b = forecast.backtest;
  return (
    <Card aria-labelledby="fc-evidence">
      <CardHeader title="How trustworthy is this forecast?" titleId="fc-evidence" />
      <p>
        Model: <strong>{forecast.model.name}</strong> (engine {forecast.model.engine_version}). {forecast.model.selection}
      </p>
      {b.mae_vs_naive === null ? (
        <Alert tone="warning">There was not enough history to backtest this model against the naive baseline.</Alert>
      ) : (
        <Alert tone={b.beats_naive ? 'success' : 'warning'} title={b.beats_naive ? 'Beats the naive baseline' : 'Does not beat the naive baseline'}>
          Backtest over {b.origins} past forecast origins ({b.horizon_weeks}-week horizon): mean absolute error{' '}
          {formatNumber(b.selected_mae ?? 0)} versus {formatNumber(b.naive_mae ?? 0)} for repeating the last value (ratio{' '}
          {b.mae_vs_naive.toFixed(3)}; below 1 is better).
        </Alert>
      )}
      <p className="muted">Interval level: {Math.round(forecast.interval_level * 100)}%.</p>
      <ul className="caveat-list">
        {forecast.caveats.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </Card>
  );
}
