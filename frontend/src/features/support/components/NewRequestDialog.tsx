import { Alert } from '@/components/feedback/Alert';
import { useToast } from '@/components/feedback/toast-context';
import { useFields } from '@/components/forms/useFields';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Choice';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, Textarea } from '@/components/ui/Input';
import { getErrorMessage } from '@/services/error-handler';
import { useCreateTicket } from '../hooks/useSupport';

/**
 * Ask the support team a question. When it starts from an assistant chat, the person decides
 * whether staff may read that chat; it is not shared by default.
 */
export function NewRequestDialog({
  initialSubject = '',
  initialBody = '',
  conversationId,
  onClose,
  onCreated,
}: {
  initialSubject?: string;
  initialBody?: string;
  conversationId?: string;
  onClose: () => void;
  onCreated?: (id: string) => void;
}) {
  const { values, bind, set } = useFields({ subject: initialSubject.slice(0, 200), body: initialBody, share: '' });
  const create = useCreateTicket();
  const toast = useToast();
  const subject = values.subject.trim();
  const body = values.body.trim();
  const valid = subject.length >= 3 && body.length >= 10;
  const submit = () =>
    create.mutate(
      { subject, body, conversation_id: conversationId, share_conversation: Boolean(conversationId) && values.share === 'yes' },
      {
        onSuccess: (ticket) => {
          toast({ tone: 'success', title: 'Request sent', description: 'The support team will reply under Support.' });
          onCreated?.(ticket.id);
          onClose();
        },
      },
    );
  return (
    <Dialog
      open
      onClose={onClose}
      title="Ask the support team"
      description="A member of staff will reply here. Do not include passwords or payment details."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={create.isPending} unavailableReason={valid ? undefined : 'Enter a subject and at least 10 characters of detail'} onClick={submit}>
            Send request
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Subject" required hint="3 to 200 characters">
          {(c) => <Input {...c} data-autofocus maxLength={200} {...bind('subject')} />}
        </Field>
        <Field label="What do you need help with?" required hint="At least 10 characters">
          {(c) => <Textarea {...c} rows={5} maxLength={4000} {...bind('body')} />}
        </Field>
        {conversationId && (
          <Checkbox
            label="Let the support team read my chat with the assistant"
            checked={values.share === 'yes'}
            onChange={(e) => set({ share: e.target.checked ? 'yes' : '' })}
          />
        )}
        {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
      </div>
    </Dialog>
  );
}
