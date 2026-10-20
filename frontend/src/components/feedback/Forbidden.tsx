import { ShieldAlert } from 'lucide-react';
import { ButtonLink } from '@/components/ui/Button';
import { EmptyState } from './EmptyState';

/** Shown when the signed-in user lacks a permission. The server enforces this independently. */
export function Forbidden() {
  return (
    <EmptyState
      icon={<ShieldAlert size={24} />}
      title="You do not have access to this page"
      description="Your account's role does not include this area. If you think this is a mistake, ask an administrator to review your role."
      action={
        <ButtonLink to="/dashboard" variant="secondary">
          Back to dashboard
        </ButtonLink>
      }
    />
  );
}
