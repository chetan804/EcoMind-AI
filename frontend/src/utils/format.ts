const NUMBER = new Intl.NumberFormat('en', { maximumFractionDigits: 1 });
const DATE_TIME = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
const DATE = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' });
const DATE_UTC = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeZone: 'UTC' });
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

export const formatNumber = (value: number): string => NUMBER.format(value);
export const formatKg = (value: number): string => `${NUMBER.format(value)} kg`;
export const formatPercent = (ratio: number | null): string => (ratio === null ? 'n/a' : `${NUMBER.format(ratio * 100)}%`);

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : DATE_TIME.format(date);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  // A bare calendar date (2026-05-04) has no time zone: show that day, not the day in the viewer's zone.
  return (DATE_ONLY.test(value) ? DATE_UTC : DATE).format(date);
}

/** `in_progress` becomes `In progress`. */
export function humanize(code: string): string {
  const text = code.replace(/[_-]+/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
