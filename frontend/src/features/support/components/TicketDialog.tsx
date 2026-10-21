import { useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Select, Textarea } from '@/components/ui/Input';
import { getErrorMessage } from '@/services/error-handler';
import { formatDateTime, humanize } from '@/utils/format';
import { TICKET_TRANSITIONS, type TicketDetail, type TicketStatus } from '../api/support-api';
import { useCloseTicket, useReply, useTicket, useUpdateTicket } from '../hooks/useSupport';
import { Conversation } from './Conversation';
import { STATUS_TONE } from './tones';

/** One request: what was asked, the replies, and the actions that person is allowed to take. */
export function TicketDialog({ id, staff, onClose }: { id: string; staff: boolean; onClose: () => void }) {
  const query = useTicket(id);
  return (
    <Dialog open onClose={onClose} wide title={query.data ? query.data.subject : 'Support request'} footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <QueryBoundary query={query} label="the request">
        {(ticket) => <TicketBody ticket={ticket} staff={staff} />}
      </QueryBoundary>
    </Dialog>
  );
}

function TicketBody({ ticket, staff }: { ticket: TicketDetail; staff: boolean }) {
  const [text, setText] = useState('');
  const reply = useReply(ticket.id);
  const update = useUpdateTicket(ticket.id);
  const close = useCloseTicket(ticket.id);
  const closed = ticket.status === 'closed';
  const choices: TicketStatus[] = TICKET_TRANSITIONS[ticket.status] as TicketStatus[];
  const send = () => reply.mutate(text.trim(), { onSuccess: () => setText('') });
  return (
    <div className="stack stack--tight">
      <p className="ticket__meta">
        <Badge tone={STATUS_TONE[ticket.status]}>{humanize(ticket.status)}</Badge>
        {staff && ticket.requester_name ? <span> From {ticket.requester_name}.</span> : null}
        <span> Opened {formatDateTime(ticket.created_at)}.</span>
        <span> {ticket.assignee_name ? `Handled by ${ticket.assignee_name}.` : 'Not assigned yet.'}</span>
      </p>
      <p className="ticket__body">{ticket.body}</p>

      {staff && (
        <div className="filter-bar" aria-label="Handle this request">
          <Field label="Change status">
            {(c) => (
              <Select {...c} value="" disabled={closed || update.isPending} onChange={(e) => e.target.value && update.mutate({ status: e.target.value as TicketStatus })}>
                <option value="">{closed ? 'Closed (final)' : `Keep ${humanize(ticket.status).toLowerCase()}`}</option>
                {choices.map((s) => (
                  <option key={s} value={s}>
                    Mark as {humanize(s).toLowerCase()}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {!closed && (
            <Button variant="secondary" loading={update.isPending} onClick={() => update.mutate({ assign_to_me: true })}>
              Assign to me
            </Button>
          )}
          {!closed && ticket.assignee_id && (
            <Button variant="ghost" loading={update.isPending} onClick={() => update.mutate({ unassign: true })}>
              Unassign
            </Button>
          )}
        </div>
      )}
      {update.isError && <Alert tone="danger">{getErrorMessage(update.error)}</Alert>}

      <section aria-label="Replies" className="stack stack--tight">
        <h3 className="ticket__heading">Replies ({ticket.replies.length})</h3>
        {ticket.replies.length === 0 ? (
          <p className="muted">No replies yet.</p>
        ) : (
          <ul className="ticket__replies">
            {ticket.replies.map((r) => (
              <li key={r.id} className={r.is_staff ? 'ticket__reply ticket__reply--staff' : 'ticket__reply'}>
                <p className="ticket__reply-head">
                  <strong>{r.author_name}</strong> {r.is_staff && <Badge tone="info">Support team</Badge>} <span className="muted">{formatDateTime(r.created_at)}</span>
                </p>
                <p className="ticket__body">{r.body}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {ticket.conversation && ticket.conversation.length > 0 && (
        <details className="ticket__chat">
          <summary>{staff ? 'Chat the requester chose to share' : 'The chat you shared with the support team'}</summary>
          <Conversation messages={ticket.conversation} />
        </details>
      )}

      {closed ? (
        <Alert tone="info">This request is closed. Open a new request if you still need help.</Alert>
      ) : (
        <div className="stack stack--tight">
          <Field label={staff ? 'Reply to the requester' : 'Add a reply'}>
            {(c) => <Textarea {...c} rows={3} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />}
          </Field>
          {reply.isError && <Alert tone="danger">{getErrorMessage(reply.error)}</Alert>}
          {close.isError && <Alert tone="danger">{getErrorMessage(close.error)}</Alert>}
          <div className="filter-bar">
            <Button loading={reply.isPending} unavailableReason={text.trim() ? undefined : 'Write a reply first'} onClick={send}>
              Send reply
            </Button>
            {!staff && (
              <Button variant="secondary" loading={close.isPending} onClick={() => close.mutate()}>
                Close this request
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
