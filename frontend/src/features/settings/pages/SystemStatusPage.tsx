import { config } from '@/app/config';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PageHeader } from '@/components/layout/PageHeader';
import { getErrorMessage } from '@/services/error-handler';
import { useSystemStatus } from '../hooks/useSystemStatus';

/** Operator diagnostic: shows what the backend's /health and /ready endpoints report. */
export function SystemStatusPage() {
  const { liveness, readiness, refetch } = useSystemStatus();

  return (
    <section aria-labelledby="system-status-title" className="status-stack">
      <PageHeader
        title="System status"
        titleId="system-status-title"
        subtitle={`API: ${config.apiBaseUrl || 'same origin'}`}
        actions={
          <Button variant="secondary" onClick={() => void refetch()}>
            Refresh
          </Button>
        }
      />

      <Card>
        <h2>API (liveness)</h2>
        {liveness.isPending && <p>Checking&hellip;</p>}
        {liveness.isError && (
          <p role="alert">
            <Badge tone="danger">Unreachable</Badge> {getErrorMessage(liveness.error)}
          </p>
        )}
        {liveness.isSuccess && <Badge tone="success">Running</Badge>}
      </Card>

      <Card>
        <h2>Dependencies (readiness)</h2>
        {readiness.isPending && <p>Checking&hellip;</p>}
        {readiness.isError && (
          <p role="alert">
            <Badge tone="danger">Unknown</Badge> {getErrorMessage(readiness.error)}
          </p>
        )}
        {readiness.isSuccess && (
          <>
            <p>
              {readiness.data.status === 'ready' ? (
                <Badge tone="success">Ready</Badge>
              ) : (
                <Badge tone="danger">Not ready</Badge>
              )}
            </p>
            <ul>
              {Object.entries(readiness.data.checks).map(([name, check]) => (
                <li key={name}>
                  <strong>{name}</strong>: {check.status === 'ok' ? 'ok' : 'failed'}
                  {check.detail ? <span className="text-muted"> &mdash; {check.detail}</span> : null}
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </section>
  );
}
