import { useEffect, useRef, useState } from 'react';
import Supercluster from 'supercluster';
import type * as MapLibre from 'maplibre-gl';
import type { GeoPoint, MapMarker, MapPath, PathKind } from '../types';

const PATH_STYLE: Record<PathKind, { color: string; width: number; dash?: number[] }> = {
  planned_road: { color: '#38a8f5', width: 5 },
  planned_straight: { color: '#f5b83d', width: 3, dash: [2, 2] },
  recorded: { color: '#34d399', width: 4 },
  simulated: { color: '#b794f6', width: 3, dash: [0.3, 2] },
};
const PATH_SOURCE = 'ecomind-paths';
const CLUSTER_RADIUS_PX = 56;
const MAX_ZOOM = 17;

interface Shown {
  marker: MapLibre.Marker;
  signature: string;
}

function pinElement(m: MapMarker, selected: boolean): HTMLElement {
  const el = document.createElement('button');
  el.type = 'button';
  el.className = ['map-pin', `map-pin--${m.tone}`, m.kind === 'facility' || m.kind === 'depot' ? 'map-pin--square' : '', selected ? 'map-pin--selected' : '']
    .filter(Boolean)
    .join(' ');
  el.textContent = m.glyph ?? '';
  el.setAttribute('aria-label', m.statusLabel ? `${m.title}, ${m.statusLabel}` : m.title);
  el.title = m.title;
  return el;
}

function clusterElement(count: number): HTMLElement {
  const el = document.createElement('button');
  el.type = 'button';
  el.className = 'map-pin map-pin--info map-pin--cluster';
  el.textContent = String(count);
  el.setAttribute('aria-label', `${count} locations grouped here. Activate to zoom in.`);
  return el;
}

