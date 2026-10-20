import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LocationPicker, MapPanel, type MapMarker } from '@/features/maps';
import type { MapsState } from '@/features/maps/lib/google-loader';

// ---- Fake Google Maps + marker clusterer (no network, no key, no paid calls) ----
const fake = vi.hoisted(() => {
  const maps: FakeMap[] = [];
  const markers: FakeMarker[] = [];
  const lines: FakeLine[] = [];
  const clusterers: FakeClusterer[] = [];
  type Handler = (event?: unknown) => void;
  class Listening {
    handlers = new Map<string, Handler[]>();
    addListener(name: string, fn: Handler) {
      this.handlers.set(name, [...(this.handlers.get(name) ?? []), fn]);
      return { remove: () => this.handlers.set(name, (this.handlers.get(name) ?? []).filter((h) => h !== fn)) };
    }
    emit(name: string, event?: unknown) {
      for (const h of this.handlers.get(name) ?? []) h(event);
    }
  }
  class FakeMap extends Listening {
    center: unknown = null;
    zoom = 0;
    bounds: unknown[] = [];
    constructor(public el: HTMLElement, public options: Record<string, unknown>) {
      super();
      maps.push(this);
    }
    setCenter(c: unknown) {
      this.center = c;
    }
    setZoom(z: number) {
      this.zoom = z;
    }
    fitBounds(b: unknown) {
      this.bounds.push(b);
    }
  }
  class FakeMarker extends Listening {
    map: unknown = null;
    position: unknown;
    title: string;
    content: HTMLElement;
    constructor(opts: { position: unknown; title: string; content: HTMLElement }) {
      super();
      this.position = opts.position;
      this.title = opts.title;
      this.content = opts.content;
      markers.push(this);
    }
  }
  class FakeLine {
    map: unknown;
    constructor(public options: { map: unknown; path: unknown[] }) {
      this.map = options.map;
      lines.push(this);
    }
    setMap(m: unknown) {
      this.map = m;
    }
  }
  class FakeClusterer {
    added = new Set<FakeMarker>();
    constructor(public options: unknown) {
      clusterers.push(this);
    }
    addMarker(m: FakeMarker) {
      this.added.add(m);
    }
    removeMarker(m: FakeMarker) {
      this.added.delete(m);
    }
    clearMarkers() {
      this.added.clear();
    }
  }
  class FakeBounds {
    points: unknown[] = [];
    extend(p: unknown) {
      this.points.push(p);
    }
  }
  const api = { Map: FakeMap, Polyline: FakeLine, LatLngBounds: FakeBounds, marker: { AdvancedMarkerElement: FakeMarker }, importLibrary: async () => ({}) };
  return { maps, markers, lines, clusterers, api, FakeClusterer };
});

// This file tests the opt-in Google provider; the default (offline) provider is covered in offline-map.test.tsx.
vi.mock('@/app/config', async (importOriginal) => {
  const actual = await importOriginal<{ config: Record<string, unknown> }>();
  return { ...actual, config: { ...actual.config, mapProvider: 'google' as const } };
});
vi.mock('@googlemaps/markerclusterer', () => ({ MarkerClusterer: fake.FakeClusterer }));

let mapsState: MapsState = { status: 'failed', reason: 'missing_key' };
const retry = vi.fn();
vi.mock('@/features/maps/lib/google-loader', () => ({
  useGoogleMapsState: () => mapsState,
  ensureGoogleMaps: vi.fn(),
  retryGoogleMaps: () => retry(),
}));

const vehicle = (over: Partial<MapMarker> = {}): MapMarker => ({
  id: 'vehicle:1:real',
  position: { lat: 17.4, lng: 78.5 },
  title: 'TS09-1234',
  kind: 'vehicle',
  tone: 'success',
  glyph: 'V',
  statusLabel: 'LIVE GPS',
  details: ['Recorded 21 Oct 2026, 08:00 (5 s ago)', 'Source: GPS device'],
  clusterable: true,
  ...over,
});
const depot = (): MapMarker => ({ id: 'facility:1', position: { lat: 17.41, lng: 78.51 }, title: 'North Depot', kind: 'depot', tone: 'info', glyph: 'D' });

const ready = (): MapsState => ({ status: 'ready', maps: fake.api as unknown as typeof google.maps });

beforeEach(() => {
  fake.maps.length = 0;
  fake.markers.length = 0;
  fake.lines.length = 0;
  fake.clusterers.length = 0;
  retry.mockClear();
});
afterEach(() => {
  mapsState = { status: 'failed', reason: 'missing_key' };
});

