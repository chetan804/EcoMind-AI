import { useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, Select, Textarea } from '@/components/ui/Input';
import { ReasonDialog } from '@/components/ui/ReasonDialog';
import { useFacilityOptions } from '@/features/facilities';
import { useVehicleOptions } from '@/features/fleet';
import { CollectionTrackMap } from '@/features/tracking';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, formatKg, humanize } from '@/utils/format';
import { EVENT_TYPES, type TaskDetail } from '../api/collection-api';
import { useCollectors, useTask, useTaskAction } from '../hooks/useCollection';
import { PriorityBadge, TaskStatusBadge } from './badges';
import { toIsoFromLocal } from './datetime';

type Mode = null | 'assign' | 'complete' | 'fail' | 'cancel' | 'reschedule' | 'event';

export function TaskDialog({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const query = useTask(taskId);
  return (
    <Dialog open wide onClose={onClose} title="Collection task" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <QueryBoundary query={query} label="the task">{(task) => <TaskBody task={task} />}</QueryBoundary>
    </Dialog>
  );
}

function TaskBody({ task }: { task: TaskDetail }) {
  const { can, user } = useAuth();
  const [mode, setMode] = useState<Mode>(null);
  const action = useTaskAction(task.id);
  const manage = can('collection:manage');
  const assignee = task.assignment && !task.assignment.unassigned_at ? task.assignment : null;
  const isMine = assignee?.assignee_id === user?.id;
  const canWork = manage || (can('collection:execute') && isMine);
  const close = () => {
    setMode(null);
    action.reset();
  };
  const run = (name: Parameters<typeof action.mutate>[0]['action'], body?: Record<string, unknown>) =>
    action.mutate({ action: name, body }, { onSuccess: close });

  return (
    <div className="stack stack--tight">
      <div>
        <h3 className="task__title">{task.title}</h3>
        <p className="task__meta">
          <TaskStatusBadge value={task.status} /> <PriorityBadge value={task.priority} />
        </p>
      </div>
      <dl className="detail-list">
        <dt>Address</dt><dd>{task.address_text ?? (task.latitude !== null ? `${task.latitude}, ${task.longitude}` : '—')}</dd>
        <dt>Due</dt><dd>{formatDateTime(task.due_at)}</dd>
        <dt>Assigned to</dt><dd>{assignee ? `${assignee.assignee_name}${assignee.vehicle_registration ? `, vehicle ${assignee.vehicle_registration}` : ''}` : 'Nobody yet'}</dd>
        <dt>Collected weight</dt><dd>{task.collected_weight_kg == null ? 'Not recorded' : formatKg(task.collected_weight_kg)}</dd>
        {task.notes && (<><dt>Notes</dt><dd>{task.notes}</dd></>)}
      </dl>

      {task.latitude !== null && (manage || isMine) && (
        <section aria-label="Location and tracking">
          <h4>Location and tracking</h4>
          <CollectionTrackMap taskId={task.id} />
        </section>
      )}

      {action.isError && mode === null && <Alert tone="danger">{getErrorMessage(action.error)}</Alert>}

      <div className="row-actions">
        {manage && (task.status === 'pending' || task.status === 'assigned') && (
          <Button variant="secondary" onClick={() => setMode('assign')}>{task.status === 'pending' ? 'Assign' : 'Re-assign'}</Button>
        )}
        {canWork && task.status === 'assigned' && (
          <Button loading={action.isPending && mode === null} onClick={() => action.mutate({ action: 'start' })}>Start task</Button>
        )}
        {canWork && (task.status === 'assigned' || task.status === 'in_progress') && (
          <Button variant="secondary" onClick={() => setMode('event')}>Log event</Button>
        )}
        {canWork && task.status === 'in_progress' && <Button onClick={() => setMode('complete')}>Complete with weight</Button>}
        {canWork && (task.status === 'assigned' || task.status === 'in_progress') && (
          <Button variant="secondary" onClick={() => setMode('fail')}>Mark as failed</Button>
        )}
        {manage && (task.status === 'pending' || task.status === 'assigned' || task.status === 'in_progress') && (
          <Button variant="danger" onClick={() => setMode('cancel')}>Cancel task</Button>
        )}
        {manage && task.status === 'failed' && <Button variant="secondary" onClick={() => setMode('reschedule')}>Reschedule</Button>}
      </div>

      <section aria-label="Field events">
        <h4>Field events</h4>
        {task.events.length === 0 ? <p className="muted">No events logged.</p> : (
          <ul className="timeline">
            {task.events.map((e) => (
              <li key={e.id}>
                <strong>{humanize(e.event_type)}</strong> · {formatDateTime(e.occurred_at)}
                {e.collected_weight_kg != null && ` · ${formatKg(e.collected_weight_kg)}`}
                {e.notes && <span className="muted"> · {e.notes}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-label="Status history">
        <h4>Status history</h4>
        <ul className="timeline">
          {task.history.map((h) => (
            <li key={h.id}>
              {h.from_status ? `${humanize(h.from_status)} → ` : ''}<strong>{humanize(h.to_status)}</strong> · {formatDateTime(h.created_at)}
              {h.note && <span className="muted"> · {h.note}</span>}
            </li>
          ))}
        </ul>
      </section>

      {mode === 'assign' && <AssignDialog task={task} pending={action.isPending} error={action.error} onSubmit={(b) => run('assign', b)} onClose={close} />}
      {mode === 'complete' && <CompleteDialog task={task} pending={action.isPending} error={action.error} onSubmit={(b) => run('complete', b)} onClose={close} />}
      {mode === 'event' && <EventDialog pending={action.isPending} error={action.error} onSubmit={(b) => run('events', b)} onClose={close} />}
      {mode === 'reschedule' && <RescheduleDialog pending={action.isPending} error={action.error} onSubmit={(b) => run('reschedule', b)} onClose={close} />}
      {mode === 'fail' && (
        <ReasonDialog title="Mark task as failed" description="Say why the collection could not be done. The task can be rescheduled afterwards." submitLabel="Mark as failed" pending={action.isPending} error={action.error} onSubmit={(reason) => run('fail', { reason })} onClose={close} />
      )}
      {mode === 'cancel' && (
        <ReasonDialog title="Cancel task" description="Cancelled tasks cannot be reopened." submitLabel="Cancel task" destructive pending={action.isPending} error={action.error} onSubmit={(reason) => run('cancel', { reason })} onClose={close} />
      )}
    </div>
  );
}

interface SubmitProps {
  pending: boolean;
  error: unknown;
  onSubmit: (body: Record<string, unknown>) => void;
  onClose: () => void;
}

function AssignDialog({ task, pending, error, onSubmit, onClose }: SubmitProps & { task: TaskDetail }) {
  const { can } = useAuth();
  const collectors = useCollectors(can('users:read'));
  const vehicles = useVehicleOptions(can('fleet:read'));
  const { values, bind } = useFields({ assignee_id: '', vehicle_id: '', note: '' });
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Assign: ${task.title}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={pending} disabled={!values.assignee_id} onClick={() => onSubmit({ assignee_id: values.assignee_id, vehicle_id: values.vehicle_id || null, note: optional(values.note) })}>Assign</Button>
        </>
      }
    >
      <div className="stack stack--tight">
        {!can('users:read') && <Alert tone="warning">Your role cannot list users, so collectors cannot be chosen here.</Alert>}
        <Field label="Collector">
          {(c) => (
            <Select {...c} data-autofocus {...bind('assignee_id')}>
              <option value="">Choose a collector</option>
              {(collectors.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Vehicle (optional)">
          {(c) => (
            <Select {...c} {...bind('vehicle_id')}>
              <option value="">No vehicle</option>
              {(vehicles.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.registration_number} ({humanize(v.status)}, {v.capacity_kg} kg)</option>)}
            </Select>
          )}
        </Field>
        <Field label="Note (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('note')} />}</Field>
        {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
      </div>
    </Dialog>
  );
}

function CompleteDialog({ task, pending, error, onSubmit, onClose }: SubmitProps & { task: TaskDetail }) {
  const { can } = useAuth();
  const facilities = useFacilityOptions(can('facilities:read'));
  const { values, bind } = useFields({ weight: '', facility: task.destination_facility_id ?? '', notes: '' });
  const weight = Number(values.weight);
  return (
    <Dialog
      open
      onClose={onClose}
      title="Complete task"
      description="Record the weight actually collected. This closes the linked report and awards points to the reporter."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={pending} disabled={!(weight > 0)} onClick={() => onSubmit({ collected_weight_kg: values.weight.trim(), destination_facility_id: values.facility || null, notes: optional(values.notes) })}>Complete task</Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Collected weight (kg)" hint="Greater than 0, up to 3 decimals">{(c) => <Input {...c} data-autofocus inputMode="decimal" {...bind('weight')} />}</Field>
        <Field label="Delivered to">
          {(c) => (
            <Select {...c} {...bind('facility')}>
              <option value="">Not specified</option>
              {(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Notes (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('notes')} />}</Field>
        {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
      </div>
    </Dialog>
  );
}

function EventDialog({ pending, error, onSubmit, onClose }: SubmitProps) {
  const { values, bind } = useFields({ event_type: 'arrived', notes: '' });
  return (
    <Dialog
      open
      onClose={onClose}
      title="Log field event"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={pending} onClick={() => onSubmit({ event_type: values.event_type, notes: optional(values.notes) })}>Log event</Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Event">
          {(c) => <Select {...c} data-autofocus {...bind('event_type')}>{EVENT_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>}
        </Field>
        <Field label="Notes (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('notes')} />}</Field>
        {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
      </div>
    </Dialog>
  );
}

function RescheduleDialog({ pending, error, onSubmit, onClose }: SubmitProps) {
  const { values, bind } = useFields({ due: '', note: '' });
  return (
    <Dialog
      open
      onClose={onClose}
      title="Reschedule task"
      description="Puts the failed task back to pending with a new due time."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={pending} disabled={!values.due} onClick={() => onSubmit({ due_at: toIsoFromLocal(values.due), note: optional(values.note) })}>Reschedule</Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="New due date and time">{(c) => <Input {...c} data-autofocus type="datetime-local" {...bind('due')} />}</Field>
        <Field label="Note (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('note')} />}</Field>
        {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
      </div>
    </Dialog>
  );
}
