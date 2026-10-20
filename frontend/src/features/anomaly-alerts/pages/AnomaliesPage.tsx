import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { Alert as Notice } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Select, Textarea } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { useSeriesList } from '@/features/forecasting';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDate, formatDateTime, formatNumber, humanize } from '@/utils/format';
import type { Alert, AlertAction, ScanResult } from '../api/anomalies-api';
import { useAlerts, useScan, useTransition } from '../hooks/useAnomalies';

const SEVERITY_TONES: Record<string, BadgeTone> = { info: 'info', warning: 'warning', critical: 'danger' };
const STATUS_TONES: Record<string, BadgeTone> = { open: 'warning', acknowledged: 'info', resolved: 'success', false_positive: 'neutral' };
const ACTION_LABELS: Record<AlertAction, string> = {
  acknowledge: 'Acknowledge',
  resolve: 'Resolve',
  'false-positive': 'Mark as false positive',
};

/** What each status permits, mirroring the server's lifecycle. */
function actionsFor(status: Alert['status']): AlertAction[] {
  if (status === 'open') return ['acknowledge', 'resolve', 'false-positive'];
  if (status === 'acknowledged') return ['resolve', 'false-positive'];
  return [];
}

export function AnomaliesPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ page: 1, status: 'open', severity: '', data_kind: 'platform' });
  const query = useAlerts(filters);
  const [pending, setPending] = useState<{ alert: Alert; action: AlertAction } | null>(null);
  const [scanning, setScanning] = useState(false);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  return (
    <section aria-labelledby="anomalies-title" className="stack stack--tight">
      <PageHeader
        title="Anomaly detection"
        titleId="anomalies-title"
        subtitle="Suspected anomalies are statistical flags for review, not confirmed incidents"
        actions={can('anomalies:manage') ? <Button onClick={() => setScanning(true)}>Scan a series</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All statuses</option>
              {['open', 'acknowledged', 'resolved', 'false_positive'].map((s) => (
                <option key={s} value={s}>
                  {humanize(s)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Severity">
          {(c) => (
            <Select {...c} value={filters.severity} onChange={(e) => set({ severity: e.target.value })}>
              <option value="">All severities</option>
              {['critical', 'warning', 'info'].map((s) => (
                <option key={s} value={s}>
                  {humanize(s)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Data">
          {(c) => (
            <Select {...c} value={filters.data_kind} onChange={(e) => set({ data_kind: e.target.value })}>
              <option value="platform">Platform data</option>
              <option value="public_reference">Public reference data</option>
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="anomalies">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState
              icon={<ShieldCheck size={24} />}
              title="No suspected anomalies match these filters"
              description="Run a scan over a series to look for unusual weeks. Nothing is flagged until a scan has run."
            />
          ) : (
            <>
              <Table caption="Suspected anomalies">
                <thead>
                  <tr>
                    <th scope="col">Series</th>
                    <th scope="col">Week</th>
                    <th scope="col">Observed</th>
                    <th scope="col">Expected</th>
                    <th scope="col">Severity</th>
                    <th scope="col">Status</th>
                    <th scope="col">Detected</th>
                    <th scope="col">
                      <span className="visually-hidden">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((a) => (
                    <tr key={a.id}>
                      <th scope="row">
                        {a.metric}
                        {a.data_kind === 'public_reference' && (
                          <>
                            {' '}
                            <Badge tone="warning">Reference data</Badge>
                          </>
                        )}
                        <p className="muted">{a.explanation}</p>
                      </th>
                      <td>{formatDate(a.window_start)}</td>
                      <td>
                        {formatNumber(a.observed_value)} {a.unit}
                      </td>
                      <td>{formatNumber(a.expected_value)}</td>
                      <td>
                        <StatusBadge value={a.severity} tones={SEVERITY_TONES} />
                      </td>
                      <td>
                        <StatusBadge value={a.status} tones={STATUS_TONES} />
                      </td>
                      <td>{formatDateTime(a.detected_at)}</td>
                      <td>
                        {can('anomalies:manage') && (
                          <div className="row-actions">
                            {actionsFor(a.status).map((action) => (
                              <Button
                                key={action}
                                variant="secondary"
                                onClick={() => setPending({ alert: a, action })}
                                aria-label={`${ACTION_LABELS[action]}: ${a.metric}, week of ${formatDate(a.window_start)}`}
                              >
                                {ACTION_LABELS[action]}
                              </Button>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} suspected anomal${data.total === 1 ? 'y' : 'ies'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {pending && <TransitionDialog key={pending.alert.id + pending.action} {...pending} onClose={() => setPending(null)} />}
      {scanning && <ScanDialog onClose={() => setScanning(false)} />}
    </section>
  );
}

function TransitionDialog({ alert, action, onClose }: { alert: Alert; action: AlertAction; onClose: () => void }) {
  const [note, setNote] = useState('');
  const mutation = useTransition();
  return (
    <Dialog
      open
      onClose={onClose}
      title={ACTION_LABELS[action]}
      description={`${alert.metric}, week of ${formatDate(alert.window_start)}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={mutation.isPending} onClick={() => mutation.mutate({ id: alert.id, action, note: note.trim() }, { onSuccess: onClose })}>
            {ACTION_LABELS[action]}
          </Button>
        </>
      }
    >
      <Field label="Note (optional)">{(c) => <Textarea {...c} data-autofocus value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />}</Field>
      {mutation.isError && <Notice tone="danger">{getErrorMessage(mutation.error)}</Notice>}
    </Dialog>
  );
}

function ScanDialog({ onClose }: { onClose: () => void }) {
  const list = useSeriesList();
  const [series, setSeries] = useState('');
  const [result, setResult] = useState<ScanResult | null>(null);
  const scan = useScan();
  const chosen = series || list.data?.[0]?.ref || '';
  return (
    <Dialog
      open
      onClose={onClose}
      title="Scan a series"
      description="Looks for weeks that differ unusually from the series' own recent pattern. Re-scanning never duplicates a flag."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button loading={scan.isPending} disabled={!chosen} onClick={() => scan.mutate({ series: chosen, lookback_weeks: 26 }, { onSuccess: setResult })}>
            Run scan
          </Button>
        </>
      }
    >
      <Field label="Series">
          {(c) => (
            <Select {...c} data-autofocus value={chosen} onChange={(e) => setSeries(e.target.value)}>
              {(list.data ?? []).map((s) => (
                <option key={s.ref} value={s.ref}>
                  {s.name}
                </option>
              ))}
            </Select>
          )}
      </Field>
      {list.isError && <Notice tone="danger">{getErrorMessage(list.error)}</Notice>}
      {scan.isError && <Notice tone="danger">{getErrorMessage(scan.error)}</Notice>}
      {result && (
        <Notice tone={result.created > 0 ? 'warning' : 'success'} title="Scan complete">
          Looked at {result.weeks_scanned} weeks with {result.detector}: {result.flagged} flagged, {result.created} new,{' '}
          {result.already_recorded} already recorded. {result.caveat}
        </Notice>
      )}
    </Dialog>
  );
}
