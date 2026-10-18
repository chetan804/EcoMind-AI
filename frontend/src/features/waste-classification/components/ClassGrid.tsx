import { Apple, Container, Cylinder, Newspaper, Smartphone, Wine, type LucideIcon } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui/Card';
import { plannedClasses } from '../fixtures/sample-layout';

const icons: Record<(typeof plannedClasses)[number]['id'], { icon: LucideIcon; tone: string }> = {
  plastic: { icon: Container, tone: 'var(--color-info)' },
  paper: { icon: Newspaper, tone: 'var(--color-text-secondary)' },
  glass: { icon: Wine, tone: 'var(--color-teal)' },
  metal: { icon: Cylinder, tone: 'var(--color-warning)' },
  organic: { icon: Apple, tone: 'var(--color-success)' },
  'e-waste': { icon: Smartphone, tone: 'var(--color-danger)' },
};

/** The label set the classifier is planned to use. Says so, because no model supports it yet. */
export function ClassGrid() {
  return (
    <Card aria-labelledby="classes-title" className="classes">
      <CardHeader title="Planned waste classes" titleId="classes-title" />
      <ul className="classes__grid">
        {plannedClasses.map((item) => {
          const { icon: Icon, tone } = icons[item.id];
          return (
            <li key={item.id} className="classes__item">
              <span className="classes__icon" style={{ color: tone }} aria-hidden="true">
                <Icon size={28} />
              </span>
              {item.label}
            </li>
          );
        })}
      </ul>
      <p className="classes__note">Label set for the planned classifier. No model has been trained yet.</p>
    </Card>
  );
}
