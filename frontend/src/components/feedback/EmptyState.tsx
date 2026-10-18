import type { ReactNode } from 'react';
import './feedback.css';

/** Honest empty/unavailable state: say what is missing and what the user can do about it. */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      {icon && (
        <span className="empty__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <h2 className="empty__title">{title}</h2>
      {description && <p className="empty__text">{description}</p>}
      {action}
    </div>
  );
}
