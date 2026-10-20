import { ApiError, apiRequest, buildUrl } from '@/services/api-client';

function mockFetch(response: Response | Error) {
  const fn = vi.fn(() => (response instanceof Error ? Promise.reject(response) : Promise.resolve(response)));
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe('buildUrl', () => {
  it('prefixes versioned paths with /api/v1 and leaves operational paths alone', () => {
    expect(buildUrl('/waste-reports')).toBe('/api/v1/waste-reports');
    expect(buildUrl('waste-reports')).toBe('/api/v1/waste-reports');
    expect(buildUrl('/ready', false)).toBe('/ready');
  });
});

describe('apiRequest', () => {
  it('returns parsed JSON on success and sends JSON bodies', async () => {
    const fetchMock = mockFetch(Response.json({ id: 1 }));
    const result = await apiRequest<{ id: number }>('/things', { method: 'POST', body: { a: 1 } });
    expect(result).toEqual({ id: 1 });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/v1/things');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"a":1}');
    expect(init.headers).toMatchObject({ 'Content-Type': 'application/json' });
  });

  it('sends a File as the raw body with its own content type, not as JSON', async () => {
    const fetchMock = mockFetch(Response.json({ id: 'm1' }, { status: 201 }));
    const file = new File(['pixels'], 'a.png', { type: 'image/png' });
    await apiRequest('/waste-reports/media', { method: 'POST', body: file });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBe(file);
    expect(init.headers).toMatchObject({ 'Content-Type': 'image/png' });
  });

  it('maps the structured backend error envelope onto ApiError', async () => {
    mockFetch(
      Response.json(
        { error: { code: 'not_found', message: 'Thing not found', details: null, request_id: 'req-1' } },
        { status: 404 },
      ),
    );
    const error = await apiRequest('/things/1').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: 'not_found', message: 'Thing not found', requestId: 'req-1' });
  });

  it('falls back gracefully when an error response is not JSON', async () => {
    mockFetch(new Response('<html>Bad gateway</html>', { status: 502, statusText: 'Bad Gateway' }));
    const error = (await apiRequest('/x').catch((e: unknown) => e)) as ApiError;
    expect(error).toMatchObject({ status: 502, code: 'http_error', message: 'Bad Gateway' });
  });

  it('reports network failures as status 0', async () => {
    mockFetch(new TypeError('Failed to fetch'));
    const error = (await apiRequest('/x').catch((e: unknown) => e)) as ApiError;
    expect(error).toMatchObject({ status: 0, code: 'network_error' });
  });
});
