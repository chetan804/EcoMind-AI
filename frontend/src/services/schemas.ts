import { z } from 'zod';

/** Page envelope shared by every list endpoint (docs/api/api-conventions.md). */
export const pageOf = <T extends z.ZodType>(item: T) =>
  z.object({
    items: z.array(item),
    total: z.number().int().nonnegative(),
    page: z.number().int().positive(),
    page_size: z.number().int().positive(),
  });

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

/** The API sends decimals as strings (exact); the UI needs numbers for display and charts. */
export const decimal = z.union([z.string(), z.number()]).pipe(z.coerce.number());
export const nullableDecimal = decimal.nullable();

export const uuid = z.string().uuid();
export const timestamp = z.string();

export const countSchema = z.object({ key: z.string(), count: z.number().int() });
export type Count = z.infer<typeof countSchema>;
