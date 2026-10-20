import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { pageOf, uuid } from '@/services/schemas';

export const notificationSchema = z.object({
  id: uuid,
  category: z.string(),
  title: z.string(),
  body: z.string().nullable(),
  entity_type: z.string().nullable(),
  entity_id: uuid.nullable(),
  read_at: z.string().nullable(),
  created_at: z.string(),
});
export type Notification = z.infer<typeof notificationSchema>;

const notificationPage = pageOf(notificationSchema);
const unreadSchema = z.object({ unread: z.number().int() });
const markedSchema = z.object({ marked: z.number().int() });

export const fetchNotifications = (params: { page: number; unread_only: boolean; category: string }, signal?: AbortSignal) =>
  getJson('/notifications', notificationPage, { ...params, page_size: 20 }, signal);
export const fetchUnreadCount = (signal?: AbortSignal) => getJson('/notifications/unread-count', unreadSchema, undefined, signal);
export const markRead = (id: string) => sendJson('POST', `/notifications/${id}/read`, notificationSchema);
export const markAllRead = () => sendJson('POST', '/notifications/read-all', markedSchema);
