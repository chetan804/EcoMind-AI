import type { MapMarker, MarkerTone } from '@/features/maps';
import { toPoint } from '@/features/maps';
import type { TrackingStatus, VehiclePosition } from './api/tracking-api';
import { positionDetails, STATUS_LABEL } from './labels';

const TONE: Record<TrackingStatus, MarkerTone> = {
  live: 'success',
  delayed: 'warning',
  stale: 'danger',
  historical: 'neutral',
  simulated: 'simulated',
  unavailable: 'neutral',
};

/** One marker per vehicle position that exists. A vehicle with no position gets NO marker: there
 * is nothing true to draw, and a pin at a depot or at 0,0 would pretend otherwise. */
export function vehicleMarkers(rows: VehiclePosition[]): MapMarker[] {
  const markers: MapMarker[] = [];
  for (const row of rows) {
    if (!row.position) continue;
    const position = toPoint(row.position.latitude, row.position.longitude);
    if (!position) continue;
    markers.push({
      id: `vehicle:${row.vehicle_id}:${row.simulated ? 'sim' : 'real'}`,
      position,
      title: row.simulated ? `${row.registration_number} (simulated)` : row.registration_number,
      kind: 'vehicle',
      tone: TONE[row.status],
      glyph: row.simulated ? 'S' : 'V',
      statusLabel: STATUS_LABEL[row.status],
      details: positionDetails(row),
      layer: row.simulated ? 'vehicles-simulated' : 'vehicles',
      clusterable: true,
    });
  }
  return markers;
}
