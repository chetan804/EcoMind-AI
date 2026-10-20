import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createFacility, fetchFacilities, updateFacility, type FacilityFilters } from '../api/facilities-api';

export const useFacilities = (f: FacilityFilters) =>
  useQuery({ queryKey: ['facilities', 'list', f], queryFn: ({ signal }) => fetchFacilities(f, signal) });

/** Every facility (up to 100) for pick-lists in other features. */
export const useFacilityOptions = (enabled = true) =>
  useQuery({
    queryKey: ['facilities', 'options'],
    queryFn: ({ signal }) => fetchFacilities({ page: 1, q: '', facility_type: '', status: '', page_size: 100 }, signal),
    enabled,
    select: (page) => page.items,
  });

export function useSaveFacility() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: string; body: Record<string, unknown> }) => (v.id ? updateFacility(v.id, v.body) : createFacility(v.body)),
    onSuccess: () => client.invalidateQueries({ queryKey: ['facilities'] }),
  });
}
