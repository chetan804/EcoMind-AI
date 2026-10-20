import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { ensureGoogleMaps, useGoogleMapsState } from '../lib/google-loader';
import { formatCoordinate } from '../lib/geo';
import type { GeoPoint, LegendEntry, MapMarker, MapPath, PathKind } from '../types';
import { GoogleMapSurface } from './GoogleMapSurface';
import { MapFallback, MarkerList } from './MapFallback';
import './map.css';

const LINE_COLOR: Record<PathKind, string> = {
  planned_road: '#38a8f5',
  planned_straight: '#f5b83d',
  recorded: '#34d399',
  simulated: '#b794f6',
};

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

/**
 * The one map component of the product: a Google map with markers, clusters, paths, a legend, a
 * detail panel and a text list. Without a key, or when Google cannot load, it renders the labelled
 * list fallback instead; it never renders a blank map.
 */
export function MapPanel({ label, markers, paths = [], legend = [], height = 420, onMapClick, emptyMessage, footer, detailExtra }: MapPanelProps) {
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
    return <MapFallback reason={maps.reason} label={label} markers={markers} paths={paths} legend={legend} footer={footer} />;
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
      {legend.length > 0 && (
        <ul className="map-panel__legend" aria-label={`${label}: legend`}>
          {legend.map((entry) => (
            <li key={entry.key}>
              {entry.pathKind ? (
                <span
                  className={`map-panel__line${entry.pathKind === 'planned_straight' ? ' map-panel__line--dashed' : ''}${entry.pathKind === 'simulated' ? ' map-panel__line--dotted' : ''}`}
                  style={{ ['--map-line' as string]: LINE_COLOR[entry.pathKind] }}
                  aria-hidden="true"
                />
              ) : (
                <span className={`map-panel__swatch map-pin--${entry.tone ?? 'info'}`} style={{ background: 'var(--pin)' }} aria-hidden="true" />
              )}
              {entry.label}
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <div className="map-panel__detail" role="group" aria-label={`Selected: ${selected.title}`}>
          <h3>{selected.title}</h3>
          {selected.statusLabel && <strong>{selected.statusLabel}</strong>}
          <ul>
            <li>{formatCoordinate(selected.position)}</li>
            {selected.details?.map((line) => <li key={line}>{line}</li>)}
          </ul>
          {detailExtra?.(selected)}
        </div>
      )}
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
