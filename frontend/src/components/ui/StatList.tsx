import type { Count } from '@/services/schemas';
import { humanize } from '@/utils/format';

/** Label and number rows for breakdowns (status counts and the like). Zero rows stay visible. */
export function CountList({ items, label }: { items: Count[]; label: string }) {
  return (
    <ul className="count-list" aria-label={label}>
      {items.map((item) => (
        <li key={item.key} className="count-list__row">
          <span>{humanize(item.key)}</span>
          <strong>{item.count}</strong>
        </li>
      ))}
    </ul>
  );
}
