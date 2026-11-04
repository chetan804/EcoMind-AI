import type { ReactNode } from 'react';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { cx } from '@/utils/cx';
import type { Shot } from '../content';
import { ProductShot } from './ProductShot';

/** One product area: text with a status note on one side, a real screenshot on the other. */
export function FeatureSection({
  id,
  eyebrow,
  title,
  lead,
  points,
  status,
  shot,
  reverse = false,
}: {
  id: string;
  eyebrow: string;
  title: string;
  lead: string;
  points: string[];
  status?: { tone: BadgeTone; label: string; text: ReactNode };
  shot: Shot;
  reverse?: boolean;
}) {
  return (
    <section className={cx('section feature-section', reverse && 'feature-section--reverse')} id={id} aria-labelledby={`${id}-title`}>
      <div className="feature-section__text">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={`${id}-title`} className="section__title">
          {title}
        </h2>
        <p className="section__text">{lead}</p>
        <ul className="ticks">
          {points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
        {status && (
          <p className="status-note">
            <Badge tone={status.tone}>{status.label}</Badge> <span>{status.text}</span>
          </p>
        )}
      </div>
      <ProductShot shot={shot} />
    </section>
  );
}
