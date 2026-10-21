import { describe, expect, it } from 'vitest';
import { validateStyleMin } from '@maplibre/maplibre-gl-style-spec';
import { detectTileSchema, openMapTilesAttribution } from '@/features/maps/lib/tile-schema';
import { openMapTilesLayers, openMapTilesStyle } from '@/features/maps/lib/openmaptiles-style';

const layers = (...ids: string[]) => ({ vector_layers: ids.map((id) => ({ id })) });

describe('detectTileSchema', () => {
  it('recognises the Protomaps layout', () => {
    expect(detectTileSchema(layers('earth', 'roads', 'water', 'places', 'landuse'))).toBe('protomaps');
  });
  it('recognises the OpenMapTiles layout', () => {
    expect(detectTileSchema(layers('transportation', 'place', 'water', 'landcover', 'building'))).toBe('openmaptiles');
  });
  it('treats a file with neither layout as unknown', () => {
    expect(detectTileSchema(layers('roads', 'water'))).toBe('unknown');
    expect(detectTileSchema(layers('poi'))).toBe('unknown');
  });
  it.each([undefined, null, 'text', {}, { vector_layers: 'x' }, { vector_layers: [1, null, {}] }])(
    'falls back to the documented default for unusable metadata: %j',
    (metadata) => {
      expect(detectTileSchema(metadata)).toBe('protomaps');
    },
  );
});

describe('openMapTilesAttribution', () => {
  it('always credits OpenStreetMap', () => {
    expect(openMapTilesAttribution(undefined)).toContain('OpenStreetMap contributors');
    expect(openMapTilesAttribution(undefined)).not.toContain('MapTiler');
  });
  it('credits MapTiler for MapTiler data, as its terms require', () => {
    const text = openMapTilesAttribution({ attribution: '© MapTiler © OpenStreetMap contributors' });
    expect(text).toContain('MapTiler');
    expect(text).toContain('OpenStreetMap contributors');
  });
  it('credits OpenMapTiles for a Planetiler/OpenMapTiles build', () => {
    const text = openMapTilesAttribution({
      attribution:
        '<a href="https://www.openmaptiles.org/" target="_blank">&copy; OpenMapTiles</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>',
    });
    expect(text).toContain('>OpenMapTiles</a>');
    expect(text).toContain('OpenStreetMap contributors');
    expect(text).not.toContain('MapTiler');
    expect(text).not.toContain('&copy;');
  });
  it('never copies markup from the file into the page', () => {
    const text = openMapTilesAttribution({ attribution: '<img src=x onerror=alert(1)> MapTiler' });
    expect(text).not.toContain('onerror');
    expect(text).not.toContain('<img');
  });
});

describe('OpenMapTiles style', () => {
  const style = openMapTilesStyle('/map-assets/tiles/region.pmtiles', '/map-assets', 'attr');

  it('is a valid MapLibre style', () => {
    const errors = validateStyleMin(style as never);
    expect(errors.map((e) => e.message)).toEqual([]);
  });
  it('has unique layer ids and only reads layers of the OpenMapTiles schema', () => {
    const ids = openMapTilesLayers().map((l) => l.id);
    expect(new Set(ids).size).toBe(ids.length);
    const schemaLayers = new Set([
      'landcover', 'landuse', 'park', 'water', 'waterway', 'building', 'transportation',
      'transportation_name', 'boundary', 'water_name', 'place',
    ]);
    for (const layer of openMapTilesLayers()) {
      if ('source-layer' in layer && layer['source-layer']) expect(schemaLayers.has(layer['source-layer'])).toBe(true);
    }
  });
  it('loads fonts from this deployment only', () => {
    expect(style.glyphs).toMatch(/^https?:\/\/[^/]+\/map-assets\/fonts\/\{fontstack\}\/\{range\}\.pbf$/);
  });
});
