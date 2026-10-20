import type { ReactNode } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { getErrorMessage } from '@/services/error-handler';
import { Button } from '@/components/ui/Button';
import { Alert } from './Alert';
import { Skeleton } from './Loading';

/**
 * Renders the three honest states of a request: loading, failed (with the reason and a retry),
 * and the data. Nothing is shown as if it were data until the server has answered.
 */
export function QueryBoundary<T>({
  query,
  label = 'data',
  children,
}: {
  query: UseQueryResult<T>;
  label?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) {
    return (
      <div role="status" aria-label={`Loading ${label}`} className="query-loading">
        <Skeleton height={20} width="40%" />
        <Skeleton height={120} />
      </div>
    );
  }
  if (query.isError) {
    return (
      <Alert tone="danger" title={`Could not load ${label}`}>
        <p>{getErrorMessage(query.error)}</p>
        <Button variant="secondary" onClick={() => void query.refetch()}>
          Try again
        </Button>
      </Alert>
    );
  }
  return <>{children(query.data)}</>;
}
