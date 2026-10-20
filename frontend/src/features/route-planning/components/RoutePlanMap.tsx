import { useMemo } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { decodePolyline, MapPanel, toPoint, type GeoPoint, type MapMarker, type MapPath } from '@/features/maps';
import { SimulationControls, useRouteTracking, vehicleMarkers } from '@/features/tracking';
import { useAuth } from '@/services/session';
import { formatNumber } from '@/utils/format';
import type { PlanDetail } from '../api/routes-api';
import { useRoadRoute } from '../hooks/useRoutes';

const REASON_TEXT: Record<string, string> = {
  not_configured: 'Road routing is not configured on this server (no routing provider is enabled), so only straight lines are shown.',
  too_few_points: 'The plan has too few located points for a road route.',
  access_denied: 'The routing provider rejected the request (check the credentials and access for the provider).',
  quota_exceeded: 'The routing provider quota was exceeded.',
  provider_error: 'The routing provider reported an error.',
  timeout: 'The routing provider did not answer in time.',
  network_error: 'The routing provider could not be reached.',
  bad_response: 'The routing provider returned an unusable answer.',
  no_route: 'The routing provider found no drivable route through these stops.',
};

function minutes(seconds: number): string {
  const m = Math.round(seconds / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

/** The plan on a map: numbered stops, road geometry if the provider supplied it, otherwise labelled straight lines. */
export function RoutePlanMap({ plan }: { plan: PlanDetail }) {
  const { can } = useAuth();
  const simulate = can('fleet:simulate');
  const road = useRoadRoute(plan.id, plan.status !== 'cancelled');
  const tracking = useRouteTracking(plan.id, simulate);

  const view = useMemo(() => {
    const start = toPoint(plan.start_latitude ?? null, plan.start_longitude ?? null);
    const stopPoints: GeoPoint[] = plan.stops.flatMap((s) => {
      const p = toPoint(s.latitude, s.longitude);
      return p ? [p] : [];
    });
    const straight: GeoPoint[] = start ? [start, ...stopPoints, start] : stopPoints;
    const done = new Set((tracking.data?.stops ?? []).filter((s) => s.completed).map((s) => s.sequence));
    const markers: MapMarker[] = [];
    if (start) {
      markers.push({ id: 'start', position: start, title: plan.start_label ?? 'Start depot', kind: 'depot', tone: 'info', glyph: 'D', statusLabel: 'Start and end depot', layer: 'stops' });
    }
    for (const s of plan.stops) {
      const position = toPoint(s.latitude, s.longitude);
      if (!position) continue;
      markers.push({
        id: `stop:${s.sequence}`,
        position,
        title: `Stop ${s.sequence}: ${s.label}`,
        kind: s.kind === 'facility' ? 'facility' : 'stop',
        tone: done.has(s.sequence) ? 'success' : 'info',
        glyph: String(s.sequence),
        statusLabel: done.has(s.sequence) ? 'Completed (from the collection task)' : 'Planned',
        details: [`Leg distance ${formatNumber(s.leg_distance_km)} km (straight line)`],
        layer: 'stops',
      });
    }
    const paths: MapPath[] = [];
    const roadPoints = road.data?.available ? road.data.encoded_polylines.flatMap((e) => decodePolyline(e)) : [];
    if (roadPoints.length >= 2) {
      paths.push({ id: 'road', kind: 'planned_road', points: roadPoints, label: 'Planned route on roads (routing provider, no live traffic)' });
    } else if (straight.length >= 2) {
      paths.push({ id: 'straight', kind: 'planned_straight', points: straight, label: 'Straight lines between stops. Not roads and not a driving route' });
    }
    const recorded = (tracking.data?.path ?? []).flatMap((p) => {
      const point = toPoint(p.latitude, p.longitude);
      return point ? [point] : [];
    });
    if (recorded.length >= 2) {
      paths.push({
        id: 'recorded',
        kind: tracking.data?.path_simulated ? 'simulated' : 'recorded',
        points: recorded,
        label: tracking.data?.path_simulated ? 'Simulated vehicle path (demonstration data)' : 'Recorded vehicle path',
      });
    }
    if (tracking.data?.vehicle) markers.push(...vehicleMarkers([tracking.data.vehicle]));
    return { markers, paths, roadPoints, straight };
  }, [plan, road.data, tracking.data]);

  const roadOk = road.data?.available === true && view.roadPoints.length >= 2;
  const simPath = roadOk ? view.roadPoints : view.straight;
  return (
    <div className="stack stack--tight">
      {roadOk && road.data ? (
        <p>
          <strong>Road route:</strong> {road.data.distance_m !== null ? `${formatNumber(Math.round(road.data.distance_m / 100) / 10)} km` : '—'}
          {road.data.duration_s !== null && `, about ${minutes(road.data.duration_s)}`} (provider estimate{road.data.traffic_aware ? '' : ', no live traffic'}).
        </p>
      ) : (
        <Alert tone="warning" title="No road route: straight-line fallback">
          {road.isPending ? 'Asking the routing provider…' : (REASON_TEXT[road.data?.reason ?? ''] ?? 'The road route could not be loaded.')} The dashed line joins the stops directly and is not a driving route; the
          distances in the table are straight-line estimates.
        </Alert>
      )}
      <MapPanel
        label="Route plan"
        markers={view.markers}
        paths={view.paths}
        height={340}
        emptyMessage="This plan has no located stops."
        legend={[
          { key: 'road', label: 'Route on roads (provider)', pathKind: 'planned_road' },
          { key: 'straight', label: 'Straight-line fallback (not roads)', pathKind: 'planned_straight' },
          { key: 'rec', label: 'Recorded vehicle path', pathKind: 'recorded' },
          { key: 'sim', label: 'Simulated path', pathKind: 'simulated' },
          { key: 'stop', label: 'Numbered stop (green once its task is completed)', tone: 'info' },
        ]}
      />
      {tracking.data && tracking.data.total_task_stops > 0 && (
        <p className="muted">
          Progress: {tracking.data.completed_task_stops} of {tracking.data.total_task_stops} task stops completed (from collection task status).
        </p>
      )}
      <div className="row-actions">
        <Button variant="secondary" loading={road.isFetching && !road.isPending} onClick={() => void road.refetch()}>
          Recompute road route
        </Button>
        <span className="muted">The stop order is set by the platform&apos;s straight-line optimiser; recomputing re-asks the provider for the road geometry and does not reorder stops.</span>
      </div>
      {plan.vehicle_id && simulate && (
        <SimulationControls
          vehicleId={plan.vehicle_id}
          routePlanId={plan.id}
          path={simPath}
          pathDescription={roadOk ? 'The simulated vehicle follows the provider road geometry.' : 'No road geometry is available, so the simulated vehicle moves along straight lines between the stops.'}
        />
      )}
    </div>
  );
}
