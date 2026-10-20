import { humanize } from '@/utils/format';
import { Badge, type BadgeTone } from './Badge';

/** A status code shown as readable text, with the tone chosen by the feature's own mapping. */
export function StatusBadge({ value, tones }: { value: string; tones: Record<string, BadgeTone> }) {
  return <Badge tone={tones[value] ?? 'neutral'}>{humanize(value)}</Badge>;
}
