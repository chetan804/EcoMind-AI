import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchNotifications, fetchUnreadCount, markAllRead, markRead } from '../api/notifications-api';

export const notificationsKey = ['notifications'] as const;

export const useNotifications = (params: { page: number; unread_only: boolean; category: string }) =>
  useQuery({ queryKey: [...notificationsKey, 'list', params], queryFn: ({ signal }) => fetchNotifications(params, signal) });

/** Polls gently so the bell reflects new notifications without a reload. Only when `enabled`. */
export const useUnreadCount = (enabled: boolean) =>
  useQuery({
    queryKey: [...notificationsKey, 'unread'],
    queryFn: ({ signal }) => fetchUnreadCount(signal),
    enabled,
    refetchInterval: 60_000,
  });

export function useMarkRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: markRead,
    onSuccess: () => client.invalidateQueries({ queryKey: notificationsKey }),
  });
}

export function useMarkAllRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: markAllRead,
    onSuccess: () => client.invalidateQueries({ queryKey: notificationsKey }),
  });
}
