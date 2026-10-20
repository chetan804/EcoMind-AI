import { describe, expect, it } from 'vitest';
import { formatAge, pollingInterval, STATUS_LABEL, vehicleMarkers, type VehiclePosition } from '@/features/tracking';
import { positionDetails } from '@/features/tracking/labels';
import { MAX_POLL_MS, POLL_MS } from '@/features/tracking/hooks/useTracking';

const position = (over: Partial<NonNullable<VehiclePosition['position']>> = {}): NonNullable<VehiclePosition['position']> => ({
  latitude: 17.4,
  longitude: 78.5,
  recorded_at: '2026-10-21T08:00:00Z',
  received_at: '2026-10-21T08:00:01Z',
  source: 'gps_device',
  accuracy_m: 8,
  speed_kph: 32,
  heading_deg: 90,
  age_seconds: 5,
  collection_task_id: null,
  route_plan_id: null,
  ...over,
});
const row = (over: Partial<VehiclePosition> = {}): VehiclePosition => ({
  vehicle_id: '1',
  registration_number: 'TS09-1234',
  vehicle_type: 'van',
  vehicle_status: 'in_service',
  simulated: false,
  status: 'live',
  position: position(),
  ...over,
});

describe('status labels', () => {
  it('uses the exact wording the product promises', () => {
    expect(STATUS_LABEL).toEqual({
      live: 'LIVE GPS',
      delayed: 'DELAYED',
      stale: 'STALE',
      historical: 'HISTORICAL',
      simulated: 'SIMULATED',
      unavailable: 'LOCATION UNAVAILABLE',
    });
  });

  it('formats ages', () => {
    expect(formatAge(5)).toBe('5 s ago');
    expect(formatAge(125)).toBe('2 min ago');
    expect(formatAge(7300)).toBe('2 h ago');
    expect(formatAge(200_000)).toBe('2 d ago');
  });
});

describe('vehicle markers', () => {
  it('draws a marker only for a vehicle that has a position', () => {
    const markers = vehicleMarkers([row(), row({ vehicle_id: '2', registration_number: 'TS09-0002', status: 'unavailable', position: null })]);
    expect(markers.map((m) => m.title)).toEqual(['TS09-1234']);
  });

  it('keeps real and simulated markers apart: separate ids, layers, tone, label', () => {
    const [real, sim] = vehicleMarkers([row(), row({ simulated: true, status: 'simulated', position: position({ source: 'simulator' }) })]);
    expect(real).toMatchObject({ id: 'vehicle:1:real', layer: 'vehicles', tone: 'success', statusLabel: 'LIVE GPS', glyph: 'V' });
    expect(sim).toMatchObject({ id: 'vehicle:1:sim', layer: 'vehicles-simulated', tone: 'simulated', statusLabel: 'SIMULATED', glyph: 'S' });
    expect(sim!.title).toBe('TS09-1234 (simulated)');
    expect(sim!.details?.join(' ')).toContain('Simulator (demonstration data)');
  });

  it('maps freshness to marker tone', () => {
    const tones = (['live', 'delayed', 'stale', 'historical'] as const).map((status) => vehicleMarkers([row({ status })])[0]!.tone);
    expect(tones).toEqual(['success', 'warning', 'danger', 'neutral']);
  });

  it('skips a position that is not a valid coordinate instead of drawing it at 0,0', () => {
    expect(vehicleMarkers([row({ position: position({ latitude: 0, longitude: 0 }) })])).toEqual([]);
  });

  it('states time, source and measurements in the details, and only measurements that exist', () => {
    const lines = positionDetails(row());
    expect(lines[0]).toMatch(/^Recorded .*\(5 s ago\)$/);
    expect(lines).toContain('Source: GPS device');
    expect(lines).toContain('Accuracy about 8 m');
    expect(lines).toContain('Speed 32 km/h');
    expect(positionDetails(row({ position: position({ accuracy_m: null, speed_kph: null, heading_deg: null }) }))).toHaveLength(2);
    expect(positionDetails(row({ position: null }))[0]).toMatch(/never been reported|No position/);
  });
});

describe('polling backoff', () => {
  it('polls at the base interval, doubles on consecutive failures and is capped', () => {
    expect(pollingInterval(0)).toBe(POLL_MS);
    expect(pollingInterval(1)).toBe(POLL_MS * 2);
    expect(pollingInterval(2)).toBe(POLL_MS * 4);
    expect(pollingInterval(3)).toBe(MAX_POLL_MS);
    expect(pollingInterval(50)).toBe(MAX_POLL_MS);
  });
});
