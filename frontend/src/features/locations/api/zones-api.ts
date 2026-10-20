import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { pageOf, uuid } from '@/services/schemas';

export const ZONE_TYPES = ['residential', 'commercial', 'industrial', 'mixed_use', 'institutional', 'other'] as const;

export const zoneSchema = z.object({
  id: uuid,
  code: z.string(),
  name: z.string(),
  zone_type: z.enum(ZONE_TYPES),
  description: z.string().nullable(),
  is_active: z.boolean(),
  facility_count: z.number(),
});
export type Zone = z.infer<typeof zoneSchema>;

/** The few facility fields this screen shows; the full record belongs to the facilities feature. */
export const zoneFacilitySchema = z.object({
  id: uuid,
  code: z.string(),
  name: z.string(),
  facility_type: z.string(),
  status: z.string(),
  city: z.string().nullable(),
});
export type ZoneFacility = z.infer<typeof zoneFacilitySchema>;

export interface ZoneFilters {
  page: number;
  q: string;
  zone_type: string;
  active: string;
}

export const fetchZones = (f: ZoneFilters & { page_size?: number }, signal?: AbortSignal) =>
  getJson('/zones', pageOf(zoneSchema), { page_size: 20, ...f }, signal);
export const createZone = (body: Record<string, unknown>) => sendJson('POST', '/zones', zoneSchema, body);
export const updateZone = (id: string, body: Record<string, unknown>) => sendJson('PATCH', `/zones/${id}`, zoneSchema, body);
export const fetchZoneFacilities = (zoneId: string, signal?: AbortSignal) =>
  getJson('/facilities', pageOf(zoneFacilitySchema), { zone_id: zoneId, page_size: 100 }, signal);
