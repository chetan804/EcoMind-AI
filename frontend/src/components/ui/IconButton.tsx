import type { ComponentProps, ReactNode } from 'react';
import { Link } from 'react-router';
import { cx } from '@/utils/cx';
import './button.css';

/** Icon-only button. `label` is required: it is the accessible name and the native tooltip. */
export function IconButton({
  label,
  icon,
  outlined,
  className,
  type = 'button',
  ...rest
}: Omit<ComponentProps<'button'>, 'children' | 'aria-label'> & {
  label: string;
  icon: ReactNode;
  outlined?: boolean;
}) {
  return (
    <button
      {...rest}
      type={type}
      aria-label={label}
      title={label}
      className={cx('icon-btn', outlined && 'icon-btn--outlined', className)}
    >
      {icon}
    </button>
  );
}

/** Icon-only link that looks like an IconButton. Same naming rule: `label` is required. */
export function IconLink({ label, icon, to }: { label: string; icon: ReactNode; to: string }) {
  return (
    <Link to={to} aria-label={label} title={label} className="icon-btn">
      {icon}
    </Link>
  );
}
