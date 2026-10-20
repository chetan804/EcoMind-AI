import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createZone, fetchZoneFacilities, fetchZones, updateZone, type ZoneFilters } from '../api/zones-api';

export const useZones = (f: ZoneFilters) =>
  useQuery({ queryKey: ['zones', 'list', f], queryFn: ({ signal }) => fetchZones(f, signal) });

/** Active zones (up to 100) for pick-lists in other features. */
export const useZoneOptions = (enabled = true) =>
  useQuery({
    queryKey: ['zones', 'options'],
    queryFn: ({ signal }) => fetchZones({ page: 1, q: '', zone_type: '', active: 'true', page_size: 100 }, signal),
    enabled,
    select: (page) => page.items,
  });

export const useZoneFacilities = (zoneId: string | null) =>
  useQuery({
    queryKey: ['zones', 'facilities', zoneId],
    queryFn: ({ signal }) => fetchZoneFacilities(zoneId ?? '', signal),
    enabled: zoneId !== null,
  });

export function useSaveZone() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: string; body: Record<string, unknown> }) => (v.id ? updateZone(v.id, v.body) : createZone(v.body)),
    onSuccess: () => client.invalidateQueries({ queryKey: ['zones'] }),
  });
}
