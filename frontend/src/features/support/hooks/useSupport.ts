import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ask,
  closeTicket,
  createArticle,
  createTicket,
  fetchArticles,
  fetchCategories,
  fetchMyTickets,
  fetchQueue,
  fetchStats,
  fetchTicket,
  giveFeedback,
  replyToTicket,
  updateArticle,
  updateTicket,
  type ArticleInput,
  type NewTicket,
  type TicketPatch,
} from '../api/support-api';

export const useAsk = () => useMutation({ mutationFn: (v: { message: string; conversationId: string | null }) => ask(v.message, v.conversationId) });
export const useFeedback = () => useMutation({ mutationFn: (v: { messageId: string; helpful: boolean }) => giveFeedback(v.messageId, v.helpful) });
export const useStats = (days: number) => useQuery({ queryKey: ['support', 'stats', days], queryFn: ({ signal }) => fetchStats(days, signal) });

export const useArticles = (f: { page: number; q: string; category: string; include_unpublished: boolean }) =>
  useQuery({ queryKey: ['support', 'articles', f], queryFn: ({ signal }) => fetchArticles(f, signal) });
export const useCategories = () => useQuery({ queryKey: ['support', 'categories'], queryFn: ({ signal }) => fetchCategories(signal) });

export function useSaveArticle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string | null; slug: string; input: ArticleInput }) =>
      v.id ? updateArticle(v.id, v.input) : createArticle({ ...v.input, slug: v.slug }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['support'] }),
  });
}

export const useMyTickets = (f: { page: number; status: string }) =>
  useQuery({ queryKey: ['support', 'tickets', 'mine', f], queryFn: ({ signal }) => fetchMyTickets(f, signal) });
export const useQueue = (f: { page: number; status: string; assigned_to_me: boolean; unassigned: boolean; q: string }) =>
  useQuery({ queryKey: ['support', 'tickets', 'queue', f], queryFn: ({ signal }) => fetchQueue(f, signal) });
export const useTicket = (id: string) => useQuery({ queryKey: ['support', 'ticket', id], queryFn: ({ signal }) => fetchTicket(id, signal) });

/** Any ticket change refreshes the lists and the open ticket. */
function useTicketRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ['support', 'tickets'] }).then(() => client.invalidateQueries({ queryKey: ['support', 'ticket'] }));
}

export function useCreateTicket() {
  const refresh = useTicketRefresh();
  return useMutation({ mutationFn: (body: NewTicket) => createTicket(body), onSuccess: refresh });
}
export function useReply(id: string) {
  const refresh = useTicketRefresh();
  return useMutation({ mutationFn: (body: string) => replyToTicket(id, body), onSuccess: refresh });
}
export function useUpdateTicket(id: string) {
  const refresh = useTicketRefresh();
  return useMutation({ mutationFn: (patch: TicketPatch) => updateTicket(id, patch), onSuccess: refresh });
}
export function useCloseTicket(id: string) {
  const refresh = useTicketRefresh();
  return useMutation({ mutationFn: () => closeTicket(id), onSuccess: refresh });
}