export interface MapLibreSurfaceProps {
  lib: typeof MapLibre;
  style: MapLibre.StyleSpecification;
  label: string;
  markers: MapMarker[];
  paths: MapPath[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onMapClick?: (point: GeoPoint) => void;
  height: number;
  fitKey: string;
}

/** Markers, clusters and paths on the built-in MapLibre map. All DOM and map objects are owned here. */
export function MapLibreSurface({ lib, style, label, markers, paths, selectedId, onSelect, onMapClick, height, fitKey }: MapLibreSurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibre.Map | null>(null);
  const shownRef = useRef(new Map<string, Shown>());
  const renderRef = useRef<() => void>(() => undefined);
  const lastFitRef = useRef<string | null>(null);
  const onSelectRef = useRef(onSelect);
  const onClickRef = useRef(onMapClick);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    onSelectRef.current = onSelect;
    onClickRef.current = onMapClick;
  });

  // Create the map once per mount.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const shown = shownRef.current;
    const map = new lib.Map({
      container: el,
      style,
      center: [0, 20],
      zoom: 1,
      maxPitch: 0,
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: false,
      cooperativeGestures: true,
      maxZoom: MAX_ZOOM + 1,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new lib.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new lib.ScaleControl({ unit: 'metric' }), 'bottom-left');
    map.addControl(new lib.AttributionControl({ compact: true }), 'bottom-right');
    mapRef.current = map;
    map.on('load', () => setLoaded(true));
    map.on('moveend', () => renderRef.current());
    map.on('click', (event) => {
      onClickRef.current?.({ lat: event.lngLat.lat, lng: event.lngLat.lng });
    });
    return () => {
      for (const entry of shown.values()) entry.marker.remove();
      shown.clear();
      map.remove();
      mapRef.current = null;
      lastFitRef.current = null;
      setLoaded(false);
    };
  }, [lib, style]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = onMapClick ? 'crosshair' : '';
  }, [onMapClick, loaded]);

  // Markers: clusterable ones are grouped by supercluster, the rest are always drawn. Elements are diffed by key.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const shown = shownRef.current;
    const clusterable = markers.filter((m) => m.clusterable === true);
    const index = new Supercluster<{ id: string }>({ radius: CLUSTER_RADIUS_PX, maxZoom: MAX_ZOOM });
    index.load(
      clusterable.map((m) => ({
        type: 'Feature' as const,
        properties: { id: m.id },
        geometry: { type: 'Point' as const, coordinates: [m.position.lng, m.position.lat] },
      })),
    );
    const byId = new Map(markers.map((m) => [m.id, m]));

    const draw = () => {
      const bounds = map.getBounds();
      const zoom = Math.max(0, Math.min(MAX_ZOOM, Math.floor(map.getZoom())));
      const west = Math.max(-180, bounds.getWest());
      const east = Math.min(180, bounds.getEast());
      const wanted = new Map<string, { lngLat: [number, number]; signature: string; build: () => HTMLElement; onClick: () => void }>();
      for (const feature of index.getClusters([west, Math.max(-85, bounds.getSouth()), east, Math.min(85, bounds.getNorth())], zoom)) {
        const [lng, lat] = feature.geometry.coordinates as [number, number];
        const props = feature.properties as { cluster?: boolean; cluster_id?: number; point_count?: number; id?: string };
        if (props.cluster && props.cluster_id !== undefined && props.point_count !== undefined) {
          const clusterId = props.cluster_id;
          const count = props.point_count;
          wanted.set(`cluster:${clusterId}`, {
            lngLat: [lng, lat],
            signature: `${count}|${lng}|${lat}`,
            build: () => clusterElement(count),
            onClick: () => map.easeTo({ center: [lng, lat], zoom: Math.min(index.getClusterExpansionZoom(clusterId), MAX_ZOOM + 1) }),
          });
        } else if (props.id !== undefined) {
          const m = byId.get(props.id);
          if (m) wanted.set(`marker:${m.id}`, markerEntry(m));
        }
      }
      for (const m of markers) if (m.clusterable !== true) wanted.set(`marker:${m.id}`, markerEntry(m));

      for (const [key, entry] of shown) {
        if (wanted.has(key)) continue;
        entry.marker.remove();
        shown.delete(key);
      }
      for (const [key, item] of wanted) {
        const existing = shown.get(key);
        if (existing?.signature === item.signature) continue;
        existing?.marker.remove();
        const element = item.build();
        element.addEventListener('click', (event) => {
          event.stopPropagation();
          item.onClick();
        });
        const marker = new lib.Marker({ element, anchor: 'center' }).setLngLat(item.lngLat).addTo(map);
        shown.set(key, { marker, signature: item.signature });
      }
    };

    function markerEntry(m: MapMarker) {
      const selected = m.id === selectedId;
      return {
        lngLat: [m.position.lng, m.position.lat] as [number, number],
        signature: JSON.stringify([m.position, m.title, m.tone, m.glyph, m.kind, m.statusLabel, selected]),
        build: () => pinElement(m, selected),
        onClick: () => onSelectRef.current(m.id),
      };
    }

    renderRef.current = draw;
    draw();
    return () => {
      renderRef.current = () => undefined;
    };
  }, [lib, style, markers, selectedId]);

  // Paths (one GeoJSON source, one layer per kind so each keeps its honest style).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const data: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: paths
        .filter((p) => p.points.length >= 2)
        .map((p) => ({
          type: 'Feature' as const,
          properties: { id: p.id, kind: p.kind },
          geometry: { type: 'LineString' as const, coordinates: p.points.map((pt) => [pt.lng, pt.lat]) },
        })),
    };
    const existing = map.getSource(PATH_SOURCE) as MapLibre.GeoJSONSource | undefined;
    if (existing) {
      existing.setData(data);
      return;
    }
    map.addSource(PATH_SOURCE, { type: 'geojson', data });
    for (const kind of Object.keys(PATH_STYLE) as PathKind[]) {
      const s = PATH_STYLE[kind];
      map.addLayer({
        id: `ecomind-path-${kind}`,
        type: 'line',
        source: PATH_SOURCE,
        filter: ['==', ['get', 'kind'], kind],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': s.color, 'line-width': s.width, 'line-opacity': 0.92, ...(s.dash ? { 'line-dasharray': s.dash } : {}) },
      });
    }
  }, [paths, loaded]);

  // Fit the view when the set of things shown changes, not on every position update.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || lastFitRef.current === fitKey) return;
    const points = [...markers.map((m) => m.position), ...paths.flatMap((p) => p.points)];
    if (points.length === 0) return;
    lastFitRef.current = fitKey;
    const first = points[0];
    if (points.length === 1 && first) {
      map.jumpTo({ center: [first.lng, first.lat], zoom: 15 });
      return;
    }
    const bounds = new lib.LngLatBounds();
    for (const p of points) bounds.extend([p.lng, p.lat]);
    map.fitBounds(bounds, { padding: 48, maxZoom: 16, duration: 0 });
  }, [lib, markers, paths, fitKey]);

  return <div ref={containerRef} className="map-panel__canvas" style={{ height }} role="region" aria-label={`${label} (interactive map)`} />;
}
