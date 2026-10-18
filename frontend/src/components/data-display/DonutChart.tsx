import type { ReactNode } from 'react';
import './data-display.css';

export interface DonutSegment {
  label: string;
  /** Share in percent. Segments should add up to 100. */
  value: number;
  color: string;
}

/** Share-of-total chart. The legend carries every label and value, so the ring is decorative. */
export function DonutChart({
  segments,
  center,
  ariaLabel,
  size = 148,
}: {
  segments: DonutSegment[];
  center?: ReactNode;
  ariaLabel: string;
  size?: number;
}) {
  const stroke = Math.round(size * 0.16);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const lengths = segments.map((segment) => (segment.value / 100) * circumference);
  const offsets = lengths.map((_, index) => lengths.slice(0, index).reduce((sum, length) => sum + length, 0));

  return (
    <div className="donut">
      <div className="donut__figure" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-surface-raised)" strokeWidth={stroke} />
          {segments.map((segment, index) => (
            <circle
              key={segment.label}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={stroke}
              strokeDasharray={`${lengths[index]} ${circumference - (lengths[index] ?? 0)}`}
              strokeDashoffset={-(offsets[index] ?? 0)}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          ))}
        </svg>
        {center && <div className="donut__center">{center}</div>}
      </div>
      <ul className="donut__legend" aria-label={ariaLabel}>
        {segments.map((segment) => (
          <li key={segment.label}>
            <span className="legend__swatch" style={{ background: segment.color, width: 10, height: 10, borderRadius: '50%' }} aria-hidden="true" />
            {segment.label}
            <span className="value">{segment.value}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
