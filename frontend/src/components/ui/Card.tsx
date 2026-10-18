import type { ComponentProps, ReactNode } from 'react';
import { cx } from '@/utils/cx';
import './card.css';

/** Surface container. Give it an accessible name with `aria-labelledby` pointing at its title. */
export function Card({
  flush,
  className,
  ...rest
}: ComponentProps<'section'> & { flush?: boolean }) {
  return <section {...rest} className={cx('card', flush && 'card--flush', className)} />;
}

export function CardHeader({
  title,
  titleId,
  actions,
}: {
  title: ReactNode;
  titleId?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="card__header">
      <h2 id={titleId} className="card__title">
        {title}
      </h2>
      {actions}
    </header>
  );
}
