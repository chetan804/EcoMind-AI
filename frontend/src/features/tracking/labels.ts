import type { BadgeTone } from '@/components/ui/Badge';
import { formatDateTime } from '@/utils/format';
import type { LocationSource, TrackingStatus, VehiclePosition } from './api/tracking-api';

/** Text shown for each tracking status. These strings are part of the honesty contract: only
 * LIVE GPS may be shown for a recent position from a real source. */
export const STATUS_LABEL: Record<TrackingStatus, string> = {
  live: 'LIVE GPS',
  delayed: 'DELAYED',
  stale: 'STALE',
  historical: 'HISTORICAL',
  simulated: 'SIMULATED',
  unavailable: 'LOCATION UNAVAILABLE',
};

export const STATUS_TONE: Record<TrackingStatus, BadgeTone> = {
  live: 'success',
  delayed: 'warning',
  stale: 'danger',
  historical: 'neutral',
  simulated: 'info',
  unavailable: 'neutral',
};

export const SOURCE_LABEL: Record<LocationSource, string> = {
  gps_device: 'GPS device',
  mobile_client: 'Collector mobile app',
  imported: 'Imported track',
  simulator: 'Simulator (demonstration data)',
};

export function formatAge(seconds: number): string {
  if (seconds < 60) return `${seconds} s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86_400)} d ago`;
}

export function positionDetails(row: VehiclePosition): string[] {
  const p = row.position;
  if (!p) return ['No position has ever been reported for this vehicle'];
  const lines = [`Recorded ${formatDateTime(p.recorded_at)} (${formatAge(p.age_seconds)})`, `Source: ${SOURCE_LABEL[p.source]}`];
  if (p.accuracy_m !== null) lines.push(`Accuracy about ${Math.round(p.accuracy_m)} m`);
  if (p.speed_kph !== null) lines.push(`Speed ${Math.round(p.speed_kph)} km/h`);
  if (p.heading_deg !== null) lines.push(`Heading ${Math.round(p.heading_deg)}°`);
  return lines;
}
