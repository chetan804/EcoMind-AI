import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchAudit, fetchRoles, fetchUsers, setRoles, userAction, type AuditFilters, type UserAction, type UserFilters } from '../api/admin-api';

export const useUsers = (f: UserFilters) => useQuery({ queryKey: ['admin', 'users', f], queryFn: ({ signal }) => fetchUsers(f, signal) });
export const useRoles = () => useQuery({ queryKey: ['admin', 'roles'], queryFn: ({ signal }) => fetchRoles(signal) });
export const useAudit = (f: AuditFilters) => useQuery({ queryKey: ['admin', 'audit', f], queryFn: ({ signal }) => fetchAudit(f, signal) });

export function useUserChange() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; roles?: string[]; action?: UserAction; reason: string }) =>
      v.roles ? setRoles(v.id, v.roles, v.reason) : userAction(v.id, v.action ?? 'deactivate', v.reason),
    onSuccess: () => client.invalidateQueries({ queryKey: ['admin'] }),
  });
}
