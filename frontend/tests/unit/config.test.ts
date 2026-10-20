import { normalizeBaseUrl, resolveMapProvider } from '@/app/config';

describe('normalizeBaseUrl', () => {
  it('treats missing or blank values as same origin', () => {
    expect(normalizeBaseUrl(undefined)).toBe('');
    expect(normalizeBaseUrl('   ')).toBe('');
  });

  it('removes trailing slashes', () => {
    expect(normalizeBaseUrl('https://api.example.org/')).toBe('https://api.example.org');
    expect(normalizeBaseUrl('https://api.example.org///')).toBe('https://api.example.org');
  });
});

describe('resolveMapProvider', () => {
  it('defaults to the offline provider and needs no key', () => {
    expect(resolveMapProvider(undefined, '')).toBe('offline');
    expect(resolveMapProvider('', '')).toBe('offline');
    expect(resolveMapProvider('nonsense', '')).toBe('offline');
  });

  it('keeps Google only when it is chosen or when a browser key exists and nothing else is chosen', () => {
    expect(resolveMapProvider(undefined, 'a-key')).toBe('google');
    expect(resolveMapProvider('offline', 'a-key')).toBe('offline');
    expect(resolveMapProvider(' Google ', '')).toBe('google');
  });
});
