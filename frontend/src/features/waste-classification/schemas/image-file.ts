import { z } from 'zod';

export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
/** Client-side pre-check only; the server enforces its own limit when the upload API exists. */
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

export const imageFileSchema = z
  .instanceof(File)
  .refine((file) => (ACCEPTED_IMAGE_TYPES as readonly string[]).includes(file.type), {
    message: 'Use a JPEG, PNG or WebP image.',
  })
  .refine((file) => file.size > 0, { message: 'The file is empty.' })
  .refine((file) => file.size <= MAX_IMAGE_BYTES, {
    message: `The image is larger than ${MAX_IMAGE_BYTES / (1024 * 1024)} MB.`,
  });

/** Returns an error message, or null when the file is acceptable. */
export function validateImageFile(file: File): string | null {
  const result = imageFileSchema.safeParse(file);
  return result.success ? null : (result.error.issues[0]?.message ?? 'This file cannot be used.');
}
