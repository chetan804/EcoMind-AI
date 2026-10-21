import type * as MapLibre from 'maplibre-gl';
import { ROAD_MAP_FLAVOR } from './offline-style';

/**
 * Style for vector tiles in the OpenMapTiles schema (https://openmaptiles.org/schema/): the layout
 * used by MapTiler's regional OpenStreetMap datasets and by many OpenStreetMap extracts. The colours
 * are the same original road-map palette as the Protomaps style, so the two look alike.
 *
 * Only layers every OpenMapTiles build carries are used (no POIs or house numbers: they clutter a
 * waste-collection map). Labels use the `Noto Sans` fonts shipped under `map-assets/fonts`; names fall
 * back to the Latin form so that scripts without shipped glyphs do not leave blank labels.
 */
export const OPENMAPTILES_SOURCE = 'openmaptiles';

const P = ROAD_MAP_FLAVOR;
const NAME: MapLibre.ExpressionSpecification = [
  'coalesce',
  ['get', 'name:en'],
  ['get', 'name:latin'],
  ['get', 'name_en'],
  ['get', 'name'],
];
const FONT_REGULAR = ['Noto Sans Regular'];
const FONT_MEDIUM = ['Noto Sans Medium'];
const FONT_ITALIC = ['Noto Sans Italic'];

const ROAD_CLASSES = {
  motorway: ['motorway', 'trunk'],
  main: ['primary', 'secondary', 'tertiary'],
  minor: ['minor', 'service', 'track'],
} as const;

const fill = (
  id: string,
  sourceLayer: string,
  color: string,
  filter?: MapLibre.FilterSpecification,
  extra: Partial<MapLibre.FillLayerSpecification> = {},
): MapLibre.FillLayerSpecification => ({
  id,
  type: 'fill',
  source: OPENMAPTILES_SOURCE,
  'source-layer': sourceLayer,
  ...(filter ? { filter } : {}),
  paint: { 'fill-color': color },
  ...extra,
});

function roadLayers(): MapLibre.LayerSpecification[] {
  const line = (
    id: string,
    classes: readonly string[],
    color: string,
    width: MapLibre.ExpressionSpecification,
    extra: Partial<MapLibre.LineLayerSpecification> = {},
  ): MapLibre.LineLayerSpecification => ({
    id,
    type: 'line',
    source: OPENMAPTILES_SOURCE,
    'source-layer': 'transportation',
    filter: ['all', ['in', ['get', 'class'], ['literal', classes]], ['!=', ['get', 'brunnel'], 'tunnel']],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': color, 'line-width': width },
    ...extra,
  });
  const widths = (a: number, b: number, c: number): MapLibre.ExpressionSpecification => [
    'interpolate',
    ['exponential', 1.5],
    ['zoom'],
    8,
    a,
    13,
    b,
    18,
    c,
  ];
  return [
    line('roads-minor-casing', ROAD_CLASSES.minor, P.minor_casing, widths(0.2, 2.2, 14), { minzoom: 12 }),
    line('roads-main-casing', ROAD_CLASSES.main, P.major_casing_late, widths(0.6, 3.6, 24), { minzoom: 8 }),
    line('roads-motorway-casing', ROAD_CLASSES.motorway, P.highway_casing_late, widths(1, 4.6, 28)),
    line('roads-minor', ROAD_CLASSES.minor, P.minor_a, widths(0.1, 1.6, 12), { minzoom: 12 }),
    line('roads-main', ROAD_CLASSES.main, P.major, widths(0.4, 2.8, 22), { minzoom: 8 }),
    line('roads-motorway', ROAD_CLASSES.motorway, P.highway, widths(0.8, 3.6, 26)),
    {
      id: 'roads-path',
      type: 'line',
      source: OPENMAPTILES_SOURCE,
      'source-layer': 'transportation',
      minzoom: 14,
      filter: ['in', ['get', 'class'], ['literal', ['path', 'pedestrian']]],
      paint: { 'line-color': '#c4c7ca', 'line-width': 1, 'line-dasharray': [2, 2] },
    },
    {
      id: 'roads-rail',
      type: 'line',
      source: OPENMAPTILES_SOURCE,
      'source-layer': 'transportation',
      minzoom: 10,
      filter: ['==', ['get', 'class'], 'rail'],
      paint: { 'line-color': '#b0b4b8', 'line-width': 1.2, 'line-dasharray': [4, 3] },
    },
  ];
}

