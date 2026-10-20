import '../analytics.css';
import { useState } from 'react';
import { Card, CardHeader } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Input';
import { Table } from '@/components/ui/Table';
import { CountList } from '@/components/ui/StatList';
import { Alert } from '@/components/feedback/Alert';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { formatDate, formatKg, formatNumber, formatPercent } from '@/utils/format';
import { CollectedWeightChart } from '../components/CollectedWeightChart';
import { useOverview, useWeeklyTrend } from '../hooks/useAnalytics';

const WINDOWS = [7, 30, 90, 365];
const WEEKS = [8, 12, 26, 52];

/** Executive analytics: every figure is an aggregate the server computed from stored records. */
export function AnalyticsPage() {
  const [windowDays, setWindowDays] = useState(30);
  const [weeks, setWeeks] = useState(12);
  const overview = useOverview(windowDays);
  const trend = useWeeklyTrend(weeks);

  return (
    <section aria-labelledby="analytics-title" className="stack">
      <PageHeader
        title="Executive analytics"
        titleId="analytics-title"
        subtitle="Live aggregates from the platform database"
        actions={
          <Field label="Reporting window">
            {(control) => (
              <Select {...control} value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))}>
                {WINDOWS.map((d) => (
                  <option key={d} value={d}>{`Last ${d} days`}</option>
                ))}
              </Select>
            )}
          </Field>
        }
      />

      <QueryBoundary query={overview} label="analytics">
        {(o) => (
          <>
            <div className="kpi-row">
              <Card aria-label="Collected weight">
                <p className="muted">Collected, last {o.window_days} days</p>
                <p className="analytics-figure">{formatKg(o.collection.collected_weight_kg_in_window)}</p>
                <p className="muted">All time: {formatKg(o.collection.collected_weight_kg_total)}</p>
              </Card>
              <Card aria-label="Open collection tasks">
                <p className="muted">Open collection tasks</p>
                <p className="analytics-figure">{o.collection.open_tasks}</p>
                <p className="muted">{o.collection.overdue_tasks} overdue</p>
              </Card>
              <Card aria-label="Material recovery">
                <p className="muted">Recovery rate (verified records)</p>
                <p className="analytics-figure">{formatPercent(o.recovery.recovery_rate)}</p>
                <p className="muted">
                  {o.recovery.verified_records} verified, {o.recovery.pending_records} awaiting verification
                </p>
              </Card>
              <Card aria-label="Community incidents">
                <p className="muted">Open incidents</p>
                <p className="analytics-figure">{o.incidents.open_incidents}</p>
                <p className="muted">{o.incidents.unassigned_open} unassigned</p>
              </Card>
            </div>

            <div className="grid-3">
              <Card aria-labelledby="an-tasks">
                <CardHeader title="Collection tasks by status" titleId="an-tasks" />
                <CountList items={o.collection.by_status} label="Collection tasks by status" />
              </Card>
              <Card aria-labelledby="an-reports">
                <CardHeader title="Waste reports by status" titleId="an-reports" />
                <CountList items={o.reports.by_status} label="Waste reports by status" />
                <p className="muted">{o.reports.in_window} submitted in the last {o.window_days} days</p>
              </Card>
              <Card aria-labelledby="an-fleet">
                <CardHeader title="Fleet and facilities" titleId="an-fleet" />
                <CountList items={o.fleet.by_status} label="Vehicles by status" />
                <p className="muted">
                  Capacity available: {formatKg(o.fleet.capacity_kg_available)}. Facilities active: {o.facilities.active} of{' '}
                  {o.facilities.total}.
                </p>
              </Card>
            </div>

            <div className="grid-3">
              <Card aria-labelledby="an-anomalies">
                <CardHeader title="Suspected anomalies" titleId="an-anomalies" />
                <p className="analytics-figure">{o.anomalies.open_alerts}</p>
                <p className="muted">
                  open ({o.anomalies.critical_open} critical). Suspected anomalies are statistical flags, not confirmed incidents.
                </p>
              </Card>
              <Card aria-labelledby="an-rewards">
                <CardHeader title="Rewards ledger" titleId="an-rewards" />
                <p className="analytics-figure">{formatNumber(o.rewards.net_points)} points</p>
                <p className="muted">
                  {o.rewards.entries} entries across {o.rewards.users} people; {formatKg(o.rewards.impact_weight_kg)} of recorded
                  impact weight.
                </p>
              </Card>
              <Card aria-labelledby="an-passports">
                <CardHeader title="Material passports" titleId="an-passports" />
                <CountList items={o.passports.by_status} label="Passports by status" />
              </Card>
            </div>
            <Alert tone="info">{o.basis}</Alert>
          </>
        )}
      </QueryBoundary>

      <Card aria-labelledby="an-trend">
        <CardHeader
          title="Weekly collected weight"
          titleId="an-trend"
          actions={
            <Field label="Weeks shown">
              {(control) => (
                <Select {...control} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}>
                  {WEEKS.map((w) => (
                    <option key={w} value={w}>{`${w} weeks`}</option>
                  ))}
                </Select>
              )}
            </Field>
          }
        />
        <QueryBoundary query={trend} label="the weekly trend">
          {(t) => (
            <>
              <CollectedWeightChart trend={t} />
              <Table caption="Weekly activity" captionHidden>
                <thead>
                  <tr>
                    <th scope="col">Week starting</th>
                    <th scope="col">Collected weight</th>
                    <th scope="col">Tasks completed</th>
                    <th scope="col">Reports submitted</th>
                  </tr>
                </thead>
                <tbody>
                  {[...t.points].reverse().map((p) => (
                    <tr key={p.week_start}>
                      <th scope="row">{formatDate(p.week_start)}</th>
                      <td>{formatKg(p.collected_weight_kg)}</td>
                      <td>{p.tasks_completed}</td>
                      <td>{p.reports_submitted}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <p className="muted">{t.basis}</p>
            </>
          )}
        </QueryBoundary>
      </Card>
    </section>
  );
}
