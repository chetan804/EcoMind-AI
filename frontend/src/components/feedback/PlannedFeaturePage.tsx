import { useLocation } from 'react-router';
import { Hammer } from 'lucide-react';
import { findNavItem } from '@/components/navigation/nav-items';
import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from './EmptyState';
import { ButtonLink } from '@/components/ui/Button';

/** Destination for navigation entries whose feature is not built yet. States that plainly. */
export function PlannedFeaturePage() {
  const { pathname } = useLocation();
  const item = findNavItem(pathname);
  const name = item?.label ?? 'This area';
  return (
    <>
      <PageHeader title={name} />
      <EmptyState
        icon={<Hammer size={24} />}
        title={`${name} is not built yet`}
        description={`This area is planned but has no implementation in this build. See the project roadmap (docs/project-roadmap.md) for when it is scheduled.`}
        action={
          <ButtonLink to="/dashboard" variant="secondary">
            Back to dashboard
          </ButtonLink>
        }
      />
    </>
  );
}
