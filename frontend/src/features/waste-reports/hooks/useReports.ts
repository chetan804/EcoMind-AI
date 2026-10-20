import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { uploadImage } from '@/features/waste-classification';
import { createReport, fetchReport, fetchReports, reviewReport, type ReportFilters } from '../api/reports-api';

export const useReports = (f: ReportFilters) => useQuery({ queryKey: ['waste-reports', 'list', f], queryFn: ({ signal }) => fetchReports(f, signal) });
export const useReport = (id: string) => useQuery({ queryKey: ['waste-reports', 'detail', id], queryFn: ({ signal }) => fetchReport(id, signal) });

const AFFECTED = [['waste-reports'], ['analytics'], ['notifications']];

export function useCreateReport() {
  const client = useQueryClient();
  return useMutation({
    // The photo is uploaded first (the server re-encodes it and strips location data), then attached by id.
    mutationFn: async (v: { body: Record<string, unknown>; photo: File | null }) => {
      const mediaId = v.photo ? await uploadImage(v.photo) : null;
      return createReport({ ...v.body, media_ids: mediaId ? [mediaId] : [] });
    },
    onSuccess: () => Promise.all(AFFECTED.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export function useReviewReport(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { status: string; reason?: string }) => reviewReport(id, body),
    onSuccess: () => Promise.all(AFFECTED.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}
