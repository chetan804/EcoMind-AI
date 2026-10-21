import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const ENTRY_TYPES = ['earned', 'redeemed', 'adjustment', 'reversal'] as const;
export const SOURCE_TYPES = ['waste_report', 'collection_task', 'recovery_record', 'community_incident', 'manual', 'reward_redemption'] as const;

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

// -- catalogue and redemptions ----------------------------------------------------------------
export const REDEMPTION_STATUSES = ['pending', 'fulfilled', 'cancelled'] as const;

export const catalogItemSchema = z.object({
  id: uuid,
  name: z.string(),
  description: z.string().nullable(),
  points_cost: z.number().int(),
  stock_remaining: z.number().int().nullable(),
  valid_until: z.string().nullable(),
  remaining_for_you: z.number().int().nullable(),
  available: z.boolean(),
  unavailable_reason: z.enum(['out_of_stock', 'limit_reached']).nullable(),
});
export type CatalogItem = z.infer<typeof catalogItemSchema>;

export const itemSchema = z.object({
  id: uuid,
  name: z.string(),
  description: z.string().nullable(),
  points_cost: z.number().int(),
  stock: z.number().int().nullable(),
  max_per_user: z.number().int().nullable(),
  active: z.boolean(),
  valid_until: z.string().nullable(),
  redeemed_count: z.number().int(),
  pending_count: z.number().int(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type RewardItem = z.infer<typeof itemSchema>;

export const redemptionSchema = z.object({
  id: uuid,
  user_id: uuid,
  user_name: z.string().nullable(),
  user_email: z.string().nullable(),
  item_id: uuid,
  item_name: z.string(),
  points_spent: z.number().int(),
  code: z.string(),
  status: z.enum(REDEMPTION_STATUSES),
  created_at: z.string(),
  fulfilled_at: z.string().nullable(),
  note: z.string().nullable(),
  cancelled_at: z.string().nullable(),
  cancel_reason: z.string().nullable(),
});
export type Redemption = z.infer<typeof redemptionSchema>;

export interface ItemInput {
  name: string;
  description: string | null;
  points_cost: number;
  stock: number | null;
  max_per_user: number | null;
  valid_until: string | null;
}

export const fetchCatalog = (page: number, signal?: AbortSignal) =>
  getJson('/rewards/catalog', pageOf(catalogItemSchema), { page, page_size: 24 }, signal);
export const redeemItem = (itemId: string, clientRequestId: string) =>
  sendJson('POST', `/rewards/catalog/${itemId}/redeem`, redemptionSchema, { client_request_id: clientRequestId });
export const fetchMyRedemptions = (page: number, signal?: AbortSignal) =>
  getJson('/rewards/me/redemptions', pageOf(redemptionSchema), { page, page_size: 20 }, signal);
export const cancelMyRedemption = (id: string, reason?: string) =>
  sendJson('POST', `/rewards/me/redemptions/${id}/cancel`, redemptionSchema, reason ? { reason } : {});

export const fetchItems = (page: number, signal?: AbortSignal) =>
  getJson('/rewards/items', pageOf(itemSchema), { page, page_size: 20 }, signal);
export const createItem = (body: ItemInput & { active: boolean }) => sendJson('POST', '/rewards/items', itemSchema, body);
export const updateItem = (id: string, body: Partial<ItemInput> & { active?: boolean }) =>
  sendJson('PATCH', `/rewards/items/${id}`, itemSchema, body);
export const fetchRedemptions = (f: { page: number; status: string; code: string }, signal?: AbortSignal) =>
  getJson('/rewards/redemptions', pageOf(redemptionSchema), { page_size: 20, ...f }, signal);
export const fulfilRedemption = (id: string, note?: string) =>
  sendJson('POST', `/rewards/redemptions/${id}/fulfil`, redemptionSchema, note ? { note } : {});
export const cancelRedemption = (id: string, reason: string) =>
  sendJson('POST', `/rewards/redemptions/${id}/cancel`, redemptionSchema, { reason });
