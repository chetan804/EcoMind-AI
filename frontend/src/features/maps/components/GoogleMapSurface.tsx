import { useEffect, useRef } from 'react';
import { MarkerClusterer } from '@googlemaps/markerclusterer';
import { config } from '@/app/config';
import type { GeoPoint, MapMarker, MapPath, PathKind } from '../types';

const PATH_STYLE: Record<PathKind, { color: string; weight: number; dash?: 'dashed' | 'dotted' }> = {
  planned_road: { color: '#38a8f5', weight: 5 },
  planned_straight: { color: '#f5b83d', weight: 3, dash: 'dashed' },
  recorded: { color: '#34d399', weight: 4 },
  simulated: { color: '#b794f6', weight: 3, dash: 'dotted' },
};

interface Entry {
  marker: google.maps.marker.AdvancedMarkerElement;
  signature: string;
  clustered: boolean;
}

function pinElement(m: MapMarker, selected: boolean): HTMLElement {
  const el = document.createElement('div');
  el.className = ['map-pin', `map-pin--${m.tone}`, m.kind === 'facility' || m.kind === 'depot' ? 'map-pin--square' : '', selected ? 'map-pin--selected' : '']
    .filter(Boolean)
    .join(' ');
  el.textContent = m.glyph ?? '';
  return el;
}

/** Google Maps objects are mutated imperatively; keeping that in plain functions keeps it out of React's data flow. */
function detach(marker: google.maps.marker.AdvancedMarkerElement): void {
  marker.map = null;
}
function attach(marker: google.maps.marker.AdvancedMarkerElement, map: google.maps.Map): void {
  marker.map = map;
}

function dashIcons(color: string, dash: 'dashed' | 'dotted'): google.maps.IconSequence[] {
  return [
    {
      icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, strokeColor: color, scale: dash === 'dotted' ? 2 : 3 },
      offset: '0',
      repeat: dash === 'dotted' ? '8px' : '16px',
    },
  ];
}

export interface GoogleMapSurfaceProps {
  maps: typeof google.maps;
  label: string;
  markers: MapMarker[];
  paths: MapPath[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onMapClick?: (point: GeoPoint) => void;
  height: number;
  fitKey: string;
}

/** Renders markers, clusters and paths on a real Google map. All DOM/Maps objects are owned here. */
export function GoogleMapSurface({ maps, label, markers, paths, selectedId, onSelect, onMapClick, height, fitKey }: GoogleMapSurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const clustererRef = useRef<MarkerClusterer | null>(null);
  const entriesRef = useRef(new Map<string, Entry>());
  const linesRef = useRef<google.maps.Polyline[]>([]);
  const lastFitRef = useRef<string | null>(null);
  const onSelectRef = useRef(onSelect);
  const onClickRef = useRef(onMapClick);
  useEffect(() => {
    onSelectRef.current = onSelect;
    onClickRef.current = onMapClick;
  });

  // Create the map once per mount.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const entries = entriesRef.current;
    const map = new maps.Map(el, {
      center: { lat: 0, lng: 0 },
      zoom: 2,
      mapId: config.googleMapsMapId,
      mapTypeControl: false,
      streetViewControl: false,
      clickableIcons: false,
      gestureHandling: 'cooperative',
    });
    mapRef.current = map;
    const click = map.addListener('click', (event: google.maps.MapMouseEvent) => {
      const at = event.latLng;
      if (at && onClickRef.current) onClickRef.current({ lat: at.lat(), lng: at.lng() });
    });
    return () => {
      click.remove();
      clustererRef.current?.clearMarkers();
      clustererRef.current = null;
      for (const entry of entries.values()) detach(entry.marker);
      entries.clear();
      for (const line of linesRef.current) line.setMap(null);
      linesRef.current = [];
      mapRef.current = null;
      lastFitRef.current = null;
      el.replaceChildren();
    };
  }, [maps]);

  // Keep markers in sync (diffed by id: unchanged markers are left alone).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const entries = entriesRef.current;
    if (!clustererRef.current) clustererRef.current = new MarkerClusterer({ map, markers: [] });
    const clusterer = clustererRef.current;
    const wanted = new Set(markers.map((m) => m.id));
    for (const [id, entry] of entries) {
      if (wanted.has(id)) continue;
      if (entry.clustered) clusterer.removeMarker(entry.marker);
      detach(entry.marker);
      entries.delete(id);
    }
    for (const m of markers) {
      const selected = m.id === selectedId;
      const signature = JSON.stringify([m.position, m.title, m.tone, m.glyph, m.kind, m.clusterable, selected]);
      const existing = entries.get(m.id);
      if (existing?.signature === signature) continue;
      if (existing) {
        if (existing.clustered) clusterer.removeMarker(existing.marker);
        detach(existing.marker);
      }
      const marker = new maps.marker.AdvancedMarkerElement({
        position: m.position,
        title: m.title,
        content: pinElement(m, selected),
        gmpClickable: true,
      });
      marker.addListener('click', () => onSelectRef.current(m.id));
      const clustered = m.clusterable === true;
      if (clustered) clusterer.addMarker(marker);
      else attach(marker, map);
      entries.set(m.id, { marker, signature, clustered });
    }
  }, [maps, markers, selectedId]);

  // Paths.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const lines = paths
      .filter((p) => p.points.length >= 2)
      .map((p) => {
        const style = PATH_STYLE[p.kind];
        return new maps.Polyline({
          map,
          path: p.points,
          strokeColor: style.color,
          strokeWeight: style.weight,
          strokeOpacity: style.dash ? 0 : 0.9,
          icons: style.dash ? dashIcons(style.color, style.dash) : undefined,
        });
      });
    linesRef.current = lines;
    return () => {
      for (const line of lines) line.setMap(null);
      linesRef.current = [];
    };
  }, [maps, paths]);

  // Fit the view when the set of things shown changes, not on every position update.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || lastFitRef.current === fitKey) return;
    const points = [...markers.map((m) => m.position), ...paths.flatMap((p) => p.points)];
    if (points.length === 0) return;
    lastFitRef.current = fitKey;
    if (points.length === 1) {
      map.setCenter(points[0]!);
      map.setZoom(15);
      return;
    }
    const bounds = new maps.LatLngBounds();
    for (const p of points) bounds.extend(p);
    map.fitBounds(bounds, 48);
  }, [maps, markers, paths, fitKey]);

  return <div ref={containerRef} className="map-panel__canvas" style={{ height }} role="region" aria-label={`${label} (interactive map)`} />;
}
