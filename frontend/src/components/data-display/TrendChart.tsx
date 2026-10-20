import { useId } from 'react';
import { useElementWidth } from '@/hooks/useElementWidth';
import { Legend } from './Legend';
import './data-display.css';

export interface TrendSeries {
  id: string;
  label: string;
  /** CSS color (use a token, e.g. 'var(--color-teal)'). */
  color: string;
  values: Array<number | null>;
  /** Fill the area under the line. */
  area?: boolean;
  dashed?: boolean;
}

const DEFAULT_HEIGHT = 240;
const PAD = { top: 12, right: 12, bottom: 28, left: 52 };

/**
 * Line/area chart drawn in SVG at the container's real pixel width (no distortion).
 * Always supply `unit` (axis + data table) and `ariaLabel`; `emptyMessage` shows when no series
 * has data. A visually hidden table exposes the same numbers to assistive technology.
 */
export function TrendChart({
  series,
  xLabels,
  unit,
  yMax,
  yTicks = 4,
  height: HEIGHT = DEFAULT_HEIGHT,
  ariaLabel,
  emptyMessage = 'No data to display.',
}: {
  series: TrendSeries[];
  xLabels: string[];
  unit: string;
  yMax?: number;
  yTicks?: number;
  height?: number;
  ariaLabel: string;
  emptyMessage?: string;
}) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const titleId = useId();
  const hasData = series.some((s) => s.values.some((v) => v !== null));

  if (!hasData) {
    return (
      <div className="chart">
        <p className="chart__empty">{emptyMessage}</p>
      </div>
    );
  }

  const max = yMax ?? niceMax(Math.max(...series.flatMap((s) => s.values.filter((v): v is number => v !== null))));
  const innerW = Math.max(width - PAD.left - PAD.right, 1);
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const count = Math.max(xLabels.length, 2);
  const x = (i: number) => PAD.left + (i / (count - 1)) * innerW;
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => (max / yTicks) * i);

  return (
    <div className="chart" ref={ref}>
      <Legend items={series.map((s) => ({ label: s.label, color: s.color }))} />
      <svg className="chart__svg" width={width} height={HEIGHT} viewBox={`0 0 ${width} ${HEIGHT}`} role="img" aria-labelledby={titleId}>
        <title id={titleId}>{`${ariaLabel} (${unit})`}</title>
        <defs>
          {series.map((s) => (
            <linearGradient key={s.id} id={`${titleId}-area-${s.id}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor={s.color} stopOpacity={0.32} />
              <stop offset="1" stopColor={s.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="chart__grid" x1={PAD.left} x2={width - PAD.right} y1={y(tick)} y2={y(tick)} />
            <text x={PAD.left - 8} y={y(tick) + 4} textAnchor="end">
              {formatTick(tick)}
            </text>
          </g>
        ))}
        {xLabels.map((label, i) => (
          <text key={`${label}-${i}`} x={x(i)} y={HEIGHT - 8} textAnchor={i === 0 ? 'start' : i === xLabels.length - 1 ? 'end' : 'middle'}>
            {label}
          </text>
        ))}
        {series.map((s) => {
          const points = s.values.flatMap((v, i) => (v === null ? [] : [[x(i), y(v)] as const]));
          if (points.length === 0) return null;
          const line = points.map(([px, py], i) => `${i === 0 ? 'M' : 'L'}${px.toFixed(1)} ${py.toFixed(1)}`).join(' ');
          const first = points[0];
          const last = points[points.length - 1];
          return (
            <g key={s.id}>
              {s.area && first && last && (
                <path d={`${line} L${last[0].toFixed(1)} ${y(0)} L${first[0].toFixed(1)} ${y(0)} Z`} fill={`url(#${titleId}-area-${s.id})`} />
              )}
              <path d={line} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={s.dashed ? '5 4' : undefined} />
              {points.map(([px, py], i) => (
                <circle key={i} cx={px} cy={py} r={3} fill={s.color} />
              ))}
            </g>
          );
        })}
      </svg>
      {/* A wrapper clips the data table; a <table> ignores width/overflow on itself. */}
      <div className="visually-hidden">
        <table>
          <caption>{`${ariaLabel} (${unit})`}</caption>
          <thead>
            <tr>
              <th scope="col">Period</th>
              {series.map((s) => (
                <th key={s.id} scope="col">{s.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {xLabels.map((label, i) => (
              <tr key={`${label}-${i}`}>
                <th scope="row">{label}</th>
                {series.map((s) => (
                  <td key={s.id}>{s.values[i] ?? 'no data'}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / magnitude) * magnitude;
}

function formatTick(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(value % 1000 ? 1 : 0)}k` : String(Math.round(value));
}
