import { Badge } from '@/components/ui/Badge';
import type { TrackingStatus } from '../api/tracking-api';
import { STATUS_LABEL, STATUS_TONE } from '../labels';

export function VehicleStatusBadge({ status }: { status: TrackingStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]} dot>
      {STATUS_LABEL[status]}
    </Badge>
  );
}
