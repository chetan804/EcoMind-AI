/** Which vector-tile layout an installed PMTiles file uses, read from its own metadata. */
export type TileSchema = 'protomaps' | 'openmaptiles' | 'unknown';

const PROTOMAPS_LAYERS = ['earth', 'roads', 'landuse', 'water', 'places'];
const OPENMAPTILES_LAYERS = ['transportation', 'water', 'place', 'landuse', 'landcover'];

function layerIds(metadata: unknown): string[] {
  if (typeof metadata !== 'object' || metadata === null) return [];
  const layers = (metadata as { vector_layers?: unknown }).vector_layers;
  if (!Array.isArray(layers)) return [];
  return layers.flatMap((layer: unknown) => {
    const id = typeof layer === 'object' && layer !== null ? (layer as { id?: unknown }).id : undefined;
    return typeof id === 'string' ? [id] : [];
  });
}

/**
 * `protomaps` needs `earth` + `roads`; `openmaptiles` needs `transportation` + `place`. A file with
 * neither is `unknown`: drawing it with the wrong style would give a blank map, so the app says so.
 * Metadata that cannot be read at all is treated as the documented default (`protomaps`).
 */
export function detectTileSchema(metadata: unknown): TileSchema {
  const ids = layerIds(metadata);
  if (ids.length === 0) return 'protomaps';
  const has = (...wanted: string[]) => wanted.every((id) => ids.includes(id));
  if (has('earth', 'roads') && PROTOMAPS_LAYERS.some((id) => ids.includes(id))) return 'protomaps';
  if (has('transportation', 'place') && OPENMAPTILES_LAYERS.some((id) => ids.includes(id))) return 'openmaptiles';
  return 'unknown';
}

const OSM =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>';
const MAPTILER =
  '© <a href="https://www.maptiler.com/copyright/" target="_blank" rel="noopener noreferrer">MapTiler</a>';
const OPENMAPTILES =
  '© <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener noreferrer">OpenMapTiles</a>';

/**
 * Attribution for an OpenMapTiles-schema file. The text is built here, never copied as HTML from the
 * file: OpenStreetMap is always credited (ODbL); MapTiler is credited when the file says it is
 * MapTiler data (its terms require that credit); OpenMapTiles is credited when the file says it was
 * built with the OpenMapTiles schema (as the Planetiler build in scripts/maps/build_region_data.py does).
 */
export function openMapTilesAttribution(metadata: unknown): string {
  const declared =
    typeof metadata === 'object' && metadata !== null ? (metadata as { attribution?: unknown }).attribution : undefined;
  const fromMapTiler = typeof declared === 'string' && /maptiler/i.test(declared);
  // "© OpenMapTiles" would also match a MapTiler file's "OpenMapTiles"; MapTiler's own credit covers that case.
  const fromOpenMapTiles = !fromMapTiler && typeof declared === 'string' && /openmaptiles/i.test(declared);
  if (fromMapTiler) return `${MAPTILER} ${OSM}`;
  return fromOpenMapTiles ? `${OPENMAPTILES} ${OSM}` : OSM;
}
