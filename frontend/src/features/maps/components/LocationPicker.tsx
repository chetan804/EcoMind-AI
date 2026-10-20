import { useId, useMemo, useState } from 'react';
import { LocateFixed } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { isValidPoint } from '../lib/geo';
import type { GeoPoint, MapMarker } from '../types';
import { MapPanel } from './MapPanel';

/** Parse a coordinate text box; '' and anything non-numeric give NaN so validation fails closed. */
const parse = (text: string) => (text.trim() === '' ? Number.NaN : Number(text));

export interface LocationPickerProps {
  value: GeoPoint | null;
  onChange: (point: GeoPoint | null) => void;
  /** Accessible label, e.g. "Waste location". */
  label: string;
  /** Where the map opens when nothing is picked yet is decided by the map itself; this is only a hint text. */
  hint?: string;
  /** Called when typed text stops/starts being a valid coordinate pair, so a form can block submit instead of silently dropping the location. */
  onInvalidChange?: (invalid: boolean) => void;
}

/**
 * Pick a coordinate by clicking the map, typing it, or (only when the user presses the button and
 * the browser grants permission) using the device location. The typed fields always work, so the
 * picker is usable without Google Maps, with a keyboard, and with a screen reader.
 */
export function LocationPicker({ value, onChange, label, hint, onInvalidChange }: LocationPickerProps) {
  const id = useId();
  const [latText, setLatText] = useState(value ? String(value.lat) : '');
  const [lngText, setLngText] = useState(value ? String(value.lng) : '');
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apply = (lat: string, lng: string) => {
    setLatText(lat);
    setLngText(lng);
    const point = { lat: parse(lat), lng: parse(lng) };
    const ok = isValidPoint(point.lat, point.lng);
    onChange(ok ? point : null);
    onInvalidChange?.(!ok && (lat.trim() !== '' || lng.trim() !== ''));
  };
  const pick = (point: GeoPoint) => {
    setError(null);
    apply(point.lat.toFixed(6), point.lng.toFixed(6));
  };
  const locate = () => {
    if (!('geolocation' in navigator)) {
      setError('This browser cannot provide your location. Click the map or type the coordinates.');
      return;
    }
    setLocating(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        pick({ lat: position.coords.latitude, lng: position.coords.longitude });
      },
      (failure) => {
        setLocating(false);
        setError(
          failure.code === failure.PERMISSION_DENIED
            ? 'Location permission was denied. Click the map or type the coordinates instead.'
            : 'Your location could not be determined. Click the map or type the coordinates instead.',
        );
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  };
  const markers = useMemo<MapMarker[]>(
    () => (value ? [{ id: 'picked', position: value, title: `${label} (selected)`, kind: 'picked', tone: 'info', glyph: '●' }] : []),
    [value, label],
  );
  const invalid = (latText !== '' || lngText !== '') && value === null;

  return (
    <div className="location-picker">
      <MapPanel label={label} markers={markers} onMapClick={pick} height={280} />
      <p className="map-panel__note" id={`${id}-hint`}>
        {hint ?? 'Click the map, type the coordinates, or use your current location. Only the coordinates are stored.'}
      </p>
      <div className="location-picker__inputs">
        <Field label="Latitude" error={invalid ? 'Latitude must be between -90 and 90' : undefined}>
          {(c) => <Input {...c} inputMode="decimal" value={latText} onChange={(e) => apply(e.target.value, lngText)} />}
        </Field>
        <Field label="Longitude" error={invalid ? 'Longitude must be between -180 and 180' : undefined}>
          {(c) => <Input {...c} inputMode="decimal" value={lngText} onChange={(e) => apply(latText, e.target.value)} />}
        </Field>
        <Button type="button" variant="secondary" loading={locating} onClick={locate}>
          <LocateFixed size={16} aria-hidden="true" /> Use my current location
        </Button>
      </div>
      {error && <Alert tone="warning">{error}</Alert>}
    </div>
  );
}
