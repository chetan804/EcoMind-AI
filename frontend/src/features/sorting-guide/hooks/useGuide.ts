import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createCategory, createGuidance, fetchCategories, fetchGuidance, updateGuidance, type GuidanceFilters } from '../api/guide-api';

/** Material categories (shared by the guide, recovery records and passports). */
export const useCategories = (includeInactive = false, enabled = true) =>
  useQuery({ queryKey: ['sorting-guide', 'categories', includeInactive], queryFn: ({ signal }) => fetchCategories(includeInactive, signal), enabled, select: (p) => p.items });
export const useGuidance = (f: GuidanceFilters) => useQuery({ queryKey: ['sorting-guide', 'guidance', f], queryFn: ({ signal }) => fetchGuidance(f, signal) });

const useInvalidating = <V,>(fn: (v: V) => Promise<unknown>) => {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: ['sorting-guide'] }) });
};
export const useCreateCategory = () => useInvalidating(createCategory);
export const useCreateGuidance = () => useInvalidating(createGuidance);
export const useUpdateGuidance = () => useInvalidating((v: { id: string; body: Record<string, unknown> }) => updateGuidance(v.id, v.body));
