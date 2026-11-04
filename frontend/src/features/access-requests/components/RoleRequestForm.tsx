import { useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input, Select, Textarea } from '@/components/ui/Input';
import { getErrorMessage } from '@/services/error-handler';
import { useRequestChanges } from '../hooks/useAccessRequests';
import { REQUESTABLE, type RoleKey } from '../roles';
import type { RoleRequest } from '../api/access-requests-api';

const MIN_REASON = 20;

/**
 * Ask an administrator for an operational role. Nothing is granted by submitting: the request waits
 * for a decision and the server refuses a second open request or a role the person already holds.
 */
export function RoleRequestForm({ initialRole, held }: { initialRole?: RoleKey; held: string[] }) {
  const options = REQUESTABLE.filter((r) => !held.includes(r.key));
  const first = options.find((o) => o.key === initialRole)?.key ?? options[0]?.key ?? 'collector';
  const [role, setRole] = useState<string>(first);
  const [reason, setReason] = useState('');
  const [organisation, setOrganisation] = useState('');
  const { create } = useRequestChanges();
  const valid = reason.trim().length >= MIN_REASON && options.length > 0;

  if (options.length === 0) {
    return <Alert tone="info" title="Nothing left to request">You already hold every role that can be requested.</Alert>;
  }
  return (
    <form
      className="access-form"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (!valid) return;
        create.mutate(
          { requested_role: role as RoleRequest['requested_role'], reason: reason.trim(), organisation: organisation.trim() || undefined },
          { onSuccess: () => { setReason(''); setOrganisation(''); } },
        );
      }}
    >
      <Field label="Role you need">
        {(c) => (
          <Select {...c} value={role} onChange={(e) => setRole(e.target.value)}>
            {options.map((o) => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Organisation or team (optional)">{(c) => <Input {...c} maxLength={200} value={organisation} onChange={(e) => setOrganisation(e.target.value)} />}</Field>
      <Field label="Why do you need this role?" hint={`At least ${MIN_REASON} characters. An administrator reads this before deciding.`}>
        {(c) => <Textarea {...c} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </Field>
      {create.isError && <Alert tone="danger" title="Request not sent">{getErrorMessage(create.error)}</Alert>}
      {create.isSuccess && <Alert tone="success" title="Request sent">An administrator will review it. You will get a notification with the decision.</Alert>}
      <Button type="submit" loading={create.isPending} unavailableReason={valid ? undefined : `Explain why you need the role (at least ${MIN_REASON} characters).`}>
        Send request
      </Button>
    </form>
  );
}
