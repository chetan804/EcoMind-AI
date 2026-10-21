import { createHmac } from 'node:crypto';

/** RFC 6238 time-based one-time password (HMAC-SHA1, 30 s steps), computed independently of the app. */
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

export function base32Decode(text: string): Buffer {
  const clean = text.replace(/[\s=]/g, '').toUpperCase();
  let bits = '';
  for (const char of clean) {
    const value = ALPHABET.indexOf(char);
    if (value < 0) throw new Error(`not base32: ${char}`);
    bits += value.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

export function totp(secret: string, atMs: number = Date.now(), digits = 6, periodSeconds = 30): string {
  const counter = Math.floor(atMs / 1000 / periodSeconds);
  const message = Buffer.alloc(8);
  message.writeBigUInt64BE(BigInt(counter));
  const hmac = createHmac('sha1', base32Decode(secret)).update(message).digest();
  const offset = (hmac[hmac.length - 1] ?? 0) & 0x0f;
  const binary =
    (((hmac[offset] ?? 0) & 0x7f) << 24) |
    (((hmac[offset + 1] ?? 0) & 0xff) << 16) |
    (((hmac[offset + 2] ?? 0) & 0xff) << 8) |
    ((hmac[offset + 3] ?? 0) & 0xff);
  return String(binary % 10 ** digits).padStart(digits, '0');
}
