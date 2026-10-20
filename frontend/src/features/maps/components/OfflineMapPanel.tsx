import { useEffect, useMemo, useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { ensureOfflineMaps, retryOfflineMaps, useOfflineMapsState } from '../lib/offline-loader';
import { MapDetail, MapLegend } from './MapChrome';
import { MapFallback, MarkerList } from './MapFallback';
import { MapLibreSurface } from './MapLibreSurface';
import type { MapPanelProps } from './map-panel-props';

/**
 * The default provider: a built-in map (MapLibre over self-hosted OpenStreetMap tiles). It needs no
 * key and calls no third party. Without WebGL it shows the labelled list; without an installed tile
 * file it still draws markers and routes and says the base map is missing.
 */
export function OfflineMapPanel({ label, markers, paths = [], legend = [], height = 420, onMapClick, emptyMessage, footer, detailExtra }: MapPanelProps) {
  const maps = useOfflineMapsState();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    ensureOfflineMaps();
  }, []);
  const selected = markers.find((m) => m.id === selectedId) ?? null;
  const fitKey = useMemo(
    () => [...markers.map((m) => m.id), ...paths.map((p) => `${p.id}:${p.points.length}`)].sort().join('|'),
    [markers, paths],
  );

  if (maps.status === 'failed') {
    return <MapFallback reason={maps.reason} label={label} markers={markers} paths={paths} legend={legend} footer={footer} onRetry={retryOfflineMaps} />;
  }
  const empty = markers.length === 0 && paths.every((p) => p.points.length < 2) && !onMapClick;
  return (
    <div className="map-panel">
      <div className="map-panel__stage">
        {maps.status !== 'ready' ? (
          <div className="map-panel__placeholder" style={{ height }} role="status">
            Loading map…
          </div>
        ) : empty ? (
          <div className="map-panel__placeholder" style={{ height: Math.min(height, 160) }}>
            {emptyMessage ?? 'Nothing to show on the map yet.'}
          </div>
        ) : (
          <MapLibreSurface
            lib={maps.lib}
            style={maps.style}
            label={label}
            markers={markers}
            paths={paths}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onMapClick={onMapClick}
            height={height}
            fitKey={fitKey}
          />
        )}
      </div>
      {maps.status === 'ready' && maps.basemap === 'missing' && !empty && (
        <Alert tone="info" title="Base map not installed">
          No map tile file is installed on this server, so locations and routes are drawn on a plain background without streets. An administrator can add a regional tile file (docs/maps/OFFLINE_MAPS.md).
        </Alert>
      )}
      <MapLegend label={label} legend={legend} />
      <MapDetail selected={selected} extra={detailExtra} />
      {footer}
      {maps.status === 'ready' && !empty && (
        <details className="map-panel__list">
          <summary>Show these locations as a list</summary>
          <MarkerList markers={markers} paths={paths} caption={`${label}: locations`} />
        </details>
      )}
    </div>
  );
}
