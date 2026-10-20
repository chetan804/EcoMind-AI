import { cx } from '@/utils/cx';
import './feedback.css';

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return <span className="spinner" role="status" aria-label={label} />;
}

/** Placeholder block for content that is loading. Decorative: pair with a live region or Spinner. */
export function Skeleton({ width, height = 16, className }: { width?: number | string; height?: number | string; className?: string }) {
  return <span aria-hidden="true" className={cx('skeleton', className)} style={{ width, height }} />;
}

/** Full-area loading state, shown while a route's code is first fetched. */
export function PageLoading() {
  return (
    <div className="page-loading">
      <Spinner label="Loading page" />
    </div>
  );
}
