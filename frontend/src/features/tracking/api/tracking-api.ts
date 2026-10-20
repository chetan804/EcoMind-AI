import { z } from 'zod';
import { apiRequest } from '@/services/api-client';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, nullableDecimal, pageOf, timestamp, uuid } from '@/services/schemas';

export const TRACKING_STATUSES = ['live', 'delayed', 'stale', 'historical', 'simulated', 'unavailable'] as const;
export type TrackingStatus = (typeof TRACKING_STATUSES)[number];
export const LOCATION_SOURCES = ['gps_device', 'mobile_client', 'imported', 'simulator'] as const;
export type LocationSource = (typeof LOCATION_SOURCES)[number];

const positionSchema = z.object({
  latitude: decimal,
  longitude: decimal,
  recorded_at: timestamp,
  received_at: timestamp,
  source: z.enum(LOCATION_SOURCES),
  accuracy_m: nullableDecimal,
  speed_kph: nullableDecimal,
  heading_deg: nullableDecimal,
  age_seconds: z.number().int(),
  collection_task_id: uuid.nullable(),
  route_plan_id: uuid.nullable(),
});
export type VehiclePositionDetail = z.infer<typeof positionSchema>;

export const vehiclePositionSchema = z.object({
  vehicle_id: uuid,
  registration_number: z.string(),
  vehicle_type: z.string(),
  vehicle_status: z.string(),
  simulated: z.boolean(),
  status: z.enum(TRACKING_STATUSES),
  position: positionSchema.nullable(),
});
export type VehiclePosition = z.infer<typeof vehiclePositionSchema>;

const latestSchema = z.object({
  generated_at: timestamp,
  live_within_seconds: z.number().int(),
  stale_after_seconds: z.number().int(),
  items: z.array(vehiclePositionSchema),
});
export type LatestPositions = z.infer<typeof latestSchema>;

export const trackingConfigSchema = z.object({
  live_within_seconds: z.number().int(),
  stale_after_seconds: z.number().int(),
  retention_days: z.number().int(),
  simulator_enabled: z.boolean(),
  max_events_per_minute: z.number().int(),
  road_routing_configured: z.boolean(),
});
export type TrackingConfig = z.infer<typeof trackingConfigSchema>;

const pathPointSchema = z.object({ latitude: decimal, longitude: decimal, recorded_at: timestamp, source: z.enum(LOCATION_SOURCES) });
export type PathPoint = z.infer<typeof pathPointSchema>;

const stopSchema = z.object({
  sequence: z.number().int(),
  kind: z.enum(['task', 'facility']),
  label: z.string(),
  latitude: decimal,
  longitude: decimal,
  task_id: uuid.nullable(),
  task_status: z.string().nullable(),
  completed: z.boolean(),
});

export const routeTrackingSchema = z.object({
  route_plan_id: uuid,
  plan_status: z.string(),
  vehicle_id: uuid.nullable(),
  stops: z.array(stopSchema),
  completed_task_stops: z.number().int(),
  total_task_stops: z.number().int(),
  vehicle: vehiclePositionSchema.nullable(),
  path: z.array(pathPointSchema),
  path_simulated: z.boolean(),
  path_truncated: z.boolean(),
  basis: z.string(),
});
export type RouteTracking = z.infer<typeof routeTrackingSchema>;

export const collectionTrackingSchema = z.object({
  task_id: uuid,
  title: z.string(),
  status: z.string(),
  latitude: nullableDecimal,
  longitude: nullableDecimal,
  destination_facility_id: uuid.nullable(),
  vehicle_id: uuid.nullable(),
  vehicle: vehiclePositionSchema.nullable(),
  path: z.array(pathPointSchema),
  path_truncated: z.boolean(),
  basis: z.string(),
});
export type CollectionTracking = z.infer<typeof collectionTrackingSchema>;

const ingestSchema = z.object({ duplicate: z.boolean(), event: z.object({ id: uuid }) });

export const fetchTrackingConfig = (signal?: AbortSignal) => getJson('/tracking/config', trackingConfigSchema, undefined, signal);
export const fetchLatestPositions = (includeSimulated: boolean, signal?: AbortSignal) =>
  getJson('/tracking/vehicles', latestSchema, { include_simulated: includeSimulated }, signal);
export const fetchRouteTracking = (planId: string, includeSimulated: boolean, signal?: AbortSignal) =>
  getJson(`/tracking/route-plans/${planId}`, routeTrackingSchema, { include_simulated: includeSimulated }, signal);
export const fetchCollectionTracking = (taskId: string, signal?: AbortSignal) =>
  getJson(`/tracking/collections/${taskId}`, collectionTrackingSchema, undefined, signal);

const historySchema = pageOf(z.object({ id: uuid, latitude: decimal, longitude: decimal, recorded_at: timestamp, source: z.enum(LOCATION_SOURCES), quality: z.string() }));
export const fetchLocationHistory = (vehicleId: string, signal?: AbortSignal) =>
  getJson(`/tracking/vehicles/${vehicleId}/locations`, historySchema, { page_size: 20 }, signal);

export const postSimulatedLocation = (vehicleId: string, body: Record<string, unknown>) =>
  sendJson('POST', `/tracking/simulation/vehicles/${vehicleId}/locations`, ingestSchema, body);
export const resetSimulation = (vehicleId: string) =>
  apiRequest<{ removed: number }>(`/tracking/simulation/vehicles/${vehicleId}/locations`, { method: 'DELETE' });
