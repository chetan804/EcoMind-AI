import type { ReactNode } from 'react';
import './badge.css';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

/** Status label. Colour is never the only signal: always pass meaningful text as children. */
export function Badge({
  tone = 'neutral',
  dot = false,
  children,
}: {
  tone?: BadgeTone;
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={`badge badge--${tone}`}>
      {dot && <span className="badge__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}
