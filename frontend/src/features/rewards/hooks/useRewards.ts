import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adjust, fetchBalance, fetchLedger, fetchLedgerSummary, fetchMyEntries, fetchUserOptions, reverse } from '../api/rewards-api';

export const useBalance = () => useQuery({ queryKey: ['rewards', 'balance'], queryFn: ({ signal }) => fetchBalance(signal) });
export const useMyEntries = (page: number, entryType: string) =>
  useQuery({ queryKey: ['rewards', 'mine', page, entryType], queryFn: ({ signal }) => fetchMyEntries(page, entryType, signal) });
export const useLedger = (f: { page: number; entry_type: string; source_type: string }) =>
  useQuery({ queryKey: ['rewards', 'ledger', f], queryFn: ({ signal }) => fetchLedger(f, signal) });
export const useLedgerSummary = () => useQuery({ queryKey: ['rewards', 'summary'], queryFn: ({ signal }) => fetchLedgerSummary(signal) });
export const useUserOptions = (enabled: boolean) =>
  useQuery({ queryKey: ['rewards', 'users'], queryFn: ({ signal }) => fetchUserOptions(signal), enabled, select: (p) => p.items });

export function useAdjust() {
  const client = useQueryClient();
  return useMutation({ mutationFn: adjust, onSuccess: () => client.invalidateQueries({ queryKey: ['rewards'] }) });
}
export function useReverse() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (v: { id: string; reason: string }) => reverse(v.id, v.reason), onSuccess: () => client.invalidateQueries({ queryKey: ['rewards'] }) });
}
