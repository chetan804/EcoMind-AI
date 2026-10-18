import { config } from '@/app/config';
import { Badge } from '@/components/ui/Badge';
import { getErrorMessage } from '@/services/error-handler';
import { useSystemStatus } from '../hooks/useSystemStatus';

/** Operator diagnostic: shows what the backend's /health and /ready endpoints report. */
export function SystemStatusPage() {
  const { liveness, readiness, refetch } = useSystemStatus();

  return (
    <section aria-labelledby="system-status-title">
      <h1 id="system-status-title">System status</h1>
      <p className="muted">
        API: {config.apiBaseUrl || 'same origin'} &middot;{' '}
        <button type="button" onClick={() => void refetch()}>
          Refresh
        </button>
      </p>

      <div className="card">
        <h2>API (liveness)</h2>
        {liveness.isPending && <p>Checking&hellip;</p>}
        {liveness.isError && (
          <p role="alert">
            <Badge tone="danger">Unreachable</Badge> {getErrorMessage(liveness.error)}
          </p>
        )}
        {liveness.isSuccess && <Badge tone="success">Running</Badge>}
      </div>

      <div className="card">
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
                  {check.detail ? <span className="muted"> &mdash; {check.detail}</span> : null}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
