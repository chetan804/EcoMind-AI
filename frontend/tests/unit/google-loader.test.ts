import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type * as LoaderModule from '@/features/maps/lib/google-loader';

type Loader = typeof LoaderModule;

async function loadWith(key: string): Promise<Loader> {
  vi.resetModules();
  vi.doMock('@/app/config', () => ({ config: { googleMapsApiKey: key, googleMapsMapId: 'DEMO_MAP_ID' } }));
  return import('@/features/maps/lib/google-loader');
}

const scripts = () => Array.from(document.querySelectorAll<HTMLScriptElement>('script[src*="maps.googleapis.com"]'));

function installFakeGoogle(): void {
  const importLibrary = vi.fn().mockResolvedValue({});
  (window as unknown as { google: unknown }).google = { maps: { importLibrary } };
}

describe('Google Maps loader', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    document.head.innerHTML = '';
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.doUnmock('@/app/config');
    delete (window as unknown as { google?: unknown }).google;
    delete (window as { gm_authFailure?: unknown }).gm_authFailure;
  });

  it('reports a missing key without requesting anything from Google', async () => {
    const loader = await loadWith('');
    loader.ensureGoogleMaps();
    expect(scripts()).toHaveLength(0);
    // The current state is a failure with a specific reason, never "loading forever".
    const { renderHook } = await import('@testing-library/react');
    expect(renderHook(() => loader.useGoogleMapsState()).result.current).toEqual({ status: 'failed', reason: 'missing_key' });
  });

  it('injects the script once, keeps the key in the query string it must, and becomes ready', async () => {
    const loader = await loadWith('test-browser-key');
    const { renderHook } = await import('@testing-library/react');
    const hook = renderHook(() => loader.useGoogleMapsState());
    expect(hook.result.current.status).toBe('idle');
    loader.ensureGoogleMaps();
    loader.ensureGoogleMaps();
    expect(scripts()).toHaveLength(1);
    const url = new URL(scripts()[0]!.src);
    expect(url.searchParams.get('loading')).toBe('async');
    expect(url.searchParams.get('key')).toBe('test-browser-key');
    installFakeGoogle();
    const { act } = await import('@testing-library/react');
    await act(async () => {
      (window as unknown as Record<string, () => void>)['__ecomindMapsReady']!();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(hook.result.current.status).toBe('ready');
  });

  it('classifies a blocked script as a network failure and allows a retry', async () => {
    const loader = await loadWith('k');
    const { renderHook, act } = await import('@testing-library/react');
    const hook = renderHook(() => loader.useGoogleMapsState());
    loader.ensureGoogleMaps();
    await act(async () => {
      scripts()[0]!.onerror?.(new Event('error'));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(hook.result.current).toEqual({ status: 'failed', reason: 'network' });
    act(() => loader.retryGoogleMaps());
    expect(hook.result.current.status).toBe('loading');
    expect(scripts()).toHaveLength(1);
  });

  it('times out when Google never answers', async () => {
    const loader = await loadWith('k');
    const { renderHook, act } = await import('@testing-library/react');
    const hook = renderHook(() => loader.useGoogleMapsState());
    loader.ensureGoogleMaps();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(loader.LOAD_TIMEOUT_MS + 10);
    });
    expect(hook.result.current).toEqual({ status: 'failed', reason: 'timeout' });
  });

  it('reports a rejected key through Google\'s auth-failure hook and does not offer a retry', async () => {
    const loader = await loadWith('bad-key');
    const { renderHook, act } = await import('@testing-library/react');
    const hook = renderHook(() => loader.useGoogleMapsState());
    loader.ensureGoogleMaps();
    act(() => window.gm_authFailure?.());
    expect(hook.result.current).toEqual({ status: 'failed', reason: 'auth' });
    act(() => loader.retryGoogleMaps());
    expect(hook.result.current).toEqual({ status: 'failed', reason: 'auth' });
  });
});
