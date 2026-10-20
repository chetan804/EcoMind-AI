import { StatusBadge } from '@/components/ui/StatusBadge';
import type { BadgeTone } from '@/components/ui/Badge';

const STATUS: Record<string, BadgeTone> = {
  pending: 'warning',
  assigned: 'info',
  in_progress: 'info',
  completed: 'success',
  failed: 'danger',
  cancelled: 'neutral',
};
const PRIORITY: Record<string, BadgeTone> = { low: 'neutral', normal: 'info', high: 'warning', urgent: 'danger' };

export const TaskStatusBadge = ({ value }: { value: string }) => <StatusBadge value={value} tones={STATUS} />;
export const PriorityBadge = ({ value }: { value: string }) => <StatusBadge value={value} tones={PRIORITY} />;
