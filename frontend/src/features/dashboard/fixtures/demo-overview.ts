/**
 * DEMONSTRATION FIXTURES: illustrative values used only to validate the dashboard layout.
 * They are not measurements, not produced by any service, and must never be presented as live
 * operational data. Every region that renders them shows <DemoDataNotice />.
 * Replace with API-backed queries when the analytics module exists (see docs/project-roadmap.md).
 */
export const demoKpis = [
  { id: 'collected', label: 'Waste collected', value: '12,482 kg', tone: 'teal' },
  { id: 'diversion', label: 'Diversion rate', value: '82.4%', tone: 'teal' },
  { id: 'points', label: 'Open reports', value: '28', tone: 'blue' },
  { id: 'pending', label: 'Pending collections', value: '6', tone: 'red' },
] as const;

export const demoTrend = {
  xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
  observed: [540, 790, 830, 1140, 1000, 730, 1120],
  forecast: [null, null, null, null, 1000, 940, 1160],
  unit: 'kg per day',
} as const;

export const demoAlerts = [
  { id: 'a1', severity: 'danger', title: 'Collection overdue in Zone 04', when: '10 min ago' },
  { id: 'a2', severity: 'warning', title: 'Unusual intake volume at Depot 2', when: '1 hour ago' },
] as const;

export const demoComposition = [
  { label: 'Organic', value: 47, color: 'var(--color-teal)' },
  { label: 'Plastic', value: 24, color: 'var(--color-info)' },
  { label: 'Other', value: 29, color: 'var(--color-warning)' },
] as const;

export const demoImpact = { value: '1,248', unit: 'kg', label: 'Diverted from landfill' } as const;

/** Map pins in map-space percentages (illustrative positions only). */
export const demoPins = [
  { id: 'p1', kind: 'alert', x: 8, y: 30 },
  { id: 'p2', kind: 'collection', x: 38, y: 22 },
  { id: 'p3', kind: 'collection', x: 62, y: 50 },
  { id: 'p4', kind: 'report', x: 26, y: 62 },
  { id: 'p5', kind: 'facility', x: 82, y: 72 },
  { id: 'p6', kind: 'facility', x: 54, y: 78 },
] as const;
