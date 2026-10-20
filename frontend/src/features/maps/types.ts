/** Shared location and route types used by every map in the product. */

export interface GeoPoint {
  lat: number;
  lng: number;
}

export type MarkerKind = 'vehicle' | 'facility' | 'depot' | 'task' | 'stop' | 'report' | 'incident' | 'picked';

/** Visual meaning of a marker. Colour is never the only signal: markers also carry a glyph/label. */
export type MarkerTone = 'success' | 'info' | 'warning' | 'danger' | 'neutral' | 'simulated';

export interface MapMarker {
  id: string;
  position: GeoPoint;
  /** Accessible name and list label. Must not contain private data (no reporter identity, no home address). */
  title: string;
  kind: MarkerKind;
  tone: MarkerTone;
  /** One or two characters drawn on the pin (stop number, "V"). */
  glyph?: string;
  /** Human-readable status shown in the detail panel and list, e.g. "LIVE GPS". */
  statusLabel?: string;
  /** Lines for the detail panel: timestamp, source, accuracy... */
  details?: string[];
  /** Legend/layer key; used by layer toggles in the caller. */
  layer?: string;
  /** Group nearby markers of the same kind into a cluster when zoomed out. */
  clusterable?: boolean;
}

export type PathKind =
  /** Geometry returned by the routing provider (roads). */
  | 'planned_road'
  /** Straight segments between planned stops; NOT roads. Always labelled as a fallback. */
  | 'planned_straight'
  /** Positions recorded from a real source. */
  | 'recorded'
  /** Simulator positions. */
  | 'simulated';

export interface MapPath {
  id: string;
  kind: PathKind;
  points: GeoPoint[];
  /** Legend and list text, e.g. "Planned route (straight lines, not roads)". */
  label: string;
}

export interface LegendEntry {
  key: string;
  label: string;
  tone?: MarkerTone;
  /** Line sample for paths. */
  pathKind?: PathKind;
}

/** Why a map could not be drawn. The first five belong to the optional Google provider, the last two to the offline provider. */
export type MapsFailureReason = 'missing_key' | 'network' | 'timeout' | 'auth' | 'unsupported' | 'no_webgl' | 'load_error';
