import type { ComponentProps, ReactNode } from 'react';
import { Button } from './Button';
import './display.css';

/**
 * Styled semantic table. Give it a `caption` (visible or via `captionHidden`), use <th scope>,
 * and put sorting/filtering state in the owning feature, not here.
 */
export function Table({
  caption,
  captionHidden,
  children,
  ...rest
}: Omit<ComponentProps<'table'>, 'children'> & { caption: string; captionHidden?: boolean; children: ReactNode }) {
  return (
    <div className="table-scroll">
      <table {...rest} className="table">
        <caption className={captionHidden ? 'visually-hidden' : undefined}>{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export function Pagination({
  page,
  pageCount,
  onPageChange,
  summary,
}: {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  summary?: string;
}) {
  return (
    <nav className="pagination" aria-label="Pagination">
      <span aria-live="polite">{summary ?? `Page ${page} of ${pageCount}`}</span>
      <div className="pagination__controls">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <Button variant="secondary" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}
