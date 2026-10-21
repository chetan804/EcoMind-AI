import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  closeListing,
  createListing,
  createRequest,
  decideRequest,
  deleteListingPhoto,
  fetchListingRequests,
  fetchListing,
  fetchListings,
  fetchMyRequests,
  publishListing,
  renewListing,
  updateListing,
  uploadListingPhoto,
  type Listing,
  type ListingFilters,
} from '../api/marketplace-api';

export const useListings = (f: ListingFilters) => useQuery({ queryKey: ['marketplace', 'list', f], queryFn: ({ signal }) => fetchListings(f, signal) });
/** One listing, kept fresh after actions; starts from the row already on screen. */
export const useListing = (initial: Listing) =>
  useQuery({ queryKey: ['marketplace', 'listing', initial.id], queryFn: ({ signal }) => fetchListing(initial.id, signal), initialData: initial, staleTime: 0 });
export const useListingRequests = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ['marketplace', 'requests', id], queryFn: ({ signal }) => fetchListingRequests(id, signal), enabled });
export const useMyRequests = (enabled: boolean) => useQuery({ queryKey: ['marketplace', 'mine'], queryFn: ({ signal }) => fetchMyRequests(signal), enabled });

/** Every marketplace mutation can change listings, requests and notifications, so refresh all three. */
function useRefresh() {
  const client = useQueryClient();
  return () => Promise.all([['marketplace'], ['notifications']].map((queryKey) => client.invalidateQueries({ queryKey })));
}

export function useSaveListing() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (v: { id?: string; body: Record<string, unknown> }) => (v.id ? updateListing(v.id, v.body) : createListing(v.body)),
    onSuccess: refresh,
  });
}
export function usePublishListing() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; days?: number }) => publishListing(v.id, v.days), onSuccess: refresh });
}
export function useRenewListing() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; days?: number }) => renewListing(v.id, v.days), onSuccess: refresh });
}
export function useCloseListing() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (v: { id: string; reason?: string; outcome?: 'handed_over' | 'withdrawn' }) => closeListing(v.id, v.reason, v.outcome),
    onSuccess: refresh,
  });
}
export function useUploadPhoto() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; file: File; caption?: string }) => uploadListingPhoto(v.id, v.file, v.caption), onSuccess: refresh });
}
export function useDeletePhoto() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; photoId: string }) => deleteListingPhoto(v.id, v.photoId), onSuccess: refresh });
}
export function useAskForListing() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; message?: string }) => createRequest(v.id, v.message), onSuccess: refresh });
}
export function useDecideRequest() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (v: { id: string; action: 'accept' | 'decline' | 'withdraw' }) => decideRequest(v.id, v.action), onSuccess: refresh });
}
