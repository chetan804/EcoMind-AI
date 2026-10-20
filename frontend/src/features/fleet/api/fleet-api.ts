import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, pageOf, uuid } from '@/services/schemas';

export const VEHICLE_TYPES = ['compactor_truck', 'tipper_truck', 'van', 'cargo_bike', 'other'] as const;
export const VEHICLE_STATUSES = ['available', 'in_service', 'maintenance', 'retired'] as const;

export const vehicleSchema = z.object({
  id: uuid,
  registration_number: z.string(),
  vehicle_type: z.enum(VEHICLE_TYPES),
  status: z.enum(VEHICLE_STATUSES),
  capacity_kg: decimal,
  home_facility_id: uuid.nullable(),
  active_task_count: z.number().int().optional(),
});
export type Vehicle = z.infer<typeof vehicleSchema>;

export interface VehicleFilters {
  page: number;
  q: string;
  vehicle_type: string;
  status: string;
}

export const fetchVehicles = (f: VehicleFilters & { page_size?: number }, signal?: AbortSignal) =>
  getJson('/fleet/vehicles', pageOf(vehicleSchema), { page_size: 20, ...f }, signal);
export const createVehicle = (body: Record<string, unknown>) => sendJson('POST', '/fleet/vehicles', vehicleSchema, body);
export const updateVehicle = (id: string, body: Record<string, unknown>) => sendJson('PATCH', `/fleet/vehicles/${id}`, vehicleSchema, body);
