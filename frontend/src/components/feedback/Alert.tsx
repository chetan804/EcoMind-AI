import type { ReactNode } from 'react';
import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react';
import { cx } from '@/utils/cx';
import './feedback.css';

export type AlertTone = 'info' | 'success' | 'warning' | 'danger';

const icons = { info: Info, success: CircleCheck, warning: TriangleAlert, danger: CircleAlert } as const;

/** Inline message. `danger` is announced assertively (role="alert"); others politely (role="status"). */
export function Alert({
  tone = 'info',
  title,
  children,
  className,
}: {
  tone?: AlertTone;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  const Icon = icons[tone];
  return (
    <div className={cx('alert', `alert--${tone}`, className)} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon size={20} aria-hidden="true" />
      <div className="alert__body">
        {title && <p className="alert__title">{title}</p>}
        {children && <div className="alert__text">{children}</div>}
      </div>
    </div>
  );
}
