import type { ReactNode } from 'react';
import type { GeoPoint, LegendEntry, MapMarker, MapPath } from '../types';

export interface MapPanelProps {
  /** Accessible name of the map region, e.g. "Fleet positions". */
  label: string;
  markers: MapMarker[];
  paths?: MapPath[];
  legend?: LegendEntry[];
  height?: number;
  /** Called with the clicked point (location picking). */
  onMapClick?: (point: GeoPoint) => void;
  /** Shown instead of an empty map. */
  emptyMessage?: string;
  /** Extra content under the map (notes, counts). */
  footer?: ReactNode;
  /** Shown in the detail panel for the selected marker, after its own lines. */
  detailExtra?: (marker: MapMarker) => ReactNode;
}
