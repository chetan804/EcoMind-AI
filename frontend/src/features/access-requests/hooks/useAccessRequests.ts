import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createRoleRequest,
  decideRoleRequest,
  fetchMyRequests,
  fetchRequests,
  withdrawRoleRequest,
  type RoleRequestInput,
} from '../api/access-requests-api';

export const useMyRequests = () => useQuery({ queryKey: ['access-requests', 'mine'], queryFn: ({ signal }) => fetchMyRequests(signal) });

export const useRequests = (params: { status_filter: string; page: number }) =>
  useQuery({ queryKey: ['access-requests', 'all', params], queryFn: ({ signal }) => fetchRequests(params, signal) });

export function useRequestChanges() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ['access-requests'] });
  return {
    create: useMutation({ mutationFn: (input: RoleRequestInput) => createRoleRequest(input), onSuccess: refresh }),
    withdraw: useMutation({ mutationFn: (id: string) => withdrawRoleRequest(id), onSuccess: refresh }),
    decide: useMutation({
      mutationFn: (v: { id: string; approve: boolean; note: string }) => decideRoleRequest(v.id, v.approve, v.note),
      onSuccess: () => {
        void refresh();
        void client.invalidateQueries({ queryKey: ['admin'] });
      },
    }),
  };
}
