import type { ReactNode } from 'react';
import { formatCoordinate } from '../lib/geo';
import type { LegendEntry, MapMarker, PathKind } from '../types';

const LINE_COLOR: Record<PathKind, string> = {
  planned_road: '#38a8f5',
  planned_straight: '#f5b83d',
  recorded: '#34d399',
  simulated: '#b794f6',
};

/** Legend under a working map (the list fallback renders its own plain-text legend). */
export function MapLegend({ label, legend }: { label: string; legend: LegendEntry[] }) {
  if (legend.length === 0) return null;
  return (
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
  );
}

/** Status, timestamp and source of the selected marker. */
export function MapDetail({ selected, extra }: { selected: MapMarker | null; extra?: (marker: MapMarker) => ReactNode }) {
  if (!selected) return null;
  return (
    <div className="map-panel__detail" role="group" aria-label={`Selected: ${selected.title}`}>
      <h3>{selected.title}</h3>
      {selected.statusLabel && <strong>{selected.statusLabel}</strong>}
      <ul>
        <li>{formatCoordinate(selected.position)}</li>
        {selected.details?.map((line) => <li key={line}>{line}</li>)}
      </ul>
      {extra?.(selected)}
    </div>
  );
}
