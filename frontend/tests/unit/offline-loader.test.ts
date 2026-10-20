import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type * as LoaderModule from '@/features/maps/lib/offline-loader';

type Loader = typeof LoaderModule;

const addProtocol = vi.fn();
const setWorkerUrl = vi.fn();
const getHeader = vi.fn();
const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

async function freshLoader(options: { importFails?: boolean } = {}): Promise<Loader> {
  vi.resetModules();
  vi.doMock('@/app/config', () => ({ config: { mapTilesUrl: '/map-assets/tiles/region.pmtiles', mapAssetsPath: '/map-assets' } }));
  if (options.importFails) {
    vi.doMock('maplibre-gl', () => {
      throw new Error('chunk failed');
    });
  } else {
    vi.doMock('maplibre-gl', () => ({ addProtocol, setWorkerUrl }));
  }
  vi.doMock('maplibre-gl/dist/maplibre-gl.css', () => ({}));
  vi.doMock('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url', () => ({ default: '/assets/worker.js' }));
  vi.doMock('pmtiles', () => ({
    Protocol: class {
      tile = () => undefined;
    },
    PMTiles: class {
      getHeader = getHeader;
    },
  }));
  return import('@/features/maps/lib/offline-loader');
}

async function stateOf(loader: Loader): Promise<LoaderModule.OfflineMapsState> {
  const { renderHook } = await import('@testing-library/react');
  return renderHook(() => loader.useOfflineMapsState()).result.current;
}

function withWebgl(on: boolean): void {
  if (!on) {
    delete (globalThis as { WebGL2RenderingContext?: unknown }).WebGL2RenderingContext;
    return;
  }
  (globalThis as { WebGL2RenderingContext?: unknown }).WebGL2RenderingContext = class {};
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as unknown as RenderingContext);
}

describe('offline map loader', () => {
  beforeEach(() => {
    addProtocol.mockReset();
    setWorkerUrl.mockReset();
    getHeader.mockReset();
  });
  afterEach(() => {
    withWebgl(false);
    vi.restoreAllMocks();
    vi.doUnmock('maplibre-gl');
    vi.doUnmock('pmtiles');
    vi.doUnmock('@/app/config');
  });

  it('reports no WebGL without loading anything', async () => {
    withWebgl(false);
    const loader = await freshLoader();
    loader.ensureOfflineMaps();
    await flush();
    expect(await stateOf(loader)).toEqual({ status: 'failed', reason: 'no_webgl' });
    expect(addProtocol).not.toHaveBeenCalled();
  });

  it('becomes ready with the installed basemap when the tile file answers', async () => {
    withWebgl(true);
    getHeader.mockResolvedValue({});
    const loader = await freshLoader();
    loader.ensureOfflineMaps();
    loader.ensureOfflineMaps();
    await flush();
    await flush();
    const state = await stateOf(loader);
    expect(state.status).toBe('ready');
    if (state.status !== 'ready') return;
    expect(state.basemap).toBe('installed');
    expect(Object.keys(state.style.sources)).toEqual(['protomaps']);
    expect(addProtocol).toHaveBeenCalledTimes(1);
    expect(setWorkerUrl).toHaveBeenCalledWith('/assets/worker.js');
  });

  it('is still ready, on a plain background, when no tile file is installed', async () => {
    withWebgl(true);
    getHeader.mockRejectedValue(new Error('404'));
    const loader = await freshLoader();
    loader.ensureOfflineMaps();
    await flush();
    await flush();
    const state = await stateOf(loader);
    expect(state.status).toBe('ready');
    if (state.status !== 'ready') return;
    expect(state.basemap).toBe('missing');
    expect(state.style.layers.map((l) => l.id)).toEqual(['plain-background']);
  });

  it('classifies a failed engine download as load_error and can retry', async () => {
    withWebgl(true);
    const loader = await freshLoader({ importFails: true });
    loader.ensureOfflineMaps();
    await flush();
    await flush();
    expect(await stateOf(loader)).toEqual({ status: 'failed', reason: 'load_error' });
  });
});
