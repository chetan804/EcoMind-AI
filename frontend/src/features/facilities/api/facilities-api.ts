import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const FACILITY_TYPES = ['processing_center', 'depot', 'transfer_station', 'drop_off_point'] as const;
export const FACILITY_STATUSES = ['active', 'inactive', 'maintenance'] as const;

export const facilitySchema = z.object({
  id: uuid,
  code: z.string(),
  name: z.string(),
  facility_type: z.enum(FACILITY_TYPES),
  status: z.enum(FACILITY_STATUSES),
  address_line: z.string().nullable(),
  city: z.string().nullable(),
  region: z.string().nullable(),
  country_code: z.string().nullable(),
  latitude: nullableDecimal,
  longitude: nullableDecimal,
  daily_capacity_kg: nullableDecimal,
  contact_email: z.string().nullable(),
  zone_id: uuid.nullable(),
});
export type Facility = z.infer<typeof facilitySchema>;

export interface FacilityFilters {
  page: number;
  q: string;
  facility_type: string;
  status: string;
}

export const fetchFacilities = (f: FacilityFilters & { page_size?: number }, signal?: AbortSignal) =>
  getJson('/facilities', pageOf(facilitySchema), { page_size: 20, ...f }, signal);
export const createFacility = (body: Record<string, unknown>) => sendJson('POST', '/facilities', facilitySchema, body);
export const updateFacility = (id: string, body: Record<string, unknown>) => sendJson('PATCH', `/facilities/${id}`, facilitySchema, body);
