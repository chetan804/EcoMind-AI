import type { MapMarker, MarkerTone } from '@/features/maps';
import { toPoint } from '@/features/maps';
import { formatDateTime, humanize } from '@/utils/format';
import type { Incident } from './api/incidents-api';

const TONE: Record<string, MarkerTone> = { open: 'warning', acknowledged: 'info', in_progress: 'info', resolved: 'success', dismissed: 'neutral' };

/** Markers for incidents that have coordinates. Labels carry type and status only: no reporter, no free text. */
export function incidentMarkers(incidents: Incident[]): MapMarker[] {
  const markers: MapMarker[] = [];
  for (const i of incidents) {
    const position = toPoint(i.latitude, i.longitude);
    if (!position) continue;
    markers.push({
      id: `incident:${i.id}`,
      position,
      title: `${humanize(i.incident_type)} (${humanize(i.status)})`,
      kind: 'incident',
      tone: TONE[i.status] ?? 'neutral',
      glyph: '!',
      statusLabel: humanize(i.status),
      details: [`Reported ${formatDateTime(i.created_at)}`],
      clusterable: true,
    });
  }
  return markers;
}
