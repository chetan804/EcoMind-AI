import { z } from 'zod';
import { getJson } from '@/services/list-api';
import { pageOf, uuid } from '@/services/schemas';

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

export interface AuditFilters {
  page: number;
  action: string;
  entity_type: string;
}

export const fetchAudit = (f: AuditFilters, signal?: AbortSignal) =>
  getJson('/admin/audit-logs', pageOf(auditSchema), { ...f, page_size: 25 }, signal);
