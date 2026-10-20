import { layers, LIGHT, type Flavor } from '@protomaps/basemaps';
import type * as MapLibre from 'maplibre-gl';

/**
 * Colours chosen to read like the familiar road-map look (pale land, blue water, green parks, white
 * streets with grey casings, amber highways). It is an original palette over OpenStreetMap data, not
 * Google's data or styling.
 */
export const ROAD_MAP_FLAVOR: Flavor = {
  ...LIGHT,
  background: '#f1f3f4',
  earth: '#f5f5f5',
  water: '#aadaff',
  park_a: '#c8e6c9',
  park_b: '#c8e6c9',
  wood_a: '#b9deb4',
  wood_b: '#b9deb4',
  scrub_a: '#d3e8c8',
  scrub_b: '#d3e8c8',
  hospital: '#f9dcdc',
  school: '#f2eadb',
  industrial: '#ecebe9',
  buildings: '#e4e1dc',
  minor_service: '#ffffff',
  minor_service_casing: '#e1e3e6',
  minor_a: '#ffffff',
  minor_b: '#ffffff',
  minor_casing: '#dadce0',
  link: '#ffffff',
  link_casing: '#dadce0',
  other: '#ffffff',
  major: '#ffffff',
  major_casing_early: '#c9cdd2',
  major_casing_late: '#c9cdd2',
  highway: '#fde293',
  highway_casing_early: '#f1b43d',
  highway_casing_late: '#f1b43d',
  roads_label_minor: '#5f6368',
  roads_label_minor_halo: '#ffffff',
  roads_label_major: '#3c4043',
  roads_label_major_halo: '#ffffff',
  subplace_label: '#5f6368',
  subplace_label_halo: '#ffffff',
  city_label: '#202124',
  city_label_halo: '#ffffff',
  state_label: '#70757a',
  state_label_halo: '#ffffff',
  country_label: '#5f6368',
  ocean_label: '#4a7baa',
};

const ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a> · <a href="https://protomaps.com" target="_blank" rel="noopener noreferrer">Protomaps</a>';

function absolute(path: string): string {
  return new URL(path, window.location.origin).href;
}

/** Style with the installed vector basemap (PMTiles served by this deployment). */
export function basemapStyle(tilesUrl: string, assetsPath: string): MapLibre.StyleSpecification {
  const assets = assetsPath.replace(/\/+$/, '');
  return {
    version: 8,
    glyphs: `${absolute(assets)}/fonts/{fontstack}/{range}.pbf`,
    sprite: `${absolute(assets)}/sprites/v4/light`,
    sources: {
      protomaps: { type: 'vector', url: `pmtiles://${absolute(tilesUrl)}`, attribution: ATTRIBUTION },
    },
    layers: layers('protomaps', ROAD_MAP_FLAVOR, { lang: 'en' }) as MapLibre.LayerSpecification[],
  };
}

/** Plain background used when no tile file is installed: overlays are still drawn and say so. */
export function plainStyle(): MapLibre.StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [{ id: 'plain-background', type: 'background', paint: { 'background-color': ROAD_MAP_FLAVOR.background } }],
  };
}
