export const PIN_COLOR = {
  alert: 'var(--color-danger)',
  collection: 'var(--color-info)',
  report: 'var(--color-warning)',
  facility: 'var(--color-teal)',
} as const;

export const mapLegend = [
  { label: 'Reports', color: PIN_COLOR.report },
  { label: 'Collections', color: PIN_COLOR.collection },
  { label: 'Facilities', color: PIN_COLOR.facility },
  { label: 'Alerts', color: PIN_COLOR.alert },
];
