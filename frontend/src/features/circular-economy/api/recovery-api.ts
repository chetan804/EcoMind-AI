import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const METHODS = ['recycled', 'composted', 'reused', 'refurbished', 'energy_recovered'] as const;
export const VERIFICATION = ['pending', 'verified', 'rejected'] as const;

export const recoverySchema = z.object({
  id: uuid,
  facility_id: uuid,
  material_category_id: uuid,
  collection_task_id: uuid.nullable(),
  recovery_method: z.enum(METHODS),
  input_weight_kg: decimal,
  recovered_weight_kg: decimal,
  processed_at: z.string(),
  verification_status: z.enum(VERIFICATION),
  verified_at: z.string().nullable(),
  notes: z.string().nullable(),
});
export type Recovery = z.infer<typeof recoverySchema>;

const breakdown = z.object({ key: z.string(), label: z.string(), records: z.number().int(), input_weight_kg: decimal, recovered_weight_kg: decimal, recovery_rate: nullableDecimal });
export const summarySchema = z.object({
  verified_records: z.number().int(),
  input_weight_kg: decimal,
  recovered_weight_kg: decimal,
  recovery_rate: nullableDecimal,
  pending_records: z.number().int(),
  rejected_records: z.number().int(),
  by_category: z.array(breakdown),
  by_method: z.array(breakdown),
  basis: z.string().optional(),
});

export interface RecoveryFilters {
  page: number;
  status: string;
  recovery_method: string;
  facility_id: string;
}

export const fetchRecords = (f: RecoveryFilters, signal?: AbortSignal) =>
  getJson('/circular-economy/recovery-records', pageOf(recoverySchema), { page_size: 20, sort_by: 'processed_at', order: 'desc', ...f }, signal);
export const fetchSummary = (signal?: AbortSignal) => getJson('/circular-economy/recovery-records/summary', summarySchema, undefined, signal);
export const createRecord = (body: Record<string, unknown>) => sendJson('POST', '/circular-economy/recovery-records', recoverySchema, body);
export const verifyRecord = (id: string, decision: 'verified' | 'rejected', notes?: string) =>
  sendJson('POST', `/circular-economy/recovery-records/${id}/verify`, recoverySchema, { decision, notes });
