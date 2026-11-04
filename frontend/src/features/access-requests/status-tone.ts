import type { BadgeTone } from '@/components/ui/Badge';
import type { RequestStatus } from './api/access-requests-api';

export const STATUS_TONE: Record<RequestStatus, BadgeTone> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  withdrawn: 'neutral',
};
