import type { ReactNode } from 'react';
import './layout.css';

/** Page title block: h1, optional subtitle and meta row (badges, notices), plus right-aligned actions. */
export function PageHeader({
  title,
  subtitle,
  meta,
  actions,
  titleId,
}: {
  title: string;
  subtitle?: string;
  meta?: ReactNode;
  actions?: ReactNode;
  titleId?: string;
}) {
  return (
    <header className="page-header">
      <div>
        <h1 id={titleId} className="page-header__title">
          {title}
        </h1>
        {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
        {meta && <div className="page-header__meta">{meta}</div>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}
