import { useEffect, useMemo, useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { headingDeg, pointsAlong, type GeoPoint } from '@/features/maps';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { useSimulation, useTrackingConfig } from '../hooks/useTracking';

export const SIM_STEP_M = 150;
export const SIM_TICK_MS = 2000;

/**
 * Demonstration driver for one vehicle. It walks the given path one step per tick and posts each
 * point with source "simulator" through the dedicated, separately authorised endpoint. Simulated
 * positions are labelled SIMULATED everywhere, are stored apart from real GPS history, and never
 * touch collection tasks. The path is whatever the caller passes: road geometry only if it came
 * from the routing provider, otherwise straight lines (and `pathDescription` says which).
 */
export function SimulationControls({ vehicleId, path, pathDescription, routePlanId }: { vehicleId: string; path: GeoPoint[]; pathDescription: string; routePlanId?: string }) {
  const { can } = useAuth();
  const config = useTrackingConfig(can('fleet:simulate'));
  const { post, reset } = useSimulation();
  const postStep = post.mutate; // stable across renders in TanStack Query v5
  const points = useMemo(() => pointsAlong(path, SIM_STEP_M), [path]);
  const [step, setStep] = useState(0);
  const [running, setRunning] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const total = points.length;
  useEffect(() => {
    if (!running) return undefined;
    const timer = window.setInterval(() => {
      setStep((current) => {
        const point = points[current];
        if (!point) {
          setRunning(false);
          return current;
        }
        const next = points[current + 1];
        postStep(
          {
            vehicleId,
            body: {
              latitude: point.lat.toFixed(6),
              longitude: point.lng.toFixed(6),
              ...(next ? { heading_deg: headingDeg(point, next).toFixed(2) } : {}),
              ...(routePlanId ? { route_plan_id: routePlanId } : {}),
            },
          },
          { onError: (error) => { setFailure(getErrorMessage(error)); setRunning(false); } },
        );
        if (current + 1 >= total) setRunning(false);
        return current + 1;
      });
    }, SIM_TICK_MS);
    return () => window.clearInterval(timer);
  }, [running, points, vehicleId, routePlanId, total, postStep]);

  if (!can('fleet:simulate') || !config.data?.simulator_enabled) return null;
  const finished = step >= total && total > 0;
  return (
    <section aria-labelledby="sim-title" className="stack stack--tight">
      <h3 id="sim-title" className="card__title">Simulation (demonstration only)</h3>
      <Alert tone="info" title="Simulated positions are not real GPS">
        {pathDescription} Each step is stored with source “simulator”, labelled SIMULATED, kept apart from real vehicle history and never attached to collection tasks.
      </Alert>
      {total < 2 ? (
        <Alert tone="warning">This plan has no usable path to simulate.</Alert>
      ) : (
        <div className="filter-bar">
          {!running ? (
            <Button onClick={() => { setFailure(null); if (finished) setStep(0); setRunning(true); }}>{step === 0 || finished ? 'Start simulation' : 'Resume'}</Button>
          ) : (
            <Button variant="secondary" onClick={() => setRunning(false)}>Pause</Button>
          )}
          <Button
            variant="secondary"
            loading={reset.isPending}
            onClick={() => { setRunning(false); setStep(0); reset.mutate(vehicleId, { onError: (e) => setFailure(getErrorMessage(e)) }); }}
          >
            Reset simulation
          </Button>
          <span role="status" aria-live="polite">{`Step ${Math.min(step, total)} of ${total}${running ? ' (running)' : finished ? ' (finished)' : step > 0 ? ' (paused)' : ''}`}</span>
        </div>
      )}
      {failure && <Alert tone="danger">{failure}</Alert>}
    </section>
  );
}
