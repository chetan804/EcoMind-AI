import type { z } from 'zod';
import type { dependencyStatusSchema, livenessSchema, readinessSchema } from '../schemas/system-status';

export type Liveness = z.infer<typeof livenessSchema>;
export type DependencyStatus = z.infer<typeof dependencyStatusSchema>;
export type Readiness = z.infer<typeof readinessSchema>;
