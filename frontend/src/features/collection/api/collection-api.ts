import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const TASK_STATUSES = ['pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled'] as const;
export const PRIORITIES = ['low', 'normal', 'high', 'urgent'] as const;
export const EVENT_TYPES = ['arrived', 'skipped', 'contaminated', 'delivered_to_facility'] as const;

const assignmentSchema = z.object({
  id: uuid,
  assignee_id: uuid,
  assignee_name: z.string(),
  vehicle_id: uuid.nullable(),
  vehicle_registration: z.string().nullable(),
  assigned_at: z.string(),
  unassigned_at: z.string().nullable(),
});

const taskFields = {
  id: uuid,
  waste_report_id: uuid.nullable(),
  destination_facility_id: uuid.nullable(),
  title: z.string(),
  status: z.enum(TASK_STATUSES),
  priority: z.enum(PRIORITIES),
  address_text: z.string().nullable(),
  latitude: nullableDecimal,
  longitude: nullableDecimal,
  due_at: z.string().nullable(),
  notes: z.string().nullable(),
  assignment: assignmentSchema.nullish(),
  collected_weight_kg: nullableDecimal.optional(),
  created_at: z.string(),
};
export const taskSchema = z.object(taskFields);
export type Task = z.infer<typeof taskSchema>;

export const taskDetailSchema = z.object({
  ...taskFields,
  history: z.array(
    z.object({
      id: uuid,
      from_status: z.enum(TASK_STATUSES).nullable(),
      to_status: z.enum(TASK_STATUSES),
      note: z.string().nullable(),
      created_at: z.string(),
    }),
  ),
  events: z.array(
    z.object({
      id: uuid,
      event_type: z.string(),
      occurred_at: z.string(),
      collected_weight_kg: nullableDecimal,
      notes: z.string().nullable(),
    }),
  ),
});
export type TaskDetail = z.infer<typeof taskDetailSchema>;

export interface TaskFilters {
  page: number;
  q: string;
  status: string;
  priority: string;
  mine: boolean;
}

const assignableSchema = pageOf(z.object({ id: uuid, full_name: z.string(), email: z.string() }));

export const fetchTasks = (f: TaskFilters & { page_size?: number }, signal?: AbortSignal) =>
  getJson('/collection/tasks', pageOf(taskSchema), { page_size: 20, sort_by: 'created_at', order: 'desc', ...f }, signal);
export const fetchTask = (id: string, signal?: AbortSignal) => getJson(`/collection/tasks/${id}`, taskDetailSchema, undefined, signal);
export const fetchCollectors = (signal?: AbortSignal) =>
  getJson('/admin/users', assignableSchema, { role: 'collector', is_active: true, page_size: 100 }, signal);

export const createTask = (body: Record<string, unknown>) => sendJson('POST', '/collection/tasks', taskSchema, body);

export type TaskAction = 'assign' | 'start' | 'events' | 'complete' | 'fail' | 'cancel' | 'reschedule';
export const taskAction = (id: string, action: TaskAction, body?: Record<string, unknown>) =>
  sendJson('POST', `/collection/tasks/${id}/${action}`, z.unknown(), body);
