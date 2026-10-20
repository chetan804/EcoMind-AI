import { Box, Container, Cylinder, Newspaper, Trash2, Wine, type LucideIcon } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui/Card';

/** The six material categories model 1.0.0 was trained on (see docs/ml/model-cards/waste-classification-1.0.0.md). */
const CATEGORIES: { id: string; label: string; icon: LucideIcon; tone: string }[] = [
  { id: 'plastic', label: 'Plastic', icon: Container, tone: 'var(--color-info)' },
  { id: 'paper', label: 'Paper', icon: Newspaper, tone: 'var(--color-text-secondary)' },
  { id: 'cardboard', label: 'Cardboard', icon: Box, tone: 'var(--color-warning)' },
  { id: 'glass', label: 'Glass', icon: Wine, tone: 'var(--color-teal)' },
  { id: 'metal', label: 'Metal', icon: Cylinder, tone: 'var(--color-primary)' },
  { id: 'trash', label: 'Other waste', icon: Trash2, tone: 'var(--color-danger)' },
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
        The model predicts these six material categories only. It does not recognise organic waste, e-waste or hazardous
        items; such images should be flagged for review.
      </p>
    </Card>
  );
}
