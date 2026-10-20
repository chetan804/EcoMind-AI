import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MapPanel, type MapMarker } from '@/features/maps';
import type { OfflineMapsState } from '@/features/maps/lib/offline-loader';

// ---- Fake MapLibre (no WebGL, no network, no tiles) ----
const fake = vi.hoisted(() => {
  type Handler = (event?: unknown) => void;
  const maps: FakeMap[] = [];
  const markers: FakeMarker[] = [];
  class FakeMap {
    handlers = new Map<string, Handler[]>();
    sources = new Map<string, { data: unknown; setData: (d: unknown) => void }>();
    layers: Array<{ id: string; filter: unknown; paint: Record<string, unknown> }> = [];
    zoom = 1;
    fits: unknown[] = [];
    jumps: unknown[] = [];
    removed = false;
    canvas = document.createElement('canvas');
    touchZoomRotate = { disableRotation: () => undefined };
    constructor(public options: Record<string, unknown>) {
      maps.push(this);
    }
    on(name: string, fn: Handler) {
      this.handlers.set(name, [...(this.handlers.get(name) ?? []), fn]);
    }
    emit(name: string, event?: unknown) {
      for (const h of this.handlers.get(name) ?? []) h(event);
    }
    addControl() {}
    getCanvas() {
      return this.canvas;
    }
    getBounds() {
      return { getWest: () => -180, getEast: () => 180, getSouth: () => -85, getNorth: () => 85 };
    }
    getZoom() {
      return this.zoom;
    }
    getSource(id: string) {
      return this.sources.get(id);
    }
    addSource(id: string, spec: { data: unknown }) {
      const source = { data: spec.data, setData(d: unknown) { source.data = d; } };
      this.sources.set(id, source);
    }
    addLayer(layer: { id: string; filter: unknown; paint: Record<string, unknown> }) {
      this.layers.push(layer);
    }
    jumpTo(o: unknown) {
      this.jumps.push(o);
    }
    fitBounds(b: unknown) {
      this.fits.push(b);
    }
    easeTo() {}
    remove() {
      this.removed = true;
    }
  }
  class FakeMarker {
    lngLat: [number, number] = [0, 0];
    onMap = false;
    constructor(public options: { element: HTMLElement }) {
      markers.push(this);
    }
    get element() {
      return this.options.element;
    }
    setLngLat(p: [number, number]) {
      this.lngLat = p;
      return this;
    }
    addTo() {
      this.onMap = true;
      // MapLibre puts the element in the map's DOM; tests read it from the document.
      document.getElementById('fake-maplibre-root')?.appendChild(this.options.element);
      return this;
    }
    remove() {
      this.onMap = false;
      this.options.element.remove();
    }
  }
  class FakeBounds {
    points: unknown[] = [];
    extend(p: unknown) {
      this.points.push(p);
    }
  }
  class Control {}
  const lib = { Map: FakeMap, Marker: FakeMarker, LngLatBounds: FakeBounds, NavigationControl: Control, ScaleControl: Control, AttributionControl: Control };
  return { maps, markers, lib };
});

let state: OfflineMapsState = { status: 'failed', reason: 'no_webgl' };
const retry = vi.fn();
vi.mock('@/features/maps/lib/offline-loader', () => ({
  useOfflineMapsState: () => state,
  ensureOfflineMaps: vi.fn(),
  retryOfflineMaps: () => retry(),
}));

const vehicle = (id: string, lat: number, lng: number, over: Partial<MapMarker> = {}): MapMarker => ({
  id,
  position: { lat, lng },
  title: `Truck ${id}`,
  kind: 'vehicle',
  tone: 'success',
  glyph: 'V',
  statusLabel: 'LIVE GPS',
  details: ['Recorded just now', 'Source: GPS device'],
  clusterable: true,
  ...over,
});
const depot = (): MapMarker => ({ id: 'facility:1', position: { lat: 17.45, lng: 78.4 }, title: 'North Depot', kind: 'depot', tone: 'info', glyph: 'D' });

