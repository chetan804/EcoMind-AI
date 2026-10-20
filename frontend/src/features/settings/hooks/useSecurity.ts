import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { activateMfa, disableMfa, enrollMfa, fetchMfaStatus, regenerateRecoveryCodes } from '../api/security-api';

const key = ['security', 'mfa'] as const;

export const useMfaStatus = () => useQuery({ queryKey: key, queryFn: ({ signal }) => fetchMfaStatus(signal) });

function useRefreshing<V, R>(fn: (v: V) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: key }) });
}

export const useEnrollMfa = () => useRefreshing(enrollMfa);
export const useActivateMfa = () => useRefreshing(activateMfa);
export const useDisableMfa = () => useRefreshing(disableMfa);
export const useRegenerateCodes = () => useRefreshing(regenerateRecoveryCodes);
