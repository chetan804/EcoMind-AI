import { useQuery } from '@tanstack/react-query';
import { fetchAudit, type AuditFilters } from '../api/audit-api';

export const useAudit = (f: AuditFilters) => useQuery({ queryKey: ['admin', 'audit', f], queryFn: ({ signal }) => fetchAudit(f, signal) });
