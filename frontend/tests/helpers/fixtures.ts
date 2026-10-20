const count = (key: string, n: number) => ({ key, count: n });

export const overviewFixture = {
  generated_at: '2026-10-20T06:00:00Z',
  window_days: 30,
  window_start: '2026-09-20T06:00:00Z',
  reports: { total: 12, in_window: 5, by_status: [count('submitted', 3), count('verified', 9)] },
  collection: {
    tasks_total: 8,
    open_tasks: 3,
    overdue_tasks: 1,
    completed_in_window: 4,
    collected_weight_kg_in_window: '37.500',
    collected_weight_kg_total: '120.000',
    by_status: [count('pending', 2), count('completed', 5), count('cancelled', 0)],
  },
  fleet: { vehicles_total: 2, by_status: [count('available', 2)], capacity_kg_available: '1500.000' },
  facilities: { total: 3, active: 2 },
  incidents: { total: 4, open_incidents: 2, unassigned_open: 1 },
  recovery: { verified_records: 0, pending_records: 1, input_weight_kg: '0', recovered_weight_kg: '0', recovery_rate: null },
  rewards: { entries: 2, users: 1, net_points: 375, impact_weight_kg: '37.500' },
  anomalies: { open_alerts: 2, critical_open: 1 },
  passports: { total: 1, by_status: [count('issued', 1)] },
  basis: 'Computed from stored records at request time.',
};

export const trendFixture = {
  weeks: 3,
  points: [
    { week_start: '2026-10-05', collected_weight_kg: '0.000', tasks_completed: 0, reports_submitted: 1 },
    { week_start: '2026-10-12', collected_weight_kg: '37.500', tasks_completed: 1, reports_submitted: 2 },
    { week_start: '2026-10-19', collected_weight_kg: '10.000', tasks_completed: 1, reports_submitted: 0 },
  ],
  basis: 'Weeks start on Monday (UTC).',
};

export const alertFixture = (over: Record<string, unknown> = {}) => ({
  id: '22222222-2222-4222-8222-222222222222',
  metric: 'platform:collected_weight_kg',
  data_kind: 'platform',
  unit: 'kg',
  severity: 'critical',
  status: 'open',
  window_start: '2026-09-28',
  window_end: '2026-10-05',
  observed_value: '400.000',
  expected_value: '40.000',
  threshold_value: '5.000',
  detector_name: 'robust-z',
  detector_version: 'ts-1.0.0',
  explanation: 'Collected weight was far above the recent pattern.',
  detected_at: '2026-10-06T00:00:00Z',
  acknowledged_by_id: null,
  acknowledged_at: null,
  resolved_at: null,
  created_at: '2026-10-06T00:00:00Z',
  updated_at: '2026-10-06T00:00:00Z',
  ...over,
});

export const notificationFixture = (over: Record<string, unknown> = {}) => ({
  id: '33333333-3333-4333-8333-333333333333',
  category: 'collection',
  title: 'Your pickup was collected',
  body: '37.5 kg collected.',
  entity_type: 'collection_task',
  entity_id: '44444444-4444-4444-8444-444444444444',
  read_at: null,
  created_at: '2026-10-19T09:00:00Z',
  ...over,
});

const seriesBase = {
  data_kind: 'platform',
  label: 'Platform data collected by this deployment',
  unit: 'kg',
  granularity: 'weekly',
  points: 40,
  first_period: '2026-01-05',
  last_period: '2026-10-12',
  interpolated_points: 0,
  provenance: null,
};
export const platformSeries = { ...seriesBase, ref: 'platform:collected_weight_kg', name: 'Collected weight (platform)' };
export const referenceSeries = {
  ...seriesBase,
  ref: 'reference:austin',
  name: 'Austin curbside (public reference)',
  data_kind: 'public_reference',
  label: 'Public reference data, not this platform',
  provenance: {
    source_url: 'https://example.org/austin',
    source_commit: 'abc123',
    licence_note: 'CC0',
    processing_note: 'Weekly sums.',
  },
};

export const historyFixture = (series = platformSeries) => ({
  series,
  points: [
    { period_start: '2026-09-28', value: '40.000', interpolated: false },
    { period_start: '2026-10-05', value: '42.000', interpolated: false },
    { period_start: '2026-10-12', value: '41.000', interpolated: true },
  ],
});

export const forecastPointsFixture = [
  { period_start: '2026-10-19', period_end: '2026-10-26', predicted: '41.000', lower: '30.000', upper: '52.000' },
  { period_start: '2026-10-26', period_end: '2026-11-02', predicted: '42.500', lower: '31.000', upper: '54.000' },
];

export const forecastFixture = (beats: boolean | null = true) => ({
  series: platformSeries,
  model: { name: 'holt_winters', engine_version: 'ts-1.0.0', parameters: { alpha: 0.3 }, selection: 'Chosen by backtest MAE.' },
  backtest: {
    horizon_weeks: 4,
    origins: 12,
    candidate_mae: { holt_winters: 4.2, naive: 5.0 },
    selected_mae: beats === null ? null : 4.2,
    naive_mae: beats === null ? null : 5.0,
    mae_vs_naive: beats === null ? null : 0.84,
    beats_naive: beats,
  },
  interval_level: 0.8,
  points: forecastPointsFixture,
  caveats: ['Weekly totals only; holidays are not modelled.'],
  generated_at: '2026-10-20T06:00:00Z',
  saved: true,
});
