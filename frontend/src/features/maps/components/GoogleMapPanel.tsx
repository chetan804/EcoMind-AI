import { useEffect, useMemo, useState } from 'react';
import { ensureGoogleMaps, retryGoogleMaps, useGoogleMapsState } from '../lib/google-loader';
import { GoogleMapSurface } from './GoogleMapSurface';
import { MapDetail, MapLegend } from './MapChrome';
import { MapFallback, MarkerList } from './MapFallback';
import type { MapPanelProps } from './map-panel-props';

/** The optional Google provider (needs VITE_GOOGLE_MAPS_API_KEY). Falls back to the labelled list. */
export function GoogleMapPanel({ label, markers, paths = [], legend = [], height = 420, onMapClick, emptyMessage, footer, detailExtra }: MapPanelProps) {
  const maps = useGoogleMapsState();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    ensureGoogleMaps();
  }, []);
  const selected = markers.find((m) => m.id === selectedId) ?? null;
  const fitKey = useMemo(
    () => [...markers.map((m) => m.id), ...paths.map((p) => `${p.id}:${p.points.length}`)].sort().join('|'),
    [markers, paths],
  );

  if (maps.status === 'failed') {
    return <MapFallback reason={maps.reason} label={label} markers={markers} paths={paths} legend={legend} footer={footer} onRetry={retryGoogleMaps} />;
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
          <GoogleMapSurface
            maps={maps.maps}
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
