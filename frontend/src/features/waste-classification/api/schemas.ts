import { z } from 'zod';

const categorySchema = z.object({ id: z.string(), code: z.string(), name: z.string() });

export const modelVersionSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  status: z.string(),
  evaluation_metrics: z
    .object({
      accuracy: z.number().optional(),
      macro_f1: z.number().optional(),
      n_test: z.number().optional(),
      dataset: z.string().optional(),
    })
    .passthrough()
    .nullable(),
});

export const activeModelSchema = z.object({
  active: modelVersionSchema.nullable(),
  scope: z.string(),
  note: z.string(),
});

export const mediaSchema = z.object({ id: z.string() });

export const predictionSchema = z.object({
  id: z.string(),
  model_name: z.string(),
  model_version: z.string(),
  material_category: categorySchema,
  confidence: z.number(),
  class_probabilities: z.record(z.string(), z.number()),
  needs_review: z.boolean(),
  review_reasons: z.array(z.string()),
  inference_ms: z.number().nullable(),
  review: z.object({
    status: z.string(),
    corrected_category: categorySchema.nullable(),
    notes: z.string().nullable(),
  }),
});

/** A prediction as listed for reviewers: also names the stored photo. */
export const queuedPredictionSchema = predictionSchema.extend({ media_asset_id: z.string() });

export type ActiveModel = z.infer<typeof activeModelSchema>;
export type QueuedPrediction = z.infer<typeof queuedPredictionSchema>;
export type Prediction = z.infer<typeof predictionSchema>;
export type ReviewDecision = 'confirmed' | 'corrected' | 'rejected';
