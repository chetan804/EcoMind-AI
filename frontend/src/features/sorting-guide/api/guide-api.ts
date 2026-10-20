import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { pageOf, uuid } from '@/services/schemas';

export const DISPOSAL_METHODS = ['recycle', 'compost', 'reuse', 'landfill', 'hazardous_drop_off', 'e_waste_drop_off', 'special_collection'] as const;

export const categorySchema = z.object({
  id: uuid,
  code: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  is_active: z.boolean(),
  guidance_count: z.number().int().optional(),
});
export type Category = z.infer<typeof categorySchema>;

export const guidanceSchema = z.object({
  id: uuid,
  material_category_id: uuid,
  category_code: z.string(),
  category_name: z.string(),
  disposal_method: z.enum(DISPOSAL_METHODS),
  title: z.string(),
  instructions: z.string(),
  preparation_notes: z.string().nullable(),
  source_reference: z.string().nullable(),
  has_source: z.boolean(),
  is_active: z.boolean(),
  updated_at: z.string(),
});
export type Guidance = z.infer<typeof guidanceSchema>;

export interface GuidanceFilters {
  page: number;
  q: string;
  category_id: string;
  disposal_method: string;
  include_inactive: boolean;
}

export const fetchCategories = (includeInactive: boolean, signal?: AbortSignal) =>
  getJson('/sorting-guide/categories', pageOf(categorySchema), { page_size: 100, include_inactive: includeInactive }, signal);
export const fetchGuidance = (f: GuidanceFilters, signal?: AbortSignal) =>
  getJson('/sorting-guide/guidance', pageOf(guidanceSchema), { page_size: 20, ...f }, signal);

export const createCategory = (body: Record<string, unknown>) => sendJson('POST', '/sorting-guide/categories', categorySchema, body);
export const createGuidance = (body: Record<string, unknown>) => sendJson('POST', '/sorting-guide/guidance', guidanceSchema, body);
export const updateGuidance = (id: string, body: Record<string, unknown>) => sendJson('PATCH', `/sorting-guide/guidance/${id}`, guidanceSchema, body);
