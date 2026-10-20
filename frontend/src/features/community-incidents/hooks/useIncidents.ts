import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { uploadImage } from '@/features/waste-classification';
import { assignIncident, createIncident, fetchIncidents, fetchIncidentSummary, setIncidentStatus, type IncidentFilters } from '../api/incidents-api';

export const useIncidents = (f: IncidentFilters) => useQuery({ queryKey: ['incidents', 'list', f], queryFn: ({ signal }) => fetchIncidents(f, signal) });
export const useIncidentSummary = (enabled: boolean) =>
  useQuery({ queryKey: ['incidents', 'summary'], queryFn: ({ signal }) => fetchIncidentSummary(signal), enabled });

const AFFECTED = [['incidents'], ['analytics'], ['notifications']];
const refresh = (client: ReturnType<typeof useQueryClient>) => Promise.all(AFFECTED.map((queryKey) => client.invalidateQueries({ queryKey })));

export function useCreateIncident() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (v: { body: Record<string, unknown>; photo: File | null }) => {
      const photo_media_asset_id = v.photo ? await uploadImage(v.photo) : undefined;
      return createIncident({ ...v.body, photo_media_asset_id });
    },
    onSuccess: () => refresh(client),
  });
}

export function useAssignIncident() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (v: { id: string; assignee_id: string }) => assignIncident(v.id, v.assignee_id), onSuccess: () => refresh(client) });
}

export function useIncidentStatus() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; status: string; notes?: string }) => setIncidentStatus(v.id, v.status, v.notes),
    onSuccess: () => refresh(client),
  });
}
