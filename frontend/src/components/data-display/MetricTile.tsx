import type { ReactNode } from 'react';
import './data-display.css';

export type MetricTone = 'teal' | 'blue' | 'red' | 'amber';

/** One headline number with its label. `value` is a string so the caller controls units/format. */
export function MetricTile({
  icon,
  tone = 'teal',
  label,
  value,
  note,
}: {
  icon: ReactNode;
  tone?: MetricTone;
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="metric">
      <span className={`metric__icon metric__icon--${tone}`} aria-hidden="true">
        {icon}
      </span>
      <div className="metric__body">
        <span className="metric__value">{value}</span>
        <span className="metric__label">{label}</span>
        {note && <span className="metric__note">{note}</span>}
      </div>
    </div>
  );
}
