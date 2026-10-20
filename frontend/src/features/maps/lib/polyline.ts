import type { GeoPoint } from '../types';

/**
 * Decode a Google "encoded polyline" (precision 1e-5). Returns [] for malformed input instead of
 * throwing, so a bad provider response can never crash a screen.
 * https://developers.google.com/maps/documentation/utilities/polylinealgorithm
 */
export function decodePolyline(encoded: string): GeoPoint[] {
  const points: GeoPoint[] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;
  const readValue = (): number | null => {
    let result = 0;
    let shift = 0;
    for (;;) {
      if (index >= encoded.length) return null;
      const byte = encoded.charCodeAt(index) - 63;
      index += 1;
      if (byte < 0 || byte > 63) return null;
      result |= (byte & 0x1f) << shift;
      shift += 5;
      if (byte < 0x20) break;
      if (shift > 30) return null;
    }
    return result & 1 ? ~(result >> 1) : result >> 1;
  };
  while (index < encoded.length) {
    const dLat = readValue();
    const dLng = readValue();
    if (dLat === null || dLng === null) return [];
    lat += dLat;
    lng += dLng;
    const point = { lat: lat / 1e5, lng: lng / 1e5 };
    if (Math.abs(point.lat) > 90 || Math.abs(point.lng) > 180) return [];
    points.push(point);
  }
  return points;
}
