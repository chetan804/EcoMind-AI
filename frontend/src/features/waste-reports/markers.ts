import type { MapMarker, MarkerTone } from '@/features/maps';
import { toPoint } from '@/features/maps';
import { formatDateTime, humanize } from '@/utils/format';
import type { Report } from './api/reports-api';

const TONE: Record<string, MarkerTone> = { submitted: 'info', under_review: 'warning', verified: 'success', rejected: 'neutral', closed: 'neutral' };

/** Markers for reports that have coordinates. Labels are generic on purpose: no reporter identity, no free text. */
export function reportMarkers(reports: Report[]): MapMarker[] {
  const markers: MapMarker[] = [];
  for (const r of reports) {
    const position = toPoint(r.latitude, r.longitude);
    if (!position) continue;
    markers.push({
      id: `report:${r.id}`,
      position,
      title: `Waste report (${humanize(r.status)})`,
      kind: 'report',
      tone: TONE[r.status] ?? 'neutral',
      glyph: 'R',
      statusLabel: humanize(r.status),
      details: [`Reported ${formatDateTime(r.reported_at)}`],
      clusterable: true,
    });
  }
  return markers;
}
