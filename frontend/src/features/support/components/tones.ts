import type { BadgeTone } from '@/components/ui/Badge';
import type { MessageKind, TicketStatus } from '../api/support-api';

export const STATUS_TONE: Record<TicketStatus, BadgeTone> = { open: 'warning', in_progress: 'info', resolved: 'success', closed: 'neutral' };

/** How an answer was produced, in words the person understands. */
export const KIND_LABEL: Record<MessageKind, string> = {
  question: 'You',
  knowledge: 'From the help articles',
  account_data: 'From your account',
  no_answer: 'No answer found',
  not_permitted: 'Not available for your role',
};
export const KIND_TONE: Record<MessageKind, BadgeTone> = { question: 'neutral', knowledge: 'success', account_data: 'info', no_answer: 'warning', not_permitted: 'danger' };
