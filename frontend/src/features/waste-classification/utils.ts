import { ApiError } from '@/services/api-client';
import { getErrorMessage } from '@/services/error-handler';

/** What a reviewer sees for each reason the server gives for sending a prediction to review. */
export const REVIEW_REASON_TEXT: Record<string, string> = {
  low_confidence: 'The model is not confident enough to accept this result on its own.',
  unfamiliar_image: 'This image looks unlike the photos the model was trained on.',
};

export const percent = (value: number): string => `${Math.round(value * 100)}%`;

/** Error text for the classify flow. Server codes get specific wording; the rest use the shared mapper. */
export function describeClassifyError(error: unknown): { title: string; detail: string } {
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'no_active_model':
        return { title: 'No model is active', detail: 'An administrator needs to activate a classification model before images can be analysed.' };
      case 'model_unavailable':
        return { title: 'The model is unavailable', detail: 'The model could not be loaded on the server. Nothing was saved. Try again later or contact an administrator.' };
      case 'invalid_image':
        return { title: 'This image cannot be analysed', detail: error.message };
      case 'payload_too_large':
        return { title: 'The image is too large', detail: error.message };
    }
    if (error.status === 429) return { title: 'Too many requests', detail: 'Please wait a moment before trying again.' };
  }
  return { title: 'Classification failed', detail: getErrorMessage(error) };
}
