/** Public interface of the maps feature: the shared map component, location types and helpers. */
export { MapPanel } from './components/MapPanel';
export type { MapPanelProps } from './components/MapPanel';
export { LocationPicker } from './components/LocationPicker';
export { decodePolyline } from './lib/polyline';
export { directionsUrl, formatCoordinate, haversineM, headingDeg, isValidPoint, pathLengthM, pointsAlong, toPoint } from './lib/geo';
export type { GeoPoint, LegendEntry, MapMarker, MapPath, MapsFailureReason, MarkerKind, MarkerTone, PathKind } from './types';
export { facilityMarkers } from './facility-markers';
export type { MappableFacility } from './facility-markers';
