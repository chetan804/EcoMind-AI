import { normalizeBaseUrl } from '@/app/config';

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
