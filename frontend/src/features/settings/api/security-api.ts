import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';

const statusSchema = z.object({
  enabled: z.boolean(),
  pending_enrollment: z.boolean(),
  enabled_at: z.string().nullable(),
  recovery_codes_remaining: z.number().int(),
});
export type MfaStatus = z.infer<typeof statusSchema>;

const enrollSchema = z.object({
  secret: z.string(),
  otpauth_uri: z.string(),
  issuer: z.string(),
  digits: z.number().int(),
  period_seconds: z.number().int(),
});
export type MfaEnrollment = z.infer<typeof enrollSchema>;

const codesSchema = z.object({ recovery_codes: z.array(z.string()) });
const emptySchema = z.unknown();

export const fetchMfaStatus = (signal?: AbortSignal) => getJson('/auth/mfa', statusSchema, undefined, signal);
export const enrollMfa = () => sendJson('POST', '/auth/mfa/enroll', enrollSchema);
export const activateMfa = (code: string) => sendJson('POST', '/auth/mfa/activate', codesSchema, { code });
export const disableMfa = (proof: { password: string; code: string }) => sendJson('POST', '/auth/mfa/disable', emptySchema, proof);
export const regenerateRecoveryCodes = (proof: { password: string; code: string }) =>
  sendJson('POST', '/auth/mfa/recovery-codes', codesSchema, proof);
