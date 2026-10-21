import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Reads the e-mails the application sends, so a browser test can follow the one-time links in
 * them. Nothing here starts a process or builds a command from configuration. Two sources:
 *
 *  1. Mailpit (preferred; what CI uses). `E2E_MAILPIT_URL`, for example `http://localhost:8025`,
 *     is the address of a Mailpit inbox that the backend delivers to over real SMTP
 *     (`make demo-mail-up`). The messages are read through Mailpit's REST API (`/api/v1/search`,
 *     `/api/v1/message/{ID}`), so the whole path backend -> SMTP (with AUTH) -> inbox is exercised.
 *  2. The backend's console e-mail log (local development only), when `E2E_MAIL_LOG_FILE` is the
 *     path of a file that holds it, for example the file the dev server's output is redirected to
 *     (`... > /tmp/api.log`) or a saved `docker compose logs --no-color backend`. The file is read
 *     directly; it must be a regular file of at most 64 MiB. This path does not exercise SMTP and is
 *     refused when `CI` is set, so a pipeline cannot silently fall back to it.
 *
 * Specs that need e-mail are skipped, visibly, when neither is set.
 */

export type LinkKind = 'reset-password' | 'verify-email';

export interface MailMessage {
  id: string;
  subject: string;
  from: string;
  to: string[];
  /** The SMTP user name the sender authenticated with (Mailpit reports it; empty when none). */
  username: string;
  text: string;
}

export interface MailConfig {
  mailpitUrl: string;
  logFile: string;
  /** How long to wait for a message to arrive. */
  timeoutMs: number;
  pollMs: number;
  /** Per-request limit for Mailpit. */
  requestTimeoutMs: number;
}

export const MAX_LOG_BYTES = 64 * 1024 * 1024;

/** Build the configuration from environment variables; throws a clear error when it is unsafe or malformed. */
export function configFromEnv(env: Record<string, string | undefined>): MailConfig {
  const rawUrl = (env.E2E_MAILPIT_URL ?? '').trim();
  const logFile = (env.E2E_MAIL_LOG_FILE ?? '').trim();
  let mailpitUrl = '';
  if (rawUrl) {
    let parsed: URL;
    try {
      parsed = new URL(rawUrl);
    } catch {
      throw new Error(`E2E_MAILPIT_URL is not a valid URL: ${rawUrl}`);
    }
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error(`E2E_MAILPIT_URL must be an http(s) URL, got ${parsed.protocol}`);
    }
    mailpitUrl = rawUrl.replace(/\/+$/, '');
  }
  if (!mailpitUrl && logFile && env.CI) {
    throw new Error('E2E_MAIL_LOG_FILE is for local development only; CI must set E2E_MAILPIT_URL');
  }
  return { mailpitUrl, logFile: mailpitUrl ? '' : logFile, timeoutMs: 20_000, pollMs: 300, requestTimeoutMs: 5_000 };
}

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const linkPattern = (kind: LinkKind): RegExp => new RegExp(`https?://\\S+/${kind}#token=[A-Za-z0-9_-]+`, 'g');

interface MailpitAddress {
  Address?: string;
}
interface MailpitSummary {
  ID?: string;
}
interface MailpitMessage {
  ID?: string;
  Subject?: string;
  From?: MailpitAddress | null;
  To?: MailpitAddress[] | null;
  Username?: string;
  Text?: string;
}

