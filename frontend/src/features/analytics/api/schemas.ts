import { z } from 'zod';
import { countSchema, decimal, nullableDecimal } from '@/services/schemas';

export const overviewSchema = z.object({
  generated_at: z.string(),
  window_days: z.number(),
  window_start: z.string(),
  reports: z.object({ total: z.number(), in_window: z.number(), by_status: z.array(countSchema) }),
  collection: z.object({
    tasks_total: z.number(),
    open_tasks: z.number(),
    overdue_tasks: z.number(),
    completed_in_window: z.number(),
    collected_weight_kg_in_window: decimal,
    collected_weight_kg_total: decimal,
    by_status: z.array(countSchema),
  }),
  fleet: z.object({ vehicles_total: z.number(), by_status: z.array(countSchema), capacity_kg_available: decimal }),
  facilities: z.object({ total: z.number(), active: z.number() }),
  incidents: z.object({ total: z.number(), open_incidents: z.number(), unassigned_open: z.number() }),
  recovery: z.object({
    verified_records: z.number(),
    pending_records: z.number(),
    input_weight_kg: decimal,
    recovered_weight_kg: decimal,
    recovery_rate: nullableDecimal,
  }),
  rewards: z.object({ entries: z.number(), users: z.number(), net_points: z.number(), impact_weight_kg: decimal }),
  anomalies: z.object({ open_alerts: z.number(), critical_open: z.number() }),
  passports: z.object({ total: z.number(), by_status: z.array(countSchema) }),
  basis: z.string(),
});
export type Overview = z.infer<typeof overviewSchema>;

export const weeklyTrendSchema = z.object({
  weeks: z.number(),
  points: z.array(
    z.object({
      week_start: z.string(),
      collected_weight_kg: decimal,
      tasks_completed: z.number(),
      reports_submitted: z.number(),
    }),
  ),
  basis: z.string(),
});
export type WeeklyTrend = z.infer<typeof weeklyTrendSchema>;
