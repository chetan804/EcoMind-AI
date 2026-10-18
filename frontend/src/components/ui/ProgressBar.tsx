import { cx } from '@/utils/cx';
import './display.css';

/** Determinate progress. `label` names what is progressing; the numeric value is exposed to AT. */
export function ProgressBar({
  value,
  max = 100,
  label,
  tone,
}: {
  value: number;
  max?: number;
  label: string;
  tone?: 'warning' | 'danger';
}) {
  const clamped = Math.min(Math.max(value, 0), max);
  return (
    <div className="progress">
      <div
        className="progress__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={clamped}
      >
        <div className={cx('progress__fill', tone && `progress__fill--${tone}`)} style={{ width: `${(clamped / max) * 100}%` }} />
      </div>
    </div>
  );
}
