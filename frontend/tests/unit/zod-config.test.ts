import '@/app/zod-config';
import { z } from 'zod';

describe('zod configuration', () => {
  it('runs in jitless mode so the app works under a CSP without unsafe-eval', () => {
    expect(z.config().jitless).toBe(true);
    expect(z.object({ n: z.number() }).parse({ n: 1 })).toEqual({ n: 1 });
  });
});
