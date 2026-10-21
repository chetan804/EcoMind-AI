import { z } from 'zod';
import { getJson, sendJson, type QueryParams } from '@/services/list-api';
import { pageOf, timestamp, uuid } from '@/services/schemas';

// -- vocabulary (mirrors backend/app/modules/support/constants.py) ----------------------------
export const TICKET_STATUSES = ['open', 'in_progress', 'resolved', 'closed'] as const;
export type TicketStatus = (typeof TICKET_STATUSES)[number];

/**
 * The edges the server allows. Used only to offer sensible choices; the server enforces them and
 * a refused change shows the server's message.
 */
export const TICKET_TRANSITIONS: Record<TicketStatus, readonly TicketStatus[]> = {
  open: ['in_progress', 'resolved', 'closed'],
  in_progress: ['open', 'resolved', 'closed'],
  resolved: ['open', 'closed'],
  closed: [],
};

export const MESSAGE_KINDS = ['question', 'knowledge', 'account_data', 'no_answer', 'not_permitted'] as const;
export type MessageKind = (typeof MESSAGE_KINDS)[number];

// -- assistant ---------------------------------------------------------------------------------
export const sourceSchema = z.object({
  kind: z.enum(['article', 'sorting_guidance', 'account']),
  id: uuid.nullable().optional(),
  title: z.string(),
});
export type Source = z.infer<typeof sourceSchema>;

export const messageSchema = z.object({
  id: uuid,
  role: z.enum(['user', 'assistant']),
  kind: z.enum(MESSAGE_KINDS),
  content: z.string(),
  sources: z.array(sourceSchema),
  helpful: z.boolean().nullable(),
  created_at: timestamp,
});
export type Message = z.infer<typeof messageSchema>;

export const askResponseSchema = z.object({
  conversation_id: uuid,
  question: messageSchema,
  reply: messageSchema,
  suggest_ticket: z.boolean(),
});
export type AskResponse = z.infer<typeof askResponseSchema>;

export const statsSchema = z.object({
  since: timestamp,
  questions: z.number().int(),
  answered_from_knowledge: z.number().int(),
  answered_from_account: z.number().int(),
  no_answer: z.number().int(),
  not_permitted: z.number().int(),
  rated: z.number().int(),
  rated_helpful: z.number().int(),
});

export const ask = (message: string, conversationId: string | null) =>
  sendJson('POST', '/support/assistant/messages', askResponseSchema, { message, conversation_id: conversationId ?? undefined });
export const giveFeedback = (messageId: string, helpful: boolean) =>
  sendJson('POST', `/support/assistant/messages/${messageId}/feedback`, messageSchema, { helpful });
export const fetchStats = (days: number, signal?: AbortSignal) => getJson('/support/assistant/stats', statsSchema, { days }, signal);

// -- knowledge base ----------------------------------------------------------------------------
export const articleSchema = z.object({
  id: uuid,
  slug: z.string(),
  title: z.string(),
  body: z.string(),
  category: z.string(),
  keywords: z.string(),
  source: z.string(),
  published: z.boolean(),
  updated_at: timestamp,
});
export type Article = z.infer<typeof articleSchema>;

export interface ArticleInput {
  title: string;
  body: string;
  category: string;
  source: string;
  keywords: string;
  published: boolean;
}

export const fetchArticles = (f: { page: number; q: string; category: string; include_unpublished: boolean }, signal?: AbortSignal) =>
  getJson('/support/articles', pageOf(articleSchema), { page_size: 20, ...f }, signal);
export const fetchCategories = (signal?: AbortSignal) => getJson('/support/articles/categories', z.array(z.string()), undefined, signal);
export const createArticle = (body: ArticleInput & { slug: string }) => sendJson('POST', '/support/articles', articleSchema, body);
export const updateArticle = (id: string, body: Partial<ArticleInput>) => sendJson('PATCH', `/support/articles/${id}`, articleSchema, body);

// -- tickets -----------------------------------------------------------------------------------
export const ticketSchema = z.object({
  id: uuid,
  user_id: uuid,
  requester_name: z.string().nullable().optional(),
  subject: z.string(),
  status: z.enum(TICKET_STATUSES),
  assignee_id: uuid.nullable(),
  assignee_name: z.string().nullable(),
  reply_count: z.number().int(),
  conversation_shared: z.boolean(),
  created_at: timestamp,
  updated_at: timestamp,
  resolved_at: timestamp.nullable(),
});
export type Ticket = z.infer<typeof ticketSchema>;

export const replySchema = z.object({
  id: uuid,
  author_id: uuid,
  author_name: z.string(),
  is_staff: z.boolean(),
  body: z.string(),
  created_at: timestamp,
});

export const ticketDetailSchema = ticketSchema.extend({
  body: z.string(),
  replies: z.array(replySchema),
  conversation: z.array(messageSchema).nullable().optional(),
});
export type TicketDetail = z.infer<typeof ticketDetailSchema>;

export interface NewTicket {
  subject: string;
  body: string;
  conversation_id?: string;
  share_conversation: boolean;
}

export interface TicketPatch {
  status?: TicketStatus;
  assign_to_me?: boolean;
  unassign?: boolean;
}

export const fetchMyTickets = (f: { page: number; status: string }, signal?: AbortSignal) =>
  getJson('/support/tickets/mine', pageOf(ticketSchema), { page_size: 20, ...f }, signal);
export const fetchQueue = (
  f: { page: number; status: string; assigned_to_me: boolean; unassigned: boolean; q: string },
  signal?: AbortSignal,
) => getJson('/support/tickets', pageOf(ticketSchema), { page_size: 20, ...f } as QueryParams, signal);
export const fetchTicket = (id: string, signal?: AbortSignal) => getJson(`/support/tickets/${id}`, ticketDetailSchema, undefined, signal);
export const createTicket = (body: NewTicket) => sendJson('POST', '/support/tickets', ticketDetailSchema, body);
export const replyToTicket = (id: string, body: string) => sendJson('POST', `/support/tickets/${id}/replies`, ticketDetailSchema, { body });
export const updateTicket = (id: string, patch: TicketPatch) => sendJson('PATCH', `/support/tickets/${id}`, ticketDetailSchema, patch);
export const closeTicket = (id: string) => sendJson('POST', `/support/tickets/${id}/close`, ticketDetailSchema);
