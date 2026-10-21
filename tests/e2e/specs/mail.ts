import { execSync } from 'node:child_process';

/**
 * Reads the e-mails the application sends, so a browser test can follow the one-time links in
 * them. Two sources, in this order:
 *
 *  1. Mailpit (preferred; what CI uses). `E2E_MAILPIT_URL`, for example `http://localhost:8025`,
 *     is the address of a Mailpit inbox that the backend delivers to over real SMTP
 *     (`make demo-mail-up`). The messages are read through Mailpit's REST API (`/api/v1/search`,
 *     `/api/v1/message/{ID}`), so the whole path backend -> SMTP (with AUTH) -> inbox is exercised.
 *  2. The backend's console e-mail log (development only), when `E2E_MAIL_LOG_COMMAND` is a shell
 *     command that prints it, for example `cat /tmp/api.log`. This path does not exercise SMTP.
 *
 * Specs that need e-mail are skipped, visibly, when neither is set.
 */
export const mailpitUrl = (process.env.E2E_MAILPIT_URL ?? '').replace(/\/+$/, '');
export const mailLogCommand = process.env.E2E_MAIL_LOG_COMMAND;
export const mailAvailable = Boolean(mailpitUrl || mailLogCommand);
export const mailSource: 'mailpit' | 'log' | null = mailpitUrl ? 'mailpit' : mailLogCommand ? 'log' : null;

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

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const linkPattern = (kind: LinkKind): RegExp => new RegExp(`https?://\\S+/${kind}#token=[A-Za-z0-9_-]+`, 'g');

interface MailpitAddress {
  Address?: string;
}
interface MailpitSummary {
  ID: string;
}
interface MailpitMessage {
  ID: string;
  Subject?: string;
  From?: MailpitAddress | null;
  To?: MailpitAddress[] | null;
  Username?: string;
  Text?: string;
}

async function mailpitGet<T>(path: string): Promise<T> {
  const response = await fetch(`${mailpitUrl}${path}`);
  if (!response.ok) throw new Error(`Mailpit ${path} answered ${response.status}`);
  return (await response.json()) as T;
}

/** Every message addressed to `to`, newest first (Mailpit only). */
export async function messagesTo(to: string): Promise<MailMessage[]> {
  if (!mailpitUrl) throw new Error('E2E_MAILPIT_URL is not set');
  const query = encodeURIComponent(`to:"${to}"`);
  const found = await mailpitGet<{ messages?: MailpitSummary[] }>(`/api/v1/search?query=${query}&limit=50`);
  const messages: MailMessage[] = [];
  for (const summary of found.messages ?? []) {
    const full = await mailpitGet<MailpitMessage>(`/api/v1/message/${encodeURIComponent(summary.ID)}`);
    const recipients = (full.To ?? []).map((a) => (a.Address ?? '').toLowerCase());
    // Mailpit's `to:` filter is a substring match; keep only exact recipients.
    if (!recipients.includes(to.toLowerCase())) continue;
    messages.push({
      id: full.ID,
      subject: full.Subject ?? '',
      from: full.From?.Address ?? '',
      to: recipients,
      username: full.Username ?? '',
      text: full.Text ?? '',
    });
  }
  return messages;
}

function linkFromLog(to: string, kind: LinkKind): string | null {
  if (!mailLogCommand) throw new Error('No e-mail source is configured');
  const raw = execSync(mailLogCommand, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
  // Docker prefixes every line ("backend-1  | "); drop prefixes so a message reads as plain lines.
  const text = raw
    .split('\n')
    .map((line) => line.replace(/^[^|]*\|\s?/, '').trimEnd())
    .join('\n');
  const pattern = new RegExp(`To: ${escapeRegExp(to)}\\n[\\s\\S]*?(https?://\\S+/${kind}#token=[A-Za-z0-9_-]+)`, 'g');
  let last: string | null = null;
  for (const match of text.matchAll(pattern)) last = match[1] ?? null;
  return last;
}

/** The newest link of `kind` mailed to `to`, or null when none has arrived. */
export async function latestMailLink(to: string, kind: LinkKind): Promise<string | null> {
  if (mailSource === 'mailpit') {
    for (const message of await messagesTo(to)) {
      const links = message.text.match(linkPattern(kind));
      if (links && links.length > 0) return links[links.length - 1] ?? null;
    }
    return null;
  }
  return linkFromLog(to, kind);
}

/** Poll briefly: the message is sent after the HTTP response. */
export async function waitForMailLink(to: string, kind: LinkKind, previous: string | null = null): Promise<string> {
  const deadline = Date.now() + 20_000;
  for (;;) {
    const link = await latestMailLink(to, kind);
    if (link && link !== previous) return link;
    if (Date.now() > deadline) throw new Error(`No ${kind} e-mail for ${to} arrived (source: ${mailSource})`);
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
}

/** Poll until `predicate` finds a message to `to` (Mailpit only); returns it. */
export async function waitForMessage(to: string, predicate: (m: MailMessage) => boolean): Promise<MailMessage> {
  const deadline = Date.now() + 20_000;
  for (;;) {
    const hit = (await messagesTo(to)).find(predicate);
    if (hit) return hit;
    if (Date.now() > deadline) throw new Error(`No matching e-mail for ${to} arrived in Mailpit`);
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
}
