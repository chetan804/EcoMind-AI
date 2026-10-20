import type { GeoPoint } from '../types';

const EARTH_RADIUS_M = 6_371_008.8;

export function isValidPoint(lat: number | null | undefined, lng: number | null | undefined): boolean {
  return (
    typeof lat === 'number' &&
    typeof lng === 'number' &&
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180 &&
    !(lat === 0 && lng === 0)
  );
}

/** A point, or null when either coordinate is missing/invalid (never a fabricated 0,0). */
export function toPoint(lat: number | null | undefined, lng: number | null | undefined): GeoPoint | null {
  return isValidPoint(lat, lng) ? { lat: lat as number, lng: lng as number } : null;
}

export function haversineM(a: GeoPoint, b: GeoPoint): number {
  const p1 = (a.lat * Math.PI) / 180;
  const p2 = (b.lat * Math.PI) / 180;
  const dPhi = p2 - p1;
  const dLambda = ((b.lng - a.lng) * Math.PI) / 180;
  const h = Math.sin(dPhi / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dLambda / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function pathLengthM(points: GeoPoint[]): number {
  let total = 0;
  for (let i = 1; i < points.length; i += 1) total += haversineM(points[i - 1]!, points[i]!);
  return total;
}

/**
 * Deterministic points along a polyline, one every `stepM` metres (plus the final vertex).
 * Used only by the simulator: the same path and step always give the same points. It follows
 * whatever geometry it is given, so it is a road path only if the caller passed provider geometry.
 */
export function pointsAlong(path: GeoPoint[], stepM: number): GeoPoint[] {
  if (path.length === 0) return [];
  if (stepM <= 0) throw new RangeError('stepM must be positive');
  const out: GeoPoint[] = [path[0]!];
  let carried = 0; // distance already covered since the last emitted point
  for (let i = 1; i < path.length; i += 1) {
    const from = path[i - 1]!;
    const to = path[i]!;
    const length = haversineM(from, to);
    if (length === 0) continue;
    let travelled = stepM - carried;
    while (travelled <= length) {
      const t = travelled / length;
      out.push({ lat: from.lat + (to.lat - from.lat) * t, lng: from.lng + (to.lng - from.lng) * t });
      travelled += stepM;
    }
    carried = length - (travelled - stepM);
  }
  const last = path[path.length - 1]!;
  const tail = out[out.length - 1]!;
  if (tail.lat !== last.lat || tail.lng !== last.lng) out.push(last);
  return out;
}

/** Heading in degrees clockwise from north, [0, 360). */
export function headingDeg(from: GeoPoint, to: GeoPoint): number {
  const p1 = (from.lat * Math.PI) / 180;
  const p2 = (to.lat * Math.PI) / 180;
  const dLambda = ((to.lng - from.lng) * Math.PI) / 180;
  const y = Math.sin(dLambda) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dLambda);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

/**
 * Google Maps URL that opens turn-by-turn directions to a point in the user's own Google Maps.
 * It is a plain link (no API key, no API call). Only coordinates are sent, never names or ids.
 */
export function directionsUrl(destination: GeoPoint): string {
  const dest = `${destination.lat.toFixed(6)},${destination.lng.toFixed(6)}`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}`;
}

export function formatCoordinate(point: GeoPoint): string {
  return `${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}`;
}
