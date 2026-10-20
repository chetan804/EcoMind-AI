import { describe, expect, it } from 'vitest';
import { decodePolyline, directionsUrl, formatCoordinate, haversineM, headingDeg, isValidPoint, pathLengthM, pointsAlong, toPoint } from '@/features/maps';

describe('coordinate validation', () => {
  it('accepts real coordinates and rejects out-of-range, non-finite and null island', () => {
    expect(isValidPoint(17.385, 78.4867)).toBe(true);
    expect(isValidPoint(-90, 180)).toBe(true);
    expect(isValidPoint(90.0001, 0)).toBe(false);
    expect(isValidPoint(0, 180.1)).toBe(false);
    expect(isValidPoint(Number.NaN, 10)).toBe(false);
    expect(isValidPoint(Number.POSITIVE_INFINITY, 10)).toBe(false);
    expect(isValidPoint(null, 10)).toBe(false);
    expect(isValidPoint(10, undefined)).toBe(false);
    // 0,0 is the classic "no data" value; it is never treated as a place.
    expect(isValidPoint(0, 0)).toBe(false);
  });

  it('toPoint never invents a coordinate', () => {
    expect(toPoint(17.4, 78.5)).toEqual({ lat: 17.4, lng: 78.5 });
    expect(toPoint(null, 78.5)).toBeNull();
    expect(toPoint(0, 0)).toBeNull();
  });
});

describe('distance helpers', () => {
  const hyderabad = { lat: 17.385, lng: 78.4867 };
  const secunderabad = { lat: 17.4399, lng: 78.4983 };

  it('computes great-circle distance', () => {
    expect(haversineM(hyderabad, hyderabad)).toBe(0);
    // One degree of latitude is about 111.2 km.
    expect(haversineM({ lat: 10, lng: 20 }, { lat: 11, lng: 20 })).toBeCloseTo(111_195, -2);
    expect(haversineM(hyderabad, secunderabad)).toBeGreaterThan(5_000);
    expect(haversineM(hyderabad, secunderabad)).toBeLessThan(7_000);
  });

  it('sums a path and is zero for fewer than two points', () => {
    expect(pathLengthM([])).toBe(0);
    expect(pathLengthM([hyderabad])).toBe(0);
    expect(pathLengthM([hyderabad, secunderabad, hyderabad])).toBeCloseTo(2 * haversineM(hyderabad, secunderabad), 6);
  });

  it('gives compass headings', () => {
    expect(headingDeg({ lat: 10, lng: 20 }, { lat: 11, lng: 20 })).toBeCloseTo(0, 5);
    expect(headingDeg({ lat: 10, lng: 20 }, { lat: 10, lng: 21 })).toBeCloseTo(90, 0);
    expect(headingDeg({ lat: 10, lng: 20 }, { lat: 9, lng: 20 })).toBeCloseTo(180, 5);
    expect(headingDeg({ lat: 10, lng: 20 }, { lat: 10, lng: 19 })).toBeCloseTo(270, 0);
  });
});

describe('pointsAlong (simulator path stepping)', () => {
  const line = [
    { lat: 17.0, lng: 78.0 },
    { lat: 17.01, lng: 78.0 },
  ];

  it('is deterministic and keeps the start and the end', () => {
    const a = pointsAlong(line, 150);
    const b = pointsAlong(line, 150);
    expect(a).toEqual(b);
    expect(a[0]).toEqual(line[0]);
    expect(a[a.length - 1]).toEqual(line[1]);
  });

  it('spaces interior points by the step along the line', () => {
    const points = pointsAlong(line, 150);
    expect(points.length).toBeGreaterThan(5);
    for (let i = 1; i < points.length - 1; i += 1) {
      expect(haversineM(points[i - 1]!, points[i]!)).toBeCloseTo(150, 0);
    }
  });

  it('handles empty, single-point and invalid steps', () => {
    expect(pointsAlong([], 100)).toEqual([]);
    expect(pointsAlong([line[0]!], 100)).toEqual([line[0]]);
    expect(() => pointsAlong(line, 0)).toThrow(RangeError);
  });
});

describe('links and formatting', () => {
  it('builds a directions link from coordinates only', () => {
    const url = directionsUrl({ lat: 17.385, lng: 78.4867 });
    expect(url).toBe('https://www.google.com/maps/dir/?api=1&destination=17.385000%2C78.486700');
    expect(url).not.toMatch(/key=/);
  });

  it('formats coordinates to five places', () => {
    expect(formatCoordinate({ lat: 17.385044, lng: 78.486671 })).toBe('17.38504, 78.48667');
  });
});

describe('decodePolyline', () => {
  it("decodes Google's documented example", () => {
    const points = decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@');
    expect(points).toEqual([
      { lat: 38.5, lng: -120.2 },
      { lat: 40.7, lng: -120.95 },
      { lat: 43.252, lng: -126.453 },
    ]);
  });

  it('returns an empty list for empty, truncated or out-of-range input instead of throwing', () => {
    expect(decodePolyline('')).toEqual([]);
    expect(decodePolyline('_p~iF')).toEqual([]);
    expect(decodePolyline('\u0001\u0002')).toEqual([]);
    // Longitude far outside +-180 once decoded.
    expect(decodePolyline('_p~iF~~~~~~~~~~~~~~')).toEqual([]);
  });
});
