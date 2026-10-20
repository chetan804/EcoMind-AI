import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { addEvent, createPassport, fetchIntegrity, fetchPassport, fetchPassports, linkRecovery, type PassportFilters } from '../api/passports-api';

export const usePassports = (f: PassportFilters) => useQuery({ queryKey: ['passports', 'list', f], queryFn: ({ signal }) => fetchPassports(f, signal) });
export const usePassport = (id: string) => useQuery({ queryKey: ['passports', 'detail', id], queryFn: ({ signal }) => fetchPassport(id, signal) });
/** Runs only when asked (the button), because it is a verification, not page data. */
export const useIntegrity = (id: string) => useQuery({ queryKey: ['passports', 'integrity', id], queryFn: ({ signal }) => fetchIntegrity(id, signal), enabled: false, retry: false });

const useInvalidating = <V,>(fn: (v: V) => Promise<unknown>) => {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: ['passports'] }) });
};
export const useCreatePassport = () => useInvalidating(createPassport);
export const useAddEvent = (id: string) => useInvalidating((body: Record<string, unknown>) => addEvent(id, body));
export const useLinkRecovery = (id: string) => useInvalidating((recoveryId: string) => linkRecovery(id, recoveryId));