const ready = (basemap: 'installed' | 'missing' = 'installed'): OfflineMapsState => ({
  status: 'ready',
  lib: fake.lib as unknown as Extract<OfflineMapsState, { status: 'ready' }>['lib'],
  style: { version: 8, sources: {}, layers: [] },
  basemap,
});

const view = (ui: React.ReactElement) => render(<div id="fake-maplibre-root">{ui}</div>);

beforeEach(() => {
  fake.maps.length = 0;
  fake.markers.length = 0;
  retry.mockClear();
});
afterEach(() => {
  state = { status: 'failed', reason: 'no_webgl' };
});

describe('built-in map without a usable engine', () => {
  it('never renders a blank map: no WebGL shows a labelled list of the same locations', () => {
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5), depot()]} />);
    expect(screen.getByText('Map not available: this browser cannot draw the map')).toBeInTheDocument();
    const table = screen.getByRole('table', { name: 'Fleet positions: locations' });
    expect(within(table).getByRole('rowheader', { name: 'Truck a' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /try loading/i })).not.toBeInTheDocument();
    expect(fake.maps).toHaveLength(0);
  });

  it('offers a retry after a load error', async () => {
    state = { status: 'failed', reason: 'load_error' };
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5)]} />);
    await userEvent.click(screen.getByRole('button', { name: 'Try loading the map again' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it('shows a loading state while the engine loads', () => {
    state = { status: 'loading' };
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5)]} />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading map');
  });
});

