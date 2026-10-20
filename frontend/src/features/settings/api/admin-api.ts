import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { pageOf, uuid } from '@/services/schemas';

export const userSchema = z.object({
  id: uuid,
  email: z.string(),
  full_name: z.string(),
  is_active: z.boolean(),
  mfa_enabled: z.boolean(),
  roles: z.array(z.string()),
  created_at: z.string(),
  last_login_at: z.string().nullable(),
});
export type AdminUser = z.infer<typeof userSchema>;

const roleSchema = z.object({
  name: z.string(),
  description: z.string().nullable(),
  is_system: z.boolean(),
  user_count: z.number().int(),
  permissions: z.array(z.string()),
});
export type Role = z.infer<typeof roleSchema>;

export const auditSchema = z.object({
  id: uuid,
  occurred_at: z.string(),
  action: z.string(),
  entity_type: z.string(),
  entity_id: uuid.nullable(),
  actor_id: uuid.nullable(),
  actor_email: z.string().nullable(),
  request_id: z.string().nullable(),
  ip_address: z.string().nullable(),
  changes: z.record(z.string(), z.unknown()).nullable(),
});
export type AuditEntry = z.infer<typeof auditSchema>;

export interface UserFilters {
  page: number;
  q: string;
  role: string;
  is_active: string;
}
export interface AuditFilters {
  page: number;
  action: string;
  entity_type: string;
}

export const fetchUsers = (f: UserFilters, signal?: AbortSignal) =>
  getJson('/admin/users', pageOf(userSchema), { ...f, page_size: 20 }, signal);
export const fetchRoles = (signal?: AbortSignal) => getJson('/admin/roles', z.array(roleSchema), undefined, signal);
export const fetchAudit = (f: AuditFilters, signal?: AbortSignal) =>
  getJson('/admin/audit-logs', pageOf(auditSchema), { ...f, page_size: 25 }, signal);

export const setRoles = (id: string, roles: string[], reason: string) =>
  sendJson('PUT', `/admin/users/${id}/roles`, userSchema, { roles, reason });
export type UserAction = 'deactivate' | 'activate' | 'reset-mfa';
export const userAction = (id: string, action: UserAction, reason: string) => sendJson('POST', `/admin/users/${id}/${action}`, userSchema, { reason });
