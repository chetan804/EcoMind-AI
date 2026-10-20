import { apiRequest } from '@/services/api-client';
import {
  activeModelSchema,
  mediaSchema,
  predictionSchema,
  type ActiveModel,
  type Prediction,
  type ReviewDecision,
} from './schemas';

export async function fetchActiveModel(signal?: AbortSignal): Promise<ActiveModel> {
  return activeModelSchema.parse(await apiRequest<unknown>('/classification/model', { signal }));
}

/** Upload the photo (raw body; the server re-encodes it and strips location metadata). */
export async function uploadImage(file: File): Promise<string> {
  const media = mediaSchema.parse(
    await apiRequest<unknown>(`/waste-reports/media?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      body: file,
    }),
  );
  return media.id;
}

export async function createPrediction(mediaId: string): Promise<Prediction> {
  return predictionSchema.parse(
    await apiRequest<unknown>('/classification/predictions', { method: 'POST', body: { media_id: mediaId } }),
  );
}

export async function reviewPrediction(
  predictionId: string,
  review: { decision: ReviewDecision; material_category_code?: string; notes?: string },
): Promise<Prediction> {
  return predictionSchema.parse(
    await apiRequest<unknown>(`/classification/predictions/${predictionId}/review`, {
      method: 'POST',
      body: review,
    }),
  );
}