describe('built-in map when ready', () => {
  it('says so when no tile file is installed, and still draws the markers', () => {
    state = ready('missing');
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5)]} />);
    expect(screen.getByText('Base map not installed')).toBeInTheDocument();
    expect(fake.markers).toHaveLength(1);
  });

  it('does not show the notice when the tiles are installed', () => {
    state = ready('installed');
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5)]} />);
    expect(screen.queryByText('Base map not installed')).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Fleet positions (interactive map)' })).toBeInTheDocument();
  });

  it('shows the empty message instead of an empty map', () => {
    state = ready();
    view(<MapPanel label="Fleet positions" markers={[]} emptyMessage="No vehicle has reported a position yet." />);
    expect(screen.getByText('No vehicle has reported a position yet.')).toBeInTheDocument();
    expect(fake.maps).toHaveLength(0);
  });

  it('draws one pin per separate item with an accessible name that carries the status', () => {
    state = ready();
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5, { clusterable: false }), vehicle('b', 12.9, 77.6, { clusterable: false }), depot()]} />);
    expect(fake.maps).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Truck a, LIVE GPS' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Truck b, LIVE GPS' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'North Depot' })).toBeInTheDocument();
    expect(fake.maps[0]!.fits).toHaveLength(1);
  });

  it('groups nearby clusterable vehicles when zoomed out and splits them when zoomed in; depots never cluster', () => {
    state = ready();
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5), vehicle('b', 17.41, 78.51), depot()]} />);
    const map = fake.maps[0]!;
    expect(screen.getByRole('button', { name: /2 locations grouped here/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Truck a, LIVE GPS' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'North Depot' })).toBeInTheDocument();
    map.zoom = 16;
    act(() => map.emit('moveend'));
    expect(screen.getByRole('button', { name: 'Truck a, LIVE GPS' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Truck b, LIVE GPS' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /locations grouped here/ })).not.toBeInTheDocument();
  });

  it('leaves unchanged markers alone, replaces a moved one and does not re-fit the view', () => {
    state = ready();
    const first = [vehicle('a', 17.4, 78.5, { clusterable: false }), depot()];
    const { rerender } = view(<MapPanel label="Fleet positions" markers={first} />);
    const depotMarker = fake.markers.find((m) => m.element.getAttribute('aria-label') === 'North Depot')!;
    const oldTruck = fake.markers.find((m) => m.element.getAttribute('aria-label') === 'Truck a, LIVE GPS')!;
    rerender(
      <div id="fake-maplibre-root">
        <MapPanel label="Fleet positions" markers={[vehicle('a', 17.401, 78.501, { clusterable: false }), depot()]} />
      </div>,
    );
    expect(depotMarker.onMap).toBe(true);
    expect(fake.markers.filter((m) => m.element.getAttribute('aria-label') === 'North Depot')).toEqual([depotMarker]);
    expect(oldTruck.onMap).toBe(false);
    const trucks = fake.markers.filter((m) => m.element.getAttribute('aria-label') === 'Truck a, LIVE GPS');
    expect(trucks).toHaveLength(2);
    expect(trucks[1]!.lngLat).toEqual([78.501, 17.401]);
    expect(fake.maps[0]!.fits).toHaveLength(1);
  });

  it('relabels a status change (a vehicle going stale) and removes markers that disappear', () => {
    state = ready();
    const { rerender } = view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5, { clusterable: false }), depot()]} />);
    rerender(
      <div id="fake-maplibre-root">
        <MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5, { clusterable: false, tone: 'danger', statusLabel: 'STALE' })]} />
      </div>,
    );
    expect(screen.queryByRole('button', { name: 'North Depot' })).not.toBeInTheDocument();
    const pin = screen.getByRole('button', { name: 'Truck a, STALE' });
    expect(pin.className).toContain('map-pin--danger');
  });

  it('opens a detail panel with status, timestamp and source when a pin is activated', async () => {
    state = ready();
    view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5, { clusterable: false, tone: 'simulated', statusLabel: 'SIMULATED', details: ['Source: Simulator (demonstration data)'] })]} />);
    await userEvent.click(screen.getByRole('button', { name: 'Truck a, SIMULATED' }));
    const detail = await screen.findByRole('group', { name: 'Selected: Truck a' });
    expect(within(detail).getByText('SIMULATED')).toBeInTheDocument();
    expect(within(detail).getByText('Source: Simulator (demonstration data)')).toBeInTheDocument();
    expect(within(detail).getByText('17.40000, 78.50000')).toBeInTheDocument();
  });

  it('draws only paths with two or more points, one honest style per kind, and reports clicks for picking', () => {
    state = ready();
    const onMapClick = vi.fn();
    view(
      <MapPanel
        label="Pick"
        markers={[]}
        onMapClick={onMapClick}
        paths={[
          { id: 'a', kind: 'planned_straight', label: 'straight', points: [{ lat: 17, lng: 78 }, { lat: 17.1, lng: 78.1 }] },
          { id: 'b', kind: 'recorded', label: 'one point', points: [{ lat: 17, lng: 78 }] },
        ]}
      />,
    );
    const map = fake.maps[0]!;
    expect(map.canvas.style.cursor).toBe('crosshair');
    act(() => map.emit('load'));
    const data = map.sources.get('ecomind-paths')!.data as { features: Array<{ properties: { kind: string }; geometry: { coordinates: number[][] } }> };
    expect(data.features).toHaveLength(1);
    expect(data.features[0]!.properties.kind).toBe('planned_straight');
    expect(data.features[0]!.geometry.coordinates).toEqual([[78, 17], [78.1, 17.1]]);
    const dashed = map.layers.find((l) => l.id === 'ecomind-path-planned_straight')!;
    expect(dashed.paint['line-dasharray']).toBeDefined();
    expect(map.layers.find((l) => l.id === 'ecomind-path-planned_road')!.paint['line-dasharray']).toBeUndefined();
    act(() => map.emit('click', { lngLat: { lat: 17.5, lng: 78.25 } }));
    expect(onMapClick).toHaveBeenCalledWith({ lat: 17.5, lng: 78.25 });
  });

  it('removes the map when the panel unmounts', () => {
    state = ready();
    const { unmount } = view(<MapPanel label="Fleet positions" markers={[vehicle('a', 17.4, 78.5)]} />);
    unmount();
    expect(fake.maps[0]!.removed).toBe(true);
  });
});
