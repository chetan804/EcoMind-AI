import { toPoint } from './lib/geo';
import type { MapMarker } from './types';
import { humanize } from '@/utils/format';

/** The fields a facility marker needs; both the full facility and the zone screen's summary satisfy it. */
export interface MappableFacility {
  id: string;
  name: string;
  facility_type: string;
  status: string;
  city: string | null;
  latitude: number | null;
  longitude: number | null;
}

/** Markers for facilities that have coordinates. No contact details, only name, type and status. */
export function facilityMarkers(facilities: MappableFacility[]): MapMarker[] {
  const markers: MapMarker[] = [];
  for (const f of facilities) {
    const position = toPoint(f.latitude, f.longitude);
    if (!position) continue;
    markers.push({
      id: `facility:${f.id}`,
      position,
      title: f.name,
      kind: f.facility_type === 'depot' ? 'depot' : 'facility',
      tone: f.status === 'active' ? 'info' : f.status === 'maintenance' ? 'warning' : 'neutral',
      glyph: f.facility_type === 'depot' ? 'D' : 'F',
      statusLabel: humanize(f.status),
      details: [humanize(f.facility_type), ...(f.city ? [f.city] : [])],
      layer: 'facilities',
      clusterable: true,
    });
  }
  return markers;
}