export function createMailClient(config: MailConfig) {
  const source: 'mailpit' | 'log' | null = config.mailpitUrl ? 'mailpit' : config.logFile ? 'log' : null;

  async function mailpitGet<T>(path: string): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${config.mailpitUrl}${path}`, { signal: AbortSignal.timeout(config.requestTimeoutMs) });
    } catch (error) {
      throw new Error(`Mailpit ${path} is unreachable: ${error instanceof Error ? error.message : String(error)}`);
    }
    if (!response.ok) throw new Error(`Mailpit ${path} answered ${response.status}`);
    try {
      return (await response.json()) as T;
    } catch {
      throw new Error(`Mailpit ${path} returned a body that is not JSON`);
    }
  }

  /** Every message addressed exactly to `to`, newest first (Mailpit only). */
  async function messagesTo(to: string): Promise<MailMessage[]> {
    if (source !== 'mailpit') throw new Error('E2E_MAILPIT_URL is not set');
    const query = encodeURIComponent(`to:"${to}"`);
    const found = await mailpitGet<{ messages?: MailpitSummary[] | null }>(`/api/v1/search?query=${query}&limit=50`);
    const messages: MailMessage[] = [];
    for (const summary of found.messages ?? []) {
      if (!summary || typeof summary.ID !== 'string' || !summary.ID) continue;
      const full = await mailpitGet<MailpitMessage>(`/api/v1/message/${encodeURIComponent(summary.ID)}`);
      const recipients = (Array.isArray(full.To) ? full.To : []).map((a) => (a?.Address ?? '').toLowerCase());
      // Mailpit's `to:` filter is a substring match; keep only exact recipients.
      if (!recipients.includes(to.toLowerCase())) continue;
      messages.push({
        id: full.ID ?? summary.ID,
        subject: full.Subject ?? '',
        from: full.From?.Address ?? '',
        to: recipients,
        username: full.Username ?? '',
        text: typeof full.Text === 'string' ? full.Text : '',
      });
    }
    return messages;
  }

  function readLog(): string {
    const path = resolve(config.logFile);
    let info;
    try {
      info = statSync(path);
    } catch {
      throw new Error(`E2E_MAIL_LOG_FILE does not exist: ${path}`);
    }
    if (!info.isFile()) throw new Error(`E2E_MAIL_LOG_FILE is not a regular file: ${path}`);
    if (info.size > MAX_LOG_BYTES) throw new Error(`E2E_MAIL_LOG_FILE is larger than ${MAX_LOG_BYTES} bytes: ${path}`);
    return readFileSync(path, 'utf8');
  }

  function linkFromLog(to: string, kind: LinkKind): string | null {
    // Docker prefixes every line ("backend-1  | "); drop prefixes so a message reads as plain lines.
    const text = readLog()
      .split('\n')
      .map((line) => line.replace(/^[^|]*\|\s?/, '').trimEnd())
      .join('\n');
    const pattern = new RegExp(`To: ${escapeRegExp(to)}\\n[\\s\\S]*?(https?://\\S+/${kind}#token=[A-Za-z0-9_-]+)`, 'g');
    let last: string | null = null;
    for (const match of text.matchAll(pattern)) last = match[1] ?? null;
    return last;
  }

  /** The newest link of `kind` mailed to `to`, or null when none has arrived. */
  async function latestMailLink(to: string, kind: LinkKind): Promise<string | null> {
    if (source === 'mailpit') {
      for (const message of await messagesTo(to)) {
        const links = message.text.match(linkPattern(kind));
        if (links && links.length > 0) return links[links.length - 1] ?? null;
      }
      return null;
    }
    if (source === 'log') return linkFromLog(to, kind);
    throw new Error('No e-mail source is configured (set E2E_MAILPIT_URL)');
  }

  const sleep = (ms: number) => new Promise((done) => setTimeout(done, ms));

  /** Poll briefly: the message is sent after the HTTP response. */
  async function waitForMailLink(to: string, kind: LinkKind, previous: string | null = null): Promise<string> {
    const deadline = Date.now() + config.timeoutMs;
    for (;;) {
      const link = await latestMailLink(to, kind);
      if (link && link !== previous) return link;
      if (Date.now() > deadline) throw new Error(`No ${kind} e-mail for ${to} arrived (source: ${source})`);
      await sleep(config.pollMs);
    }
  }

  /** Poll until `predicate` finds a message to `to` (Mailpit only); returns it. */
  async function waitForMessage(to: string, predicate: (m: MailMessage) => boolean): Promise<MailMessage> {
    const deadline = Date.now() + config.timeoutMs;
    for (;;) {
      const hit = (await messagesTo(to)).find(predicate);
      if (hit) return hit;
      if (Date.now() > deadline) throw new Error(`No matching e-mail for ${to} arrived in Mailpit`);
      await sleep(config.pollMs);
    }
  }

  return { source, available: source !== null, messagesTo, latestMailLink, waitForMailLink, waitForMessage };
}

const client = createMailClient(configFromEnv(process.env));
export const mailSource = client.source;
export const mailAvailable = client.available;
export const { messagesTo, latestMailLink, waitForMailLink, waitForMessage } = client;
