import type { BadgeTone } from '@/components/ui/Badge';
import { StatusBadge } from '@/components/ui/StatusBadge';

const TONES: Record<string, BadgeTone> = { submitted: 'info', under_review: 'warning', verified: 'success', rejected: 'danger', closed: 'neutral' };
export const ReportStatusBadge = ({ value }: { value: string }) => <StatusBadge value={value} tones={TONES} />;
