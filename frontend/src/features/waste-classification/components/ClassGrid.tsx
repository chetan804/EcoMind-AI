import { Box, Container, Cylinder, Newspaper, Wine, type LucideIcon } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui/Card';

/** The five material categories the current research model is trained on (docs/ml/model-cards/). */
const CATEGORIES: { id: string; label: string; icon: LucideIcon; tone: string }[] = [
  { id: 'plastic', label: 'Plastic', icon: Container, tone: 'var(--color-info)' },
  { id: 'paper', label: 'Paper', icon: Newspaper, tone: 'var(--color-text-secondary)' },
  { id: 'cardboard', label: 'Cardboard', icon: Box, tone: 'var(--color-warning)' },
  { id: 'glass', label: 'Glass', icon: Wine, tone: 'var(--color-accent-text)' },
  { id: 'metal', label: 'Metal', icon: Cylinder, tone: 'var(--color-primary)' },
];

export function ClassGrid() {
  return (
    <Card aria-labelledby="classes-title" className="classes">
      <CardHeader title="Material categories" titleId="classes-title" />
      <ul className="classes__grid">
        {CATEGORIES.map(({ id, label, icon: Icon, tone }) => (
          <li key={id} className="classes__item">
            <span className="classes__icon" style={{ color: tone }} aria-hidden="true">
              <Icon size={28} />
            </span>
            {label}
          </li>
        ))}
      </ul>
      <p className="classes__note">
        The model predicts these five material categories only. It does not recognise miscellaneous waste, organic or
        textile waste, e-waste or hazardous items; such images should be flagged for review.
      </p>
    </Card>
  );
}
