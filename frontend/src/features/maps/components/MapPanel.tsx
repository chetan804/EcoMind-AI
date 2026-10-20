import { config } from '@/app/config';
import { GoogleMapPanel } from './GoogleMapPanel';
import { OfflineMapPanel } from './OfflineMapPanel';
import type { MapPanelProps } from './map-panel-props';
import './map.css';

export type { MapPanelProps } from './map-panel-props';

/**
 * The one map component of the product. The engine is a build-time choice (`VITE_MAP_PROVIDER`):
 * the built-in offline map (default, no key) or Google Maps (opt-in, needs a browser key). Both
 * render the same markers, paths, legend and detail panel, and both fall back to a labelled list
 * instead of ever showing a blank map.
 */
export function MapPanel(props: MapPanelProps) {
  return config.mapProvider === 'google' ? <GoogleMapPanel {...props} /> : <OfflineMapPanel {...props} />;
}
