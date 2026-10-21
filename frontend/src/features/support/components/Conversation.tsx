import { Badge } from '@/components/ui/Badge';
import { formatDateTime } from '@/utils/format';
import type { Message } from '../api/support-api';
import { KIND_LABEL, KIND_TONE } from './tones';

/** A read-only transcript. Text is rendered as plain text; nothing from a message is ever treated as markup. */
export function Conversation({ messages }: { messages: Message[] }) {
  return (
    <ol className="chat chat--transcript" aria-label="Conversation">
      {messages.map((m) => (
        <li key={m.id} className={m.role === 'user' ? 'chat__msg chat__msg--user' : 'chat__msg'}>
          <p className="chat__who">
            {m.role === 'user' ? 'Question' : <Badge tone={KIND_TONE[m.kind]}>{KIND_LABEL[m.kind]}</Badge>} <span className="muted">{formatDateTime(m.created_at)}</span>
          </p>
          <p className="chat__text">{m.content}</p>
        </li>
      ))}
    </ol>
  );
}
