import { useEffect, useRef, useState } from 'react';
import { Bot, ThumbsDown, ThumbsUp } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Textarea } from '@/components/ui/Input';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import type { Message } from '../api/support-api';
import { KIND_LABEL, KIND_TONE } from '../components/tones';
import { NewRequestDialog } from '../components/NewRequestDialog';
import { useAsk, useFeedback } from '../hooks/useSupport';
import '../support.css';

const STARTERS = ['How do I report a missed collection?', 'How do I redeem my points for a reward?', 'How do I turn on two-step sign-in?'] as const;

/**
 * Help assistant. It answers by quoting the platform's help articles and by reading the person's
 * own records; it does not generate text. Every answer says where it came from, and when nothing
 * trustworthy is found it says so and offers to pass the question to a person.
 */
export function AssistantPage() {
  const { can } = useAuth();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [escalate, setEscalate] = useState<string | null>(null);
  const ask = useAsk();
  const feedback = useFeedback();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [messages.length]);

  const send = (text: string) => {
    const message = text.trim();
    if (!message || ask.isPending) return;
    ask.mutate(
      { message, conversationId },
      {
        onSuccess: (r) => {
          setConversationId(r.conversation_id);
          setMessages((m) => [...m, r.question, r.reply]);
          setDraft('');
        },
      },
    );
  };

  const rate = (m: Message, helpful: boolean) =>
    feedback.mutate({ messageId: m.id, helpful }, { onSuccess: (updated) => setMessages((all) => all.map((x) => (x.id === updated.id ? updated : x))) });

  const lastQuestion = [...messages].reverse().find((m) => m.role === 'user')?.content ?? '';

  return (
    <section aria-labelledby="assistant-title" className="stack stack--tight">
      <PageHeader
        title="Help assistant"
        titleId="assistant-title"
        subtitle="Ask how EcoMind works, or about your own points, reports and requests."
        actions={can('support:ask') ? <ButtonLink variant="secondary" to="/support">Support requests</ButtonLink> : null}
      />
      <Alert tone="info">
        The assistant looks up the platform's help articles and your own records. It does not write free-form answers, so it can miss a question that is worded unusually. When it does, you can send the question to the support team.
      </Alert>

      <div className="chat">
        <div role="log" aria-live="polite" aria-label="Conversation with the assistant" className="chat__log">
          {messages.length === 0 && (
            <div className="chat__empty">
              <Bot size={28} aria-hidden="true" />
              <p>Try one of these, or type your own question.</p>
              <ul className="chat__starters" aria-label="Example questions">
                {STARTERS.map((s) => (
                  <li key={s}>
                    <Button variant="secondary" onClick={() => send(s)} loading={ask.isPending}>
                      {s}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {messages.map((m) => (
            <MessageView key={m.id} message={m} onRate={rate} onEscalate={() => setEscalate(lastQuestion)} rating={feedback.isPending} />
          ))}
          {ask.isPending && (
            <p className="muted" role="status">
              Looking that up…
            </p>
          )}
          <div ref={endRef} />
        </div>

        {ask.isError && <Alert tone="danger">{getErrorMessage(ask.error)}</Alert>}
        {feedback.isError && <Alert tone="danger">{getErrorMessage(feedback.error)}</Alert>}

        <form
          className="chat__form"
          onSubmit={(e) => {
            e.preventDefault();
            send(draft);
          }}
        >
          <Field label="Your question" hint="Up to 1000 characters. Do not type passwords.">
            {(c) => <Textarea {...c} rows={2} maxLength={1000} value={draft} onChange={(e) => setDraft(e.target.value)} />}
          </Field>
          <div className="filter-bar">
            <Button type="submit" loading={ask.isPending} unavailableReason={draft.trim() ? undefined : 'Type a question first'}>
              Ask
            </Button>
            <Button variant="ghost" onClick={() => setEscalate(lastQuestion)}>
              Contact the support team
            </Button>
          </div>
        </form>
      </div>

      {escalate !== null && (
        <NewRequestDialog
          initialSubject={escalate.slice(0, 80)}
          initialBody={escalate.length >= 10 ? escalate : ''}
          conversationId={conversationId ?? undefined}
          onClose={() => setEscalate(null)}
        />
      )}
    </section>
  );
}

function MessageView({ message, onRate, onEscalate, rating }: { message: Message; onRate: (m: Message, helpful: boolean) => void; onEscalate: () => void; rating: boolean }) {
  if (message.role === 'user') {
    return (
      <div className="chat__msg chat__msg--user">
        <p className="chat__who">You</p>
        <p className="chat__text">{message.content}</p>
      </div>
    );
  }
  const related = message.kind === 'no_answer';
  return (
    <div className="chat__msg">
      <p className="chat__who">
        <Badge tone={KIND_TONE[message.kind]}>{KIND_LABEL[message.kind]}</Badge>
      </p>
      <p className="chat__text">{message.content}</p>
      {message.sources.length > 0 && (
        <div className="chat__sources">
          <p className="chat__sources-title">{related ? 'These articles may be related (not confirmed answers):' : 'Source'}</p>
          <ul>
            {message.sources.map((s) => (
              <li key={`${s.kind}-${s.id ?? s.title}`}>{s.title}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="filter-bar">
        {related && (
          <Button variant="secondary" onClick={onEscalate}>
            Send this to the support team
          </Button>
        )}
        <span className="chat__rate" role="group" aria-label="Was this helpful?">
          <Button variant="ghost" aria-pressed={message.helpful === true} disabled={rating} icon={<ThumbsUp size={16} />} onClick={() => onRate(message, true)}>
            Helpful
          </Button>
          <Button variant="ghost" aria-pressed={message.helpful === false} disabled={rating} icon={<ThumbsDown size={16} />} onClick={() => onRate(message, false)}>
            Not helpful
          </Button>
        </span>
      </div>
    </div>
  );
}
