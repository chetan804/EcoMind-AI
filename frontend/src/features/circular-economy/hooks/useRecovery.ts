import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createRecord, fetchRecords, fetchSummary, verifyRecord, type RecoveryFilters } from '../api/recovery-api';

export const useRecords = (f: RecoveryFilters) => useQuery({ queryKey: ['recovery', 'list', f], queryFn: ({ signal }) => fetchRecords(f, signal) });
export const useRecoverySummary = () => useQuery({ queryKey: ['recovery', 'summary'], queryFn: ({ signal }) => fetchSummary(signal) });
/** Recent records for pick-lists (linking a passport to its recovery record). */
export const useRecordOptions = (enabled: boolean) =>
  useQuery({
    queryKey: ['recovery', 'options'],
    queryFn: ({ signal }) => fetchRecords({ page: 1, status: '', recovery_method: '', facility_id: '' }, signal),
    enabled,
    select: (p) => p.items.filter((r) => r.verification_status !== 'rejected'),
  });

const useInvalidating = <V,>(fn: (v: V) => Promise<unknown>) => {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: ['recovery'] }), client.invalidateQueries({ queryKey: ['analytics'] }), client.invalidateQueries({ queryKey: ['passports'] })]) });
};
export const useCreateRecord = () => useInvalidating(createRecord);
export const useVerifyRecord = () => useInvalidating((v: { id: string; decision: 'verified' | 'rejected'; notes?: string }) => verifyRecord(v.id, v.decision, v.notes));