describe('MapPanel without a usable map', () => {
  it('never renders a blank map: a missing key shows a labelled list of the same locations', () => {
    render(<MapPanel label="Fleet positions" markers={[vehicle(), depot()]} />);
    expect(screen.getByText('Map not available: Google Maps is not configured')).toBeInTheDocument();
    const table = screen.getByRole('table', { name: 'Fleet positions: locations' });
    expect(within(table).getByRole('rowheader', { name: 'TS09-1234' })).toBeInTheDocument();
    expect(within(table).getByText('LIVE GPS')).toBeInTheDocument();
    expect(within(table).getByText('17.40000, 78.50000')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /try loading/i })).not.toBeInTheDocument();
    expect(fake.maps).toHaveLength(0);
  });

  it.each([
    ['network', 'Map could not be loaded', true],
    ['timeout', 'Map took too long to load', true],
    ['auth', 'Google rejected the map key', false],
    ['unsupported', 'Map could not start', false],
  ] as const)('explains a %s failure', async (reason, title, retryable) => {
    mapsState = { status: 'failed', reason };
    render(<MapPanel label="Fleet positions" markers={[vehicle()]} />);
    expect(screen.getByText(title)).toBeInTheDocument();
    const button = screen.queryByRole('button', { name: 'Try loading the map again' });
    expect(Boolean(button)).toBe(retryable);
    if (button) {
      await userEvent.click(button);
      expect(retry).toHaveBeenCalledTimes(1);
    }
  });

  it('describes paths in the list view with their honest labels', () => {
    render(
      <MapPanel
        label="Route plan"
        markers={[]}
        paths={[{ id: 'p', kind: 'planned_straight', label: 'Straight lines between stops. Not roads', points: [{ lat: 17, lng: 78 }, { lat: 17.1, lng: 78 }] }]}
      />,
    );
    expect(screen.getByText(/Straight lines between stops\. Not roads: 2 points/)).toBeInTheDocument();
  });
});