function labelLayers(): MapLibre.LayerSpecification[] {
  const place = (
    id: string,
    classes: readonly string[],
    size: MapLibre.ExpressionSpecification | number,
    color: string,
    font: string[],
    extra: Partial<MapLibre.SymbolLayerSpecification> = {},
  ): MapLibre.SymbolLayerSpecification => ({
    id,
    type: 'symbol',
    source: OPENMAPTILES_SOURCE,
    'source-layer': 'place',
    filter: ['in', ['get', 'class'], ['literal', classes]],
    layout: { 'text-field': NAME, 'text-font': font, 'text-size': size, 'text-max-width': 8 },
    paint: { 'text-color': color, 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 },
    ...extra,
  });
  return [
    {
      id: 'labels-road',
      type: 'symbol',
      source: OPENMAPTILES_SOURCE,
      'source-layer': 'transportation_name',
      minzoom: 13,
      layout: {
        'symbol-placement': 'line',
        'text-field': NAME,
        'text-font': FONT_REGULAR,
        'text-size': 11,
      },
      paint: { 'text-color': P.roads_label_minor, 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 },
    },
    {
      id: 'labels-water',
      type: 'symbol',
      source: OPENMAPTILES_SOURCE,
      'source-layer': 'water_name',
      layout: { 'text-field': NAME, 'text-font': FONT_ITALIC, 'text-size': 12 },
      paint: { 'text-color': P.ocean_label, 'text-halo-color': '#ffffff', 'text-halo-width': 1.2 },
    },
    place('labels-neighbourhood', ['suburb', 'neighbourhood', 'quarter'], 11, P.subplace_label, FONT_REGULAR, {
      minzoom: 12,
    }),
    place('labels-village', ['village', 'hamlet', 'town'], 12, P.subplace_label, FONT_MEDIUM, { minzoom: 9 }),
    place('labels-city', ['city'], ['interpolate', ['linear'], ['zoom'], 4, 12, 10, 18], P.city_label, FONT_MEDIUM),
    place('labels-state', ['state', 'province'], 12, P.state_label, FONT_REGULAR, { maxzoom: 7 }),
    place('labels-country', ['country'], 13, P.country_label, FONT_MEDIUM, { maxzoom: 6 }),
  ];
}

export function openMapTilesLayers(): MapLibre.LayerSpecification[] {
  return [
    { id: 'background', type: 'background', paint: { 'background-color': P.earth } },
    fill('landcover-grass', 'landcover', P.park_a, ['in', ['get', 'class'], ['literal', ['grass', 'farmland']]]),
    fill('landcover-wood', 'landcover', P.wood_a, ['in', ['get', 'class'], ['literal', ['wood', 'forest']]]),
    fill('landuse-industrial', 'landuse', P.industrial, [
      'in',
      ['get', 'class'],
      ['literal', ['industrial', 'commercial', 'retail', 'railway']],
    ]),
    fill('landuse-hospital', 'landuse', P.hospital, ['==', ['get', 'class'], 'hospital']),
    fill('landuse-school', 'landuse', P.school, [
      'in',
      ['get', 'class'],
      ['literal', ['school', 'university', 'college', 'kindergarten']],
    ]),
    fill('landuse-green', 'landuse', P.park_b, [
      'in',
      ['get', 'class'],
      ['literal', ['cemetery', 'playground', 'pitch', 'stadium', 'track']],
    ]),
    fill('park', 'park', P.park_a, undefined, { paint: { 'fill-color': P.park_a, 'fill-opacity': 0.85 } }),
    fill('water', 'water', P.water),
    {
      id: 'waterway',
      type: 'line',
      source: OPENMAPTILES_SOURCE,
      'source-layer': 'waterway',
      paint: { 'line-color': P.water, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.5, 16, 3] },
    },
    fill('building', 'building', P.buildings, undefined, { minzoom: 14 }),
    ...roadLayers(),
    {
      id: 'boundary-state',
      type: 'line',
      source: OPENMAPTILES_SOURCE,
      'source-layer': 'boundary',
      filter: ['all', ['<=', ['get', 'admin_level'], 4], ['!=', ['get', 'maritime'], 1]],
      paint: { 'line-color': '#9aa0a6', 'line-width': 1, 'line-dasharray': [3, 2] },
    },
    ...labelLayers(),
  ];
}

/** Style over an OpenMapTiles-schema PMTiles file served by this deployment. */
export function openMapTilesStyle(
  tilesUrl: string,
  assetsPath: string,
  attribution: string,
): MapLibre.StyleSpecification {
  const assets = assetsPath.replace(/\/+$/, '');
  const base = new URL(assets, window.location.origin).href;
  return {
    version: 8,
    glyphs: `${base}/fonts/{fontstack}/{range}.pbf`,
    sources: {
      [OPENMAPTILES_SOURCE]: {
        type: 'vector',
        url: `pmtiles://${new URL(tilesUrl, window.location.origin).href}`,
        attribution,
      },
    },
    layers: openMapTilesLayers(),
  };
}
