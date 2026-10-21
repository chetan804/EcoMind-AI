import { TrendChart } from '@/components/data-display/TrendChart';
import { formatDate } from '@/utils/format';
import type { WeeklyTrend } from '../api/schemas';

/** Weekly collected weight from `collected` field events. Zero weeks are real zeros. */
export function CollectedWeightChart({ trend, height = 220 }: { trend: WeeklyTrend; height?: number }) {
  return (
    <TrendChart
      height={height}
      unit="kg"
      ariaLabel="Weekly collected weight"
      emptyMessage="No weight has been recorded in this period."
      xLabels={trend.points.map((p) => formatDate(p.week_start).replace(/ \d{4}$/, ''))}
      series={[
        {
          id: 'collected',
          label: 'Collected weight',
          color: 'var(--color-accent-text)',
          area: true,
          values: trend.points.map((p) => p.collected_weight_kg),
        },
      ]}
    />
  );
}
