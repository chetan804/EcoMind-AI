import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const PLAN_STATUSES = ['draft', 'published', 'in_progress', 'completed', 'cancelled'] as const;

const planFields = {
  id: uuid,
  name: z.string(),
  planned_date: z.string(),
  status: z.enum(PLAN_STATUSES),
  vehicle_id: uuid.nullable(),
  driver_id: uuid.nullable(),
  start_facility_id: uuid.nullable(),
  end_facility_id: uuid.nullable(),
  total_distance_km: nullableDecimal,
  optimizer: z.string().nullable(),
};
export const planSchema = z.object(planFields);
export type Plan = z.infer<typeof planSchema>;

export const planDetailSchema = z.object({
  ...planFields,
  start_label: z.string().nullish(),
  return_leg_distance_km: nullableDecimal.optional(),
  stops: z.array(
    z.object({
      sequence: z.number().int(),
      kind: z.enum(['task', 'facility']),
      collection_task_id: uuid.nullable(),
      facility_id: uuid.nullable(),
      label: z.string(),
      latitude: decimal,
      longitude: decimal,
      leg_distance_km: decimal,
    }),
  ),
  warnings: z.array(z.string()).optional(),
  basis: z.string().optional(),
});
export type PlanDetail = z.infer<typeof planDetailSchema>;

export interface PlanFilters {
  page: number;
  status: string;
}

export const fetchPlans = (f: PlanFilters, signal?: AbortSignal) =>
  getJson('/route-planning/plans', pageOf(planSchema), { page_size: 20, sort_by: 'planned_date', order: 'desc', ...f }, signal);
export const fetchPlan = (id: string, signal?: AbortSignal) => getJson(`/route-planning/plans/${id}`, planDetailSchema, undefined, signal);
export const createPlan = (body: Record<string, unknown>) => sendJson('POST', '/route-planning/plans', planDetailSchema, body);
export const planAction = (id: string, action: 'publish' | 'cancel', reason?: string) =>
  sendJson('POST', `/route-planning/plans/${id}/${action}`, planDetailSchema, reason ? { reason } : {});
