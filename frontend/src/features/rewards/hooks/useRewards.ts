import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  adjust,
  cancelMyRedemption,
  cancelRedemption,
  createItem,
  fetchBalance,
  fetchCatalog,
  fetchItems,
  fetchLedger,
  fetchLedgerSummary,
  fetchMyEntries,
  fetchMyRedemptions,
  fetchRedemptions,
  fetchUserOptions,
  fulfilRedemption,
  redeemItem,
  reverse,
  updateItem,
  type ItemInput,
} from '../api/rewards-api';

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

export const useCatalog = (page: number) =>
  useQuery({ queryKey: ['rewards', 'catalog', page], queryFn: ({ signal }) => fetchCatalog(page, signal) });
export const useMyRedemptions = (page: number) =>
  useQuery({ queryKey: ['rewards', 'my-redemptions', page], queryFn: ({ signal }) => fetchMyRedemptions(page, signal) });
export const useItems = (page: number) =>
  useQuery({ queryKey: ['rewards', 'items', page], queryFn: ({ signal }) => fetchItems(page, signal) });
export const useRedemptionQueue = (f: { page: number; status: string; code: string }) =>
  useQuery({ queryKey: ['rewards', 'queue', f], queryFn: ({ signal }) => fetchRedemptions(f, signal) });

/** Everything on the page depends on the ledger, so any change refreshes all of it. */
function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ['rewards'] });
}

/**
 * The request id belongs to one deliberate attempt: the dialog creates it once, so a retry after a
 * lost response is the same request and cannot spend the points twice.
 */
export function useRedeem() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { itemId: string; clientRequestId: string }) => redeemItem(v.itemId, v.clientRequestId), onSuccess: refresh });
}
export function useCancelMine() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; reason?: string }) => cancelMyRedemption(v.id, v.reason), onSuccess: refresh });
}
export function useCreateItem() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: ItemInput & { active: boolean }) => createItem(v), onSuccess: refresh });
}
export function useUpdateItem() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; body: Partial<ItemInput> & { active?: boolean } }) => updateItem(v.id, v.body), onSuccess: refresh });
}
export function useFulfil() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; note?: string }) => fulfilRedemption(v.id, v.note), onSuccess: refresh });
}
export function useCancelRedemption() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; reason: string }) => cancelRedemption(v.id, v.reason), onSuccess: refresh });
}
