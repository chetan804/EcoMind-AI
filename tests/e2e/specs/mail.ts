import { execSync } from 'node:child_process';

/**
 * Reads the one-time links the backend's console e-mail backend (development only) writes to its
 * log. `E2E_MAIL_LOG_COMMAND` is a shell command that prints that log, for example
 * `docker compose logs --no-color backend` (CI) or `cat /tmp/api.log` (local). Specs that need it
 * are skipped, visibly, when it is not set.
 */
export const mailLogCommand = process.env.E2E_MAIL_LOG_COMMAND;

function readLog(): string {
  if (!mailLogCommand) throw new Error('E2E_MAIL_LOG_COMMAND is not set');
  return execSync(mailLogCommand, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
}

/** The newest link of `kind` (`reset-password` or `verify-email`) mailed to `to`, or null. */
export function latestMailLink(to: string, kind: 'reset-password' | 'verify-email'): string | null {
  // Docker prefixes every line ("backend-1  | "); drop prefixes so a message reads as plain lines.
  const lines = readLog()
    .split('\n')
    .map((line) => line.replace(/^[^|]*\|\s?/, '').trimEnd());
  const text = lines.join('\n');
  const pattern = new RegExp(`To: ${to.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\n[\\s\\S]*?(https?://\\S+/${kind}#token=[A-Za-z0-9_-]+)`, 'g');
  let last: string | null = null;
  for (const match of text.matchAll(pattern)) last = match[1] ?? null;
  return last;
}

/** Poll briefly: the message is sent after the HTTP response. */
export async function waitForMailLink(to: string, kind: 'reset-password' | 'verify-email', previous: string | null = null): Promise<string> {
  const deadline = Date.now() + 15_000;
  for (;;) {
    const link = latestMailLink(to, kind);
    if (link && link !== previous) return link;
    if (Date.now() > deadline) throw new Error(`No ${kind} e-mail for ${to} appeared in the backend log`);
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
}
