import { apiRequest } from '@/services/api-client';
import { getJson } from '@/services/list-api';
import { pageOf } from '@/services/schemas';
import {
  activeModelSchema,
  mediaSchema,
  predictionSchema,
  queuedPredictionSchema,
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

export interface QueueFilters {
  page: number;
  /** `unreviewed` is the work queue: suggestions flagged for a person that nobody has judged yet. */
  review_status: 'unreviewed' | 'confirmed' | 'corrected' | 'rejected';
}

export const fetchReviewQueue = (f: QueueFilters, signal?: AbortSignal) =>
  getJson(
    '/classification/predictions',
    pageOf(queuedPredictionSchema),
    { page: f.page, page_size: 10, review_status: f.review_status, needs_review: f.review_status === 'unreviewed' ? true : undefined },
    signal,
  );

/** Path of the photo behind a prediction (reviewers may fetch it with the session token). */
export const predictionImagePath = (id: string) => `/api/v1/classification/predictions/${id}/image`;
