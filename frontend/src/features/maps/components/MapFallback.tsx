import type { ReactNode } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { formatCoordinate, pathLengthM } from '../lib/geo';
import type { LegendEntry, MapMarker, MapPath, MapsFailureReason } from '../types';

const MESSAGES: Record<MapsFailureReason, { tone: 'info' | 'warning' | 'danger'; title: string; body: string }> = {
  missing_key: {
    tone: 'info',
    title: 'Map not available: Google Maps is not configured',
    body: 'No browser key (VITE_GOOGLE_MAPS_API_KEY) was set when this app was built. The same locations are listed below.',
  },
  network: {
    tone: 'warning',
    title: 'Map could not be loaded',
    body: 'Google Maps did not load (offline, blocked by a firewall or extension, or the service is unreachable). The same locations are listed below.',
  },
  timeout: {
    tone: 'warning',
    title: 'Map took too long to load',
    body: 'Google Maps did not answer in time. The same locations are listed below.',
  },
  auth: {
    tone: 'danger',
    title: 'Google rejected the map key',
    body: 'The key is invalid, restricted to other sites, over its quota, or the Maps JavaScript API is not enabled for it. An administrator must fix it in Google Cloud. The same locations are listed below.',
  },
  unsupported: {
    tone: 'warning',
    title: 'Map could not start',
    body: 'Google Maps loaded without the libraries this page needs. The same locations are listed below.',
  },
  no_webgl: {
    tone: 'info',
    title: 'Map not available: this browser cannot draw the map',
    body: 'The built-in map needs WebGL, which is turned off or unsupported here (hardware acceleration disabled, a very old browser or a remote session). The same locations are listed below.',
  },
  load_error: {
    tone: 'warning',
    title: 'Map could not be loaded',
    body: 'The built-in map code could not be loaded (the connection dropped or the file is missing from this deployment). The same locations are listed below.',
  },
};

const MAX_ROWS = 100;

/** Accessible list of everything a map would show. Also used under a working map as the text alternative. */
export function MarkerList({ markers, paths, caption }: { markers: MapMarker[]; paths: MapPath[]; caption: string }) {
  const shown = markers.slice(0, MAX_ROWS);
  return (
    <div className="stack stack--tight">
      {markers.length > 0 ? (
        <div className="map-panel__scroll">
          <table className="table">
            <caption className="visually-hidden">{caption}</caption>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Status</th>
                <th scope="col">Coordinates</th>
                <th scope="col">Details</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((m) => (
                <tr key={m.id}>
                  <th scope="row">{m.title}</th>
                  <td>{m.statusLabel ?? '—'}</td>
                  <td>{formatCoordinate(m.position)}</td>
                  <td>{m.details?.join(' · ') ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="map-panel__note">Nothing to show on the map yet.</p>
      )}
      {markers.length > MAX_ROWS && <p className="map-panel__note">…and {markers.length - MAX_ROWS} more.</p>}
      {paths.map((p) => (
        <p key={p.id} className="map-panel__note">
          {p.label}: {p.points.length} points, about {(pathLengthM(p.points) / 1000).toFixed(1)} km measured along the line.
        </p>
      ))}
    </div>
  );
}

export interface MapFallbackProps {
  reason: MapsFailureReason;
  label: string;
  markers: MapMarker[];
  paths: MapPath[];
  legend?: LegendEntry[];
  footer?: ReactNode;
  /** Retry action for transient failures (network, timeout, load error). */
  onRetry?: () => void;
}

export function MapFallback({ reason, label, markers, paths, legend = [], footer, onRetry }: MapFallbackProps) {
  const message = MESSAGES[reason];
  const retryable = (reason === 'network' || reason === 'timeout' || reason === 'load_error') && onRetry !== undefined;
  return (
    <div className="map-panel" role="region" aria-label={`${label} (list view)`}>
      <Alert tone={message.tone} title={message.title}>
        {message.body}
        {retryable && (
          <div>
            <Button variant="secondary" onClick={onRetry}>
              Try loading the map again
            </Button>
          </div>
        )}
      </Alert>
      <MarkerList markers={markers} paths={paths} caption={`${label}: locations`} />
      {legend.length > 0 && (
        <ul className="map-panel__legend" aria-label={`${label}: legend`}>
          {legend.map((entry) => (
            <li key={entry.key}>{entry.label}</li>
          ))}
        </ul>
      )}
      {footer}
    </div>
  );
}
