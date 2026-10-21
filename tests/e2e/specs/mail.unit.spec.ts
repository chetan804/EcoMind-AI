import { chmodSync, mkdirSync, truncateSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { configFromEnv, createMailClient, MAX_LOG_BYTES, type MailConfig } from './mail';

/**
 * Tests of the e-mail helper itself (no browser, no stack). A small HTTP server stands in for Mailpit and
 * speaks the two endpoints the helper uses, so the real fetch path is exercised, including failures.
 */

type Handler = (url: URL, res: ServerResponse) => void;

async function withServer<T>(handler: Handler, run: (base: string) => Promise<T>): Promise<T> {
  const server: Server = createServer((req: IncomingMessage, res: ServerResponse) => {
    handler(new URL(req.url ?? '/', 'http://x'), res);
  });
  await new Promise<void>((ok) => server.listen(0, '127.0.0.1', ok));
  try {
    return await run(`http://127.0.0.1:${(server.address() as AddressInfo).port}`);
  } finally {
    await new Promise((done) => server.close(done));
  }
}

const json = (res: ServerResponse, body: unknown, status = 200): void => {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(typeof body === 'string' ? body : JSON.stringify(body));
};

const LINK = 'https://app.example/reset-password#token=abc_DEF-123';
const quick = (over: Partial<MailConfig>): MailConfig => ({
  mailpitUrl: '',
  logFile: '',
  timeoutMs: 400,
  pollMs: 50,
  requestTimeoutMs: 500,
  ...over,
});

/** A fake inbox: `search` lists ids, `messages` holds the full messages. */
function inbox(messages: Record<string, unknown>): Handler {
  return (url, res) => {
    if (url.pathname === '/api/v1/search') return json(res, { messages: Object.keys(messages).map((ID) => ({ ID })) });
    const id = decodeURIComponent(url.pathname.replace('/api/v1/message/', ''));
    if (id in messages) return json(res, messages[id]);
    return json(res, { error: 'not found' }, 404);
  };
}

test.describe('configuration', () => {
  test('nothing configured means unavailable, and asking for mail says so', async () => {
    const client = createMailClient(configFromEnv({}));
    expect(client.available).toBe(false);
    expect(client.source).toBeNull();
    await expect(client.latestMailLink('a@example.org', 'reset-password')).rejects.toThrow(/No e-mail source/);
    await expect(client.messagesTo('a@example.org')).rejects.toThrow(/E2E_MAILPIT_URL is not set/);
  });

  test('Mailpit wins over a log file, and a trailing slash is dropped', () => {
    const config = configFromEnv({ E2E_MAILPIT_URL: 'http://localhost:8025//', E2E_MAIL_LOG_FILE: '/tmp/x.log' });
    expect(config.mailpitUrl).toBe('http://localhost:8025');
    expect(config.logFile).toBe('');
  });

  test('a malformed or non-http Mailpit address is refused', () => {
    expect(() => configFromEnv({ E2E_MAILPIT_URL: 'not a url' })).toThrow(/not a valid URL/);
    expect(() => configFromEnv({ E2E_MAILPIT_URL: 'file:///etc/passwd' })).toThrow(/http\(s\)/);
    expect(() => configFromEnv({ E2E_MAILPIT_URL: 'javascript:alert(1)' })).toThrow(/http\(s\)/);
  });

  test('the log-file fallback is refused in CI', () => {
    expect(() => configFromEnv({ E2E_MAIL_LOG_FILE: '/tmp/x.log', CI: 'true' })).toThrow(/local development only/);
    expect(configFromEnv({ E2E_MAIL_LOG_FILE: '/tmp/x.log' }).logFile).toBe('/tmp/x.log');
    expect(configFromEnv({ E2E_MAILPIT_URL: 'http://localhost:8025', CI: 'true' }).mailpitUrl).toBe('http://localhost:8025');
  });

  test('the retired command variable is ignored, never executed', async () => {
    const config = configFromEnv({ E2E_MAIL_LOG_COMMAND: 'touch /tmp/e2e-should-not-exist' });
    expect(createMailClient(config).available).toBe(false);
  });
});

test.describe('Mailpit source', () => {
  const good = { ID: 'm1', Subject: 'Reset', From: { Address: 'noreply@example.org' }, To: [{ Address: 'Ann@Example.org' }], Username: 'smtp-user', Text: `Open ${LINK}\nthanks` };

  test('finds the link, matching the recipient case-insensitively, and reports SMTP details', async () => {
    await withServer(inbox({ m1: good }), async (base) => {
      const client = createMailClient(quick({ mailpitUrl: base }));
      expect(await client.latestMailLink('ann@example.org', 'reset-password')).toBe(LINK);
      const [message] = await client.messagesTo('ann@example.org');
      expect(message).toMatchObject({ subject: 'Reset', from: 'noreply@example.org', username: 'smtp-user' });
    });
  });

  test('a substring match is not an exact recipient', async () => {
    const other = { ...good, ID: 'm2', To: [{ Address: 'joann@example.org' }] };
    await withServer(inbox({ m2: other }), async (base) => {
      const client = createMailClient(quick({ mailpitUrl: base }));
      expect(await client.messagesTo('ann@example.org')).toEqual([]);
      expect(await client.latestMailLink('ann@example.org', 'reset-password')).toBeNull();
    });
  });

  test('a message with the other kind of link, or none, gives no link', async () => {
    const verify = { ...good, ID: 'v', Text: 'Verify https://app.example/verify-email#token=zzz' };
    const plain = { ...good, ID: 'p', Text: 'Your password was changed.' };
    await withServer(inbox({ v: verify, p: plain }), async (base) => {
      const client = createMailClient(quick({ mailpitUrl: base }));
      expect(await client.latestMailLink('ann@example.org', 'reset-password')).toBeNull();
      expect(await client.latestMailLink('ann@example.org', 'verify-email')).toBe('https://app.example/verify-email#token=zzz');
    });
  });

  test('a token in the query string is not accepted as a link', async () => {
    const bad = { ...good, ID: 'q', Text: 'https://app.example/reset-password?token=abc' };
    await withServer(inbox({ q: bad }), async (base) => {
      expect(await createMailClient(quick({ mailpitUrl: base })).latestMailLink('ann@example.org', 'reset-password')).toBeNull();
    });
  });

  test('malformed messages are skipped or defaulted, not trusted', async () => {
    const messages = { a: { ID: 'a' }, b: { ID: 'b', To: 'not-a-list', Text: LINK }, c: { ...good, ID: 'c', Text: 42, To: [null, { Address: 'ann@example.org' }] } };
    const handler: Handler = (url, res) => {
      if (url.pathname === '/api/v1/search') return json(res, { messages: [{}, { ID: 7 }, { ID: 'a' }, { ID: 'b' }, { ID: 'c' }, null] });
      return json(res, messages[decodeURIComponent(url.pathname.replace('/api/v1/message/', '')) as keyof typeof messages]);
    };
    await withServer(handler, async (base) => {
      const found = await createMailClient(quick({ mailpitUrl: base })).messagesTo('ann@example.org');
      expect(found.map((m) => m.id)).toEqual(['c']);
      expect(found[0]?.text).toBe('');
    });
  });

  test('a null message list is an empty inbox', async () => {
    await withServer((_url, res) => json(res, { messages: null }), async (base) => {
      expect(await createMailClient(quick({ mailpitUrl: base })).messagesTo('ann@example.org')).toEqual([]);
    });
  });

  test('waiting times out with a message that names the recipient and source', async () => {
    await withServer(inbox({}), async (base) => {
      const client = createMailClient(quick({ mailpitUrl: base, timeoutMs: 200 }));
      await expect(client.waitForMailLink('ann@example.org', 'reset-password')).rejects.toThrow(
        /No reset-password e-mail for ann@example.org arrived \(source: mailpit\)/,
      );
      await expect(client.waitForMessage('ann@example.org', () => true)).rejects.toThrow(/No matching e-mail for ann@example.org/);
    });
  });

  test('waiting ignores the previous link and returns a newer one that arrives later', async () => {
    let calls = 0;
    const handler: Handler = (url, res) => {
      if (url.pathname === '/api/v1/search') {
        calls += 1;
        return json(res, { messages: [{ ID: calls > 2 ? 'new' : 'old' }] });
      }
      const id = url.pathname.endsWith('new') ? 'new' : 'old';
      const link = id === 'new' ? 'https://app.example/reset-password#token=NEW' : LINK;
      return json(res, { ...good, ID: id, Text: link });
    };
    await withServer(handler, async (base) => {
      const client = createMailClient(quick({ mailpitUrl: base, timeoutMs: 3_000 }));
      expect(await client.waitForMailLink('ann@example.org', 'reset-password', LINK)).toBe('https://app.example/reset-password#token=NEW');
    });
  });

  test('Mailpit errors are reported, not swallowed', async () => {
    await withServer((_url, res) => json(res, 'oops', 500), async (base) => {
      await expect(createMailClient(quick({ mailpitUrl: base })).messagesTo('a@example.org')).rejects.toThrow(/answered 500/);
    });
    await withServer((_url, res) => json(res, 'this is not json'), async (base) => {
      await expect(createMailClient(quick({ mailpitUrl: base })).messagesTo('a@example.org')).rejects.toThrow(/not JSON/);
    });
    await withServer(() => undefined, async (base) => {
      // never answers: the per-request limit fires
      await expect(createMailClient(quick({ mailpitUrl: base, requestTimeoutMs: 150 })).messagesTo('a@example.org')).rejects.toThrow(/unreachable/);
    });
  });

  test('an unreachable Mailpit is reported', async () => {
    const client = createMailClient(quick({ mailpitUrl: 'http://127.0.0.1:1' }));
    await expect(client.latestMailLink('a@example.org', 'reset-password')).rejects.toThrow(/unreachable/);
  });
});

test.describe('log-file source', () => {
  let dir = '';
  test.beforeAll(() => {
    dir = mkdtempSync(join(tmpdir(), 'e2e-mail-'));
  });
  test.afterAll(() => rmSync(dir, { recursive: true, force: true }));

  const entry = (to: string, link: string): string => `INFO mail\nTo: ${to}\nSubject: x\n\nOpen ${link}\n`;

  test('reads the newest link for the exact recipient, with or without Docker prefixes', () => {
    const file = join(dir, 'api.log');
    const docker = (text: string) => text.split('\n').map((l) => `backend-1  | ${l}`).join('\n');
    writeFileSync(file, docker(entry('ann@example.org', LINK) + entry('bob@example.org', 'https://a/reset-password#token=BOB') + entry('ann@example.org', 'https://a/reset-password#token=NEWER')));
    const client = createMailClient(quick({ logFile: file }));
    expect(client.source).toBe('log');
    return expect(client.latestMailLink('ann@example.org', 'reset-password')).resolves.toBe('https://a/reset-password#token=NEWER');
  });

  test('another recipient, another kind, or no link gives null', async () => {
    const file = join(dir, 'other.log');
    writeFileSync(file, entry('bob@example.org', LINK));
    const client = createMailClient(quick({ logFile: file }));
    expect(await client.latestMailLink('ann@example.org', 'reset-password')).toBeNull();
    expect(await client.latestMailLink('bob@example.org', 'verify-email')).toBeNull();
  });

  test('a missing file, a directory and an oversized file are refused with clear messages', async () => {
    await expect(createMailClient(quick({ logFile: join(dir, 'nope.log') })).latestMailLink('a@example.org', 'reset-password')).rejects.toThrow(/does not exist/);
    const sub = join(dir, 'folder');
    mkdirSync(sub);
    await expect(createMailClient(quick({ logFile: sub })).latestMailLink('a@example.org', 'reset-password')).rejects.toThrow(/not a regular file/);
    const big = join(dir, 'big.log');
    writeFileSync(big, '');
    truncateSync(big, MAX_LOG_BYTES + 1); // sparse: takes no real disk space
    await expect(createMailClient(quick({ logFile: big })).latestMailLink('a@example.org', 'reset-password')).rejects.toThrow(/larger than/);
  });

  test('a path with shell syntax is only ever a file name: nothing is executed', async () => {
    const marker = join(dir, 'executed');
    const hostile = `${join(dir, 'x.log')}; touch ${marker}`;
    await expect(createMailClient(quick({ logFile: hostile })).latestMailLink('a@example.org', 'reset-password')).rejects.toThrow(/does not exist/);
    const { existsSync } = await import('node:fs');
    expect(existsSync(marker)).toBe(false);
  });

  test('waiting on a log with no message times out clearly', async () => {
    const file = join(dir, 'empty.log');
    writeFileSync(file, '');
    chmodSync(file, 0o600);
    await expect(createMailClient(quick({ logFile: file, timeoutMs: 150 })).waitForMailLink('a@example.org', 'reset-password')).rejects.toThrow(/\(source: log\)/);
  });
});
