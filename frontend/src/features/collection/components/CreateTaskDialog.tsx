import { Alert } from '@/components/feedback/Alert';
import { optional, useFields } from '@/components/forms/useFields';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, Select, Textarea } from '@/components/ui/Input';
import { useFacilityOptions } from '@/features/facilities';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { humanize } from '@/utils/format';
import { PRIORITIES } from '../api/collection-api';
import { useCreateTask } from '../hooks/useCollection';
import { toIsoFromLocal } from './datetime';

/** Create a collection task, optionally for a verified waste report (then the report supplies title and place). */
export function CreateTaskDialog({
  wasteReportId,
  defaultTitle = '',
  defaultAddress = '',
  onClose,
  onCreated,
}: {
  wasteReportId?: string;
  defaultTitle?: string;
  defaultAddress?: string;
  onClose: () => void;
  onCreated?: () => void;
}) {
  const { can } = useAuth();
  const facilities = useFacilityOptions(can('facilities:read'));
  const create = useCreateTask();
  const { values, bind } = useFields({
    title: defaultTitle,
    address_text: defaultAddress,
    latitude: '',
    longitude: '',
    priority: 'normal',
    due: '',
    facility: '',
    notes: '',
  });
  const hasPlace = values.address_text.trim() !== '' || (values.latitude.trim() !== '' && values.longitude.trim() !== '');
  const valid = (wasteReportId !== undefined || values.title.trim().length >= 3) && (wasteReportId !== undefined || hasPlace);

  const submit = () =>
    create.mutate(
      {
        waste_report_id: wasteReportId,
        title: optional(values.title),
        address_text: optional(values.address_text),
        latitude: optional(values.latitude),
        longitude: optional(values.longitude),
        priority: values.priority,
        due_at: values.due ? toIsoFromLocal(values.due) : undefined,
        destination_facility_id: values.facility || undefined,
        notes: optional(values.notes),
      },
      {
        onSuccess: () => {
          onCreated?.();
          onClose();
        },
      },
    );

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="New collection task"
      description={wasteReportId ? 'For the selected waste report. The report must be verified.' : 'A task needs a title and an address or coordinates.'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!valid} onClick={submit}>Create task</Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Title">{(c) => <Input {...c} data-autofocus {...bind('title')} />}</Field>
        <Field label="Priority">{(c) => <Select {...c} {...bind('priority')}>{PRIORITIES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}</Select>}</Field>
        <Field label="Address">{(c) => <Input {...c} {...bind('address_text')} />}</Field>
        <Field label="Due (optional)">{(c) => <Input {...c} type="datetime-local" {...bind('due')} />}</Field>
        <Field label="Latitude (optional)">{(c) => <Input {...c} inputMode="decimal" {...bind('latitude')} />}</Field>
        <Field label="Longitude (optional)">{(c) => <Input {...c} inputMode="decimal" {...bind('longitude')} />}</Field>
        <Field label="Deliver to (optional)">
          {(c) => (
            <Select {...c} {...bind('facility')}>
              <option value="">Decide later</option>
              {(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Notes (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('notes')} />}</Field>
      </div>
      {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
    </Dialog>
  );
}
