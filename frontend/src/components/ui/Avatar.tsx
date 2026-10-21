import { UserRound } from 'lucide-react';
import './display.css';

/** Initials avatar; falls back to a generic person glyph when there is no name (decorative). */
export function Avatar({ name }: { name?: string }) {
  const initials = name
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('');
  return (
    // The initials are drawn by CSS (::before) rather than written into the DOM, so they are not
    // counted as visible label text of a button that also shows the full name (WCAG 2.5.3).
    <span className="avatar" aria-hidden="true" data-initials={initials || undefined}>
      {!initials && <UserRound size={20} />}
    </span>
  );
}
