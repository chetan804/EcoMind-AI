import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { pageOf, uuid } from '@/services/schemas';

export const requestStatus = z.enum(['pending', 'approved', 'rejected', 'withdrawn']);
export type RequestStatus = z.infer<typeof requestStatus>;

export const roleRequestSchema = z.object({
  id: uuid,
  user_id: uuid,
  requester_email: z.string(),
  requester_name: z.string(),
  requested_role: z.enum(['collector', 'facility_operator', 'manager']),
  status: requestStatus,
  reason: z.string(),
  organisation: z.string().nullable(),
  decided_by_id: uuid.nullable(),
  decided_at: z.string().nullable(),
  decision_note: z.string().nullable(),
  created_at: z.string(),
});
export type RoleRequest = z.infer<typeof roleRequestSchema>;

export interface RoleRequestInput {
  requested_role: RoleRequest['requested_role'];
  reason: string;
  organisation?: string;
}

export const createRoleRequest = (input: RoleRequestInput) => sendJson('POST', '/access-requests', roleRequestSchema, input);
export const fetchMyRequests = (signal?: AbortSignal) => getJson('/access-requests/mine', z.array(roleRequestSchema), undefined, signal);
export const withdrawRoleRequest = (id: string) => sendJson('POST', `/access-requests/${id}/withdraw`, roleRequestSchema);
export const fetchRequests = (params: { status_filter: string; page: number }, signal?: AbortSignal) =>
  getJson('/access-requests', pageOf(roleRequestSchema), { ...params, page_size: 20 }, signal);
export const decideRoleRequest = (id: string, approve: boolean, note: string) =>
  sendJson('POST', `/access-requests/${id}/decision`, roleRequestSchema, { approve, note: note.trim() || undefined });

