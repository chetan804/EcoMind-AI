import { useState } from 'react';
import { getErrorMessage } from '@/services/error-handler';
import { Alert } from '@/components/feedback/Alert';
import { Button } from './Button';
import { Dialog } from './Dialog';
import { Field } from './Field';
import { Textarea } from './Input';

/**
 * Confirm an action that takes a note or a reason (recorded server-side). `required` reasons must
 * be at least 3 characters, as the API demands. The dialog stays open and shows the server's
 * message when the action is refused.
 */
export function ReasonDialog({
  title,
  description,
  label = 'Reason',
  required = true,
  submitLabel,
  destructive = false,
  pending,
  error,
  onSubmit,
  onClose,
}: {
  title: string;
  description?: string;
  label?: string;
  required?: boolean;
  submitLabel: string;
  destructive?: boolean;
  pending: boolean;
  error: unknown;
  onSubmit: (text: string) => void;
  onClose: () => void;
}) {
  const [text, setText] = useState('');
  const trimmed = text.trim();
  const valid = required ? trimmed.length >= 3 : true;
  return (
    <Dialog
      open
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant={destructive ? 'danger' : 'primary'} loading={pending} disabled={!valid} onClick={() => onSubmit(trimmed)}>
            {submitLabel}
          </Button>
        </>
      }
    >
      <Field label={required ? `${label} (required)` : `${label} (optional)`}>
        {(c) => <Textarea {...c} data-autofocus value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} />}
      </Field>
      {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
    </Dialog>
  );
}
