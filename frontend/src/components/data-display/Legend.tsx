import { cx } from '@/utils/cx';
import './data-display.css';

export interface LegendEntry {
  label: string;
  color: string;
}

export function Legend({ items, variant = 'bars' }: { items: LegendEntry[]; variant?: 'bars' | 'dots' }) {
  return (
    <ul className={cx('legend', variant === 'dots' && 'legend--dots')}>
      {items.map((item) => (
        <li key={item.label} className="legend__item">
          <span className="legend__swatch" style={{ background: item.color }} aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
