import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { CheckCircle2, ClipboardList, Layers, Recycle, ShieldAlert, TriangleAlert, UserCheck, Clock } from 'lucide-react';
import { DonutChart } from '@/components/data-display/DonutChart';
import { MetricTile } from '@/components/data-display/MetricTile';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardHeader } from '@/components/ui/Card';
import { CountList } from '@/components/ui/StatList';
import { useRequests } from '@/features/access-requests';
import { useTasks } from '@/features/collection';
import { CollectedWeightChart, useOverview, useWeeklyTrend, type Overview } from '@/features/analytics';
import { FleetMap } from '@/features/tracking';
import { useAuth } from '@/services/session';
import { formatKg, formatPercent, humanize } from '@/utils/format';
import '../dashboard.css';

const SEGMENT_COLORS = ['var(--color-accent-text)', 'var(--color-info)', 'var(--color-warning)', 'var(--color-danger)', 'var(--color-success)', 'var(--color-text-muted)'];

function greeting(date = new Date()): string {
  const hour = date.getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

/** Operations overview for people who may read analytics; a plain starting page for everyone else. */
export function DashboardPage() {
  const { can, user } = useAuth();
  return (
    <>
      <Topbar />
      {can('analytics:read') ? <OperationsOverview /> : <MemberHome name={user?.full_name ?? null} />}
    </>
  );
}

function OperationsOverview() {
  const { can } = useAuth();
  const overview = useOverview(30);
  const trend = useWeeklyTrend(12);
  return (
    <>
      <PageHeader title={greeting()} subtitle="Operations overview, last 30 days" />
      <div className="dash">
        <QueryBoundary query={overview} label="the operations overview">
          {(o) => {
            const statuses = o.collection.by_status.filter((c) => c.count > 0);
            const total = statuses.reduce((sum, c) => sum + c.count, 0);
            return (
              <>
                <ul className="dash__kpis" aria-label="Key metrics">
                  <li>
                    <Card className="dash__kpi">
                      <MetricTile icon={<Recycle size={28} />} label="Collected, 30 days" value={formatKg(o.collection.collected_weight_kg_in_window)} />
                    </Card>
                  </li>
                  <li>
                    <Card className="dash__kpi">
                      <MetricTile
                        icon={<ClipboardList size={28} />}
                        tone="blue"
                        label="Open collection tasks"
                        value={String(o.collection.open_tasks)}
                        note={`${o.collection.overdue_tasks} overdue`}
                      />
                    </Card>
                  </li>
                  <li>
                    <Card className="dash__kpi">
                      <MetricTile
                        icon={<Layers size={28} />}
                        label="Recovery rate"
                        value={formatPercent(o.recovery.recovery_rate)}
                        note={o.recovery.recovery_rate === null ? 'No verified records yet' : `${o.recovery.verified_records} verified record${o.recovery.verified_records === 1 ? '' : 's'}`}
                      />
                    </Card>
                  </li>
                  <li>
                    <Card className="dash__kpi">
                      <MetricTile
                        icon={<TriangleAlert size={28} />}
                        tone={o.anomalies.critical_open > 0 ? 'red' : 'amber'}
                        label="Open suspected anomalies"
                        value={String(o.anomalies.open_alerts)}
                        note={`${o.anomalies.critical_open} critical · ${o.incidents.open_incidents} open incidents`}
                      />
                    </Card>
                  </li>
                </ul>

                <div className="dash__row dash__row--main">
                  <Card className="dash__chart-card" aria-labelledby="trend-title">
                    <CardHeader title="Weekly collected weight" titleId="trend-title" actions={<span className="dash__range">Last 12 weeks</span>} />
                    <QueryBoundary query={trend} label="the weekly trend">
                      {(t) => <CollectedWeightChart trend={t} height={195} />}
                    </QueryBoundary>
                  </Card>
                  <Card aria-labelledby="status-title">
                    <CardHeader title="Collection tasks by status" titleId="status-title" />
                    {total === 0 ? (
                      <p className="muted">No collection tasks have been created yet.</p>
                    ) : (
                      <DonutChart
                        ariaLabel="Collection tasks by status"
                        center={<strong>{total}</strong>}
                        segments={statuses.map((c, i) => ({
                          label: humanize(c.key),
                          value: (c.count / total) * 100,
                          color: SEGMENT_COLORS[i % SEGMENT_COLORS.length] ?? 'var(--color-accent-text)',
                        }))}
                      />
                    )}
                  </Card>
                </div>

                <Card aria-labelledby="attention-title">
                  <CardHeader title="Needs attention" titleId="attention-title" />
                  <AttentionList overview={o} />
                </Card>

                {can('fleet:read') && (
                  <Card aria-labelledby="map-title">
                    <CardHeader title="Fleet and facilities map" titleId="map-title" />
                    <FleetMap height={380} />
                  </Card>
                )}

                <div className="dash__row dash__row--summary">
                  <Card aria-labelledby="fleet-title">
                    <CardHeader title="Fleet" titleId="fleet-title" />
                    <CountList items={o.fleet.by_status} label="Vehicles by status" />
                    <p className="muted">Capacity available: {formatKg(o.fleet.capacity_kg_available)}</p>
                  </Card>
                  <Card aria-labelledby="reports-title">
                    <CardHeader title="Waste reports" titleId="reports-title" />
                    <CountList items={o.reports.by_status} label="Waste reports by status" />
                  </Card>
                  <Card aria-labelledby="passports-title">
                    <CardHeader title="Material passports" titleId="passports-title" />
                    <CountList items={o.passports.by_status} label="Passports by status" />
                    <p className="muted">
                      <Link to="/analytics">Executive analytics</Link>
                    </p>
                  </Card>
                </div>
                <p className="muted">{o.basis}</p>
              </>
            );
          }}
        </QueryBoundary>
      </div>
    </>
  );
}

const MEMBER_LINKS = [
  { permission: 'waste_reports:create', to: '/classify', title: 'Classify an item', body: 'Photograph an item and get sorting guidance.' },
  { permission: 'collection:read', to: '/collection', title: 'Collections', body: 'Your collection tasks.' },
  { permission: 'notifications:read_own', to: '/notifications', title: 'Notifications', body: 'Updates about your reports and tasks.' },
  { permission: 'rewards:read_own', to: '/rewards', title: 'Rewards', body: 'Your points and recorded impact.' },
];

function MemberHome({ name }: { name: string | null }) {
  const { can } = useAuth();
  const links = MEMBER_LINKS.filter((l) => can(l.permission));
  return (
    <>
      <PageHeader title={`${greeting()}${name ? `, ${name}` : ''}`} subtitle="What would you like to do?" />
      {can('collection:read') && <MyTasks />}
      <ul className="member-links">
        {links.map((l) => (
          <li key={l.to}>
            <Card>
              <h2 className="member-links__title">
                <Link to={l.to}>{l.title}</Link>
              </h2>
              <p className="muted">{l.body}</p>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}

type AttentionItem = { key: string; icon: ReactNode; tone: 'danger' | 'warning'; text: string; to: string };

/** Things a manager can act on now, derived only from the counts above; nothing is invented. */
function AttentionList({ overview: o }: { overview: Overview }) {
  const { can } = useAuth();
  const pending = useRequests({ status_filter: 'pending', page: 1 }, can('users:manage'));
  const items: AttentionItem[] = [];
  if (o.collection.overdue_tasks > 0)
    items.push({ key: 'overdue', icon: <Clock size={18} />, tone: 'danger', text: `${o.collection.overdue_tasks} overdue collection task${o.collection.overdue_tasks === 1 ? '' : 's'}`, to: '/collection' });
  if (o.anomalies.critical_open > 0)
    items.push({ key: 'critical', icon: <TriangleAlert size={18} />, tone: 'danger', text: `${o.anomalies.critical_open} critical suspected anomal${o.anomalies.critical_open === 1 ? 'y' : 'ies'} to review`, to: '/anomalies' });
  else if (o.anomalies.open_alerts > 0)
    items.push({ key: 'anomalies', icon: <TriangleAlert size={18} />, tone: 'warning', text: `${o.anomalies.open_alerts} suspected anomal${o.anomalies.open_alerts === 1 ? 'y' : 'ies'} awaiting review`, to: '/anomalies' });
  if (o.incidents.unassigned_open > 0)
    items.push({ key: 'incidents', icon: <ShieldAlert size={18} />, tone: 'warning', text: `${o.incidents.unassigned_open} open incident${o.incidents.unassigned_open === 1 ? '' : 's'} with nobody assigned`, to: '/incidents' });
  if (o.recovery.pending_records > 0)
    items.push({ key: 'recovery', icon: <Layers size={18} />, tone: 'warning', text: `${o.recovery.pending_records} recovery record${o.recovery.pending_records === 1 ? '' : 's'} waiting for verification`, to: '/recovery' });
  const waiting = pending.data?.total ?? 0;
  if (waiting > 0)
    items.push({ key: 'roles', icon: <UserCheck size={18} />, tone: 'warning', text: `${waiting} role request${waiting === 1 ? '' : 's'} waiting for a decision`, to: '/settings/users' });
  if (items.length === 0)
    return (
      <p className="attention__clear">
        <CheckCircle2 size={18} aria-hidden="true" /> Nothing needs attention right now.
      </p>
    );
  return (
    <ul className="attention" aria-label="Items that need attention">
      {items.map((item) => (
        <li key={item.key}>
          <Link to={item.to} className="attention__row">
            <span className={`alert-row__icon alert-row__icon--${item.tone}`} aria-hidden="true">
              {item.icon}
            </span>
            <span className="alert-row__title">{item.text}</span>
            <span className="attention__go">Open</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** A collector's own open tasks, read from the collection API (only tasks assigned to the signed-in person). */
function MyTasks() {
  const query = useTasks({ page: 1, q: '', status: '', priority: '', mine: true });
  const open = (query.data?.items ?? []).filter((t) => t.status === 'assigned' || t.status === 'in_progress').slice(0, 5);
  return (
    <Card aria-labelledby="my-tasks-title">
      <CardHeader title="My open tasks" titleId="my-tasks-title" actions={<Link to="/collection">All collections</Link>} />
      <QueryBoundary query={query} label="your tasks">
        {() =>
          open.length === 0 ? (
            <p className="muted">No tasks are assigned to you right now.</p>
          ) : (
            <ul className="attention" aria-label="Your open tasks">
              {open.map((t) => (
                <li key={t.id}>
                  <Link to="/collection" className="attention__row">
                    <span className="alert-row__title">{t.title}</span>
                    <span className="attention__go">{humanize(t.status)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )
        }
      </QueryBoundary>
    </Card>
  );
}
