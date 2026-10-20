import { useMutation, useQuery } from '@tanstack/react-query';
import { createPrediction, fetchActiveModel, reviewPrediction, uploadImage } from '../api/classification-api';

export const modelKey = ['classification', 'model'] as const;

export function useActiveModel() {
  return useQuery({ queryKey: modelKey, queryFn: ({ signal }) => fetchActiveModel(signal) });
}

/** Upload, then classify. The two requests are separate API calls; either can fail on its own. */
export function useClassifyImage() {
  return useMutation({
    mutationFn: async (file: File) => createPrediction(await uploadImage(file)),
  });
}

export function useReviewPrediction(predictionId: string) {
  return useMutation({
    mutationFn: (review: Parameters<typeof reviewPrediction>[1]) => reviewPrediction(predictionId, review),
  });
}
