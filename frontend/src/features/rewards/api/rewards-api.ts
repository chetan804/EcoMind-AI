import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const ENTRY_TYPES = ['earned', 'redeemed', 'adjustment', 'reversal'] as const;
export const SOURCE_TYPES = ['waste_report', 'collection_task', 'recovery_record', 'community_incident', 'manual'] as const;

export const balanceSchema = z.object({
  user_id: uuid,
  points: z.number().int(),
  earned_points: z.number().int(),
  impact_weight_kg: decimal,
  entries: z.number().int(),
  points_per_kg: z.number().int(),
  basis: z.string().optional(),
});

export const entrySchema = z.object({
  id: uuid,
  user_id: uuid,
  entry_type: z.enum(ENTRY_TYPES),
  points: z.number().int(),
  impact_weight_kg: nullableDecimal,
  source_type: z.enum(SOURCE_TYPES),
  source_id: uuid.nullable(),
  reverses_entry_id: uuid.nullable(),
  description: z.string().nullable(),
  created_at: z.string(),
});
export type Entry = z.infer<typeof entrySchema>;

export const ledgerSummarySchema = z.object({
  entries: z.number().int(),
  users: z.number().int(),
  points_issued: z.number().int(),
  points_removed: z.number().int(),
  net_points: z.number().int(),
  impact_weight_kg: decimal,
  basis: z.string().optional(),
});

const userOption = pageOf(z.object({ id: uuid, full_name: z.string(), email: z.string() }));

export const fetchBalance = (signal?: AbortSignal) => getJson('/rewards/me/balance', balanceSchema, undefined, signal);
export const fetchMyEntries = (page: number, entry_type: string, signal?: AbortSignal) =>
  getJson('/rewards/me/entries', pageOf(entrySchema), { page, page_size: 20, entry_type }, signal);
export const fetchLedger = (f: { page: number; entry_type: string; source_type: string }, signal?: AbortSignal) =>
  getJson('/rewards/ledger', pageOf(entrySchema), { page_size: 20, ...f }, signal);
export const fetchLedgerSummary = (signal?: AbortSignal) => getJson('/rewards/ledger/summary', ledgerSummarySchema, undefined, signal);
export const fetchUserOptions = (signal?: AbortSignal) => getJson('/admin/users', userOption, { is_active: true, page_size: 100 }, signal);

export const adjust = (body: { user_id: string; points: number; description: string }) => sendJson('POST', '/rewards/adjustments', entrySchema, body);
export const reverse = (id: string, reason: string) => sendJson('POST', `/rewards/entries/${id}/reverse`, entrySchema, { reason });
