import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createVehicle, fetchVehicles, updateVehicle, type VehicleFilters } from '../api/fleet-api';

export const useVehicles = (f: VehicleFilters) => useQuery({ queryKey: ['fleet', 'list', f], queryFn: ({ signal }) => fetchVehicles(f, signal) });

/** Vehicles that can be given work (not retired), for pick-lists in other features. */
export const useVehicleOptions = (enabled = true) =>
  useQuery({
    queryKey: ['fleet', 'options'],
    queryFn: ({ signal }) => fetchVehicles({ page: 1, q: '', vehicle_type: '', status: '', page_size: 100 }, signal),
    enabled,
    select: (page) => page.items.filter((v) => v.status !== 'retired'),
  });

export function useSaveVehicle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: string; body: Record<string, unknown> }) => (v.id ? updateVehicle(v.id, v.body) : createVehicle(v.body)),
    onSuccess: () => client.invalidateQueries({ queryKey: ['fleet'] }),
  });
}