describe('MapPanel with a ready map', () => {
  it('shows a loading state, not a blank box, while Google loads', () => {
    mapsState = { status: 'loading' };
    render(<MapPanel label="Fleet positions" markers={[vehicle()]} />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading map');
  });

  it('shows the empty message when there is nothing to draw', () => {
    mapsState = ready();
    render(<MapPanel label="Fleet positions" markers={[]} emptyMessage="No vehicle has reported a position yet." />);
    expect(screen.getByText('No vehicle has reported a position yet.')).toBeInTheDocument();
    expect(fake.maps).toHaveLength(0);
  });

  it('draws one marker per item, clusters only clusterable ones, and fits the view', () => {
    mapsState = ready();
    render(<MapPanel label="Fleet positions" markers={[vehicle(), depot()]} />);
    expect(fake.maps).toHaveLength(1);
    expect(fake.markers.map((m) => m.title).sort()).toEqual(['North Depot', 'TS09-1234']);
    const clusterer = fake.clusterers[0]!;
    expect([...clusterer.added].map((m) => m.title)).toEqual(['TS09-1234']);
    expect(fake.markers.find((m) => m.title === 'North Depot')!.map).toBe(fake.maps[0]);
    expect(fake.maps[0]!.bounds).toHaveLength(1);
    expect(screen.getByRole('region', { name: 'Fleet positions (interactive map)' })).toBeInTheDocument();
    expect(screen.getByText('Show these locations as a list')).toBeInTheDocument();
  });

  it('updates a moved marker without touching unchanged ones, and does not re-fit the view', () => {
    mapsState = ready();
    const { rerender } = render(<MapPanel label="Fleet positions" markers={[vehicle(), depot()]} />);
    const depotMarker = fake.markers.find((m) => m.title === 'North Depot')!;
    const firstVehicle = fake.markers.find((m) => m.title === 'TS09-1234')!;
    rerender(<MapPanel label="Fleet positions" markers={[vehicle({ position: { lat: 17.401, lng: 78.501 } }), depot()]} />);
    expect(fake.markers.filter((m) => m.title === 'North Depot')).toEqual([depotMarker]);
    const vehicles = fake.markers.filter((m) => m.title === 'TS09-1234');
    expect(vehicles).toHaveLength(2);
    expect(firstVehicle.map).toBeNull();
    expect(fake.clusterers[0]!.added.has(firstVehicle)).toBe(false);
    expect(fake.clusterers[0]!.added.has(vehicles[1]!)).toBe(true);
    expect(vehicles[1]!.position).toEqual({ lat: 17.401, lng: 78.501 });
    expect(fake.maps[0]!.bounds).toHaveLength(1);
  });

  it('removes markers that disappear and relabels status changes', () => {
    mapsState = ready();
    const { rerender } = render(<MapPanel label="Fleet positions" markers={[vehicle(), depot()]} />);
    const depotMarker = fake.markers.find((m) => m.title === 'North Depot')!;
    rerender(<MapPanel label="Fleet positions" markers={[vehicle({ tone: 'danger', statusLabel: 'STALE' })]} />);
    expect(depotMarker.map).toBeNull();
    const latest = fake.markers.filter((m) => m.title === 'TS09-1234').at(-1)!;
    expect(latest.content.className).toContain('map-pin--danger');
  });

  it('opens a detail panel with status, timestamp and source when a marker is selected', async () => {
    mapsState = ready();
    render(<MapPanel label="Fleet positions" markers={[vehicle({ tone: 'simulated', statusLabel: 'SIMULATED', details: ['Source: Simulator (demonstration data)'] })]} />);
    act(() => fake.markers[0]!.emit('click'));
    const detail = await screen.findByRole('group', { name: 'Selected: TS09-1234' });
    expect(within(detail).getByText('SIMULATED')).toBeInTheDocument();
    expect(within(detail).getByText('Source: Simulator (demonstration data)')).toBeInTheDocument();
    expect(within(detail).getByText('17.40000, 78.50000')).toBeInTheDocument();
  });

  it('draws only paths with two or more points and reports clicks for location picking', () => {
    mapsState = ready();
    const onMapClick = vi.fn();
    render(
      <MapPanel
        label="Pick"
        markers={[]}
        onMapClick={onMapClick}
        paths={[
          { id: 'a', kind: 'planned_road', label: 'road', points: [{ lat: 17, lng: 78 }, { lat: 17.1, lng: 78.1 }] },
          { id: 'b', kind: 'recorded', label: 'one point', points: [{ lat: 17, lng: 78 }] },
        ]}
      />,
    );
    expect(fake.lines).toHaveLength(1);
    act(() => fake.maps[0]!.emit('click', { latLng: { lat: () => 17.5, lng: () => 78.25 } }));
    expect(onMapClick).toHaveBeenCalledWith({ lat: 17.5, lng: 78.25 });
  });
});

describe('LocationPicker', () => {
  const geolocation = { getCurrentPosition: vi.fn() };
  beforeEach(() => {
    geolocation.getCurrentPosition.mockReset();
    Object.defineProperty(navigator, 'geolocation', { value: geolocation, configurable: true });
  });

  it('accepts typed coordinates and rejects invalid ones, including 0,0', async () => {
    const onChange = vi.fn();
    const onInvalid = vi.fn();
    render(<LocationPicker label="Waste location" value={null} onChange={onChange} onInvalidChange={onInvalid} />);
    await userEvent.type(screen.getByLabelText('Latitude'), '17.4');
    expect(onChange).toHaveBeenLastCalledWith(null);
    expect(onInvalid).toHaveBeenLastCalledWith(true);
    await userEvent.type(screen.getByLabelText('Longitude'), '78.5');
    expect(onChange).toHaveBeenLastCalledWith({ lat: 17.4, lng: 78.5 });
    expect(onInvalid).toHaveBeenLastCalledWith(false);
    await userEvent.clear(screen.getByLabelText('Latitude'));
    await userEvent.type(screen.getByLabelText('Latitude'), '95');
    expect(screen.getByText('Latitude must be between -90 and 90')).toBeInTheDocument();
    expect(onChange).toHaveBeenLastCalledWith(null);
    await userEvent.clear(screen.getByLabelText('Latitude'));
    await userEvent.type(screen.getByLabelText('Latitude'), '0');
    await userEvent.clear(screen.getByLabelText('Longitude'));
    await userEvent.type(screen.getByLabelText('Longitude'), '0');
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it('does not ask for the device location until the button is pressed', async () => {
    const onChange = vi.fn();
    render(<LocationPicker label="Waste location" value={null} onChange={onChange} />);
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
    geolocation.getCurrentPosition.mockImplementation((ok: (p: unknown) => void) => ok({ coords: { latitude: 17.3851, longitude: 78.4867 } }));
    await userEvent.click(screen.getByRole('button', { name: /Use my current location/ }));
    expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith({ lat: 17.3851, lng: 78.4867 });
    expect(screen.getByLabelText('Latitude')).toHaveValue('17.385100');
  });

  it('explains a denied permission and keeps manual entry available', async () => {
    geolocation.getCurrentPosition.mockImplementation((_ok: unknown, fail: (e: unknown) => void) => fail({ code: 1, PERMISSION_DENIED: 1 }));
    render(<LocationPicker label="Waste location" value={null} onChange={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /Use my current location/ }));
    expect(await screen.findByText(/Location permission was denied/)).toBeInTheDocument();
    expect(screen.getByLabelText('Latitude')).toBeEnabled();
  });

  it('picks a point from a map click when the map is available', () => {
    mapsState = ready();
    const onChange = vi.fn();
    render(<LocationPicker label="Waste location" value={null} onChange={onChange} />);
    act(() => fake.maps[0]!.emit('click', { latLng: { lat: () => 17.5, lng: () => 78.25 } }));
    expect(onChange).toHaveBeenLastCalledWith({ lat: 17.5, lng: 78.25 });
  });
});
