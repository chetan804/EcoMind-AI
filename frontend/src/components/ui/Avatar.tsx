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
    <span className="avatar" aria-hidden="true">
      {initials || <UserRound size={20} />}
    </span>
  );
}
