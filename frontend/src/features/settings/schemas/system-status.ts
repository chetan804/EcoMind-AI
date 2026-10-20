import { z } from 'zod';

export const livenessSchema = z.object({ status: z.literal('ok') });

export const dependencyStatusSchema = z.object({
  status: z.enum(['ok', 'failed']),
  detail: z.string().nullable().optional(),
});

export const readinessSchema = z.object({
  status: z.enum(['ready', 'not_ready']),
  checks: z.record(z.string(), dependencyStatusSchema),
});
