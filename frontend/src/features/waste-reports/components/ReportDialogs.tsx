import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { AuthImage } from '@/components/data-display/AuthImage';
import { Alert } from '@/components/feedback/Alert';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, Select, Textarea } from '@/components/ui/Input';
import { CreateTaskDialog } from '@/features/collection';
import { createPrediction, type Prediction } from '@/features/waste-classification';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, formatKg, humanize } from '@/utils/format';
import type { Report } from '../api/reports-api';
import { useCreateReport, useReport, useReviewReport } from '../hooks/useReports';
import { ReportStatusBadge } from './ReportStatusBadge';

export function CreateReportDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateReport();
  const [photo, setPhoto] = useState<File | null>(null);
  const { values, bind } = useFields({ title: '', description: '', address_text: '', latitude: '', longitude: '', weight: '' });
  const coordsOk = (values.latitude.trim() === '') === (values.longitude.trim() === '');
  const valid = values.title.trim().length >= 3 && coordsOk;
  const submit = () =>
    create.mutate(
      {
        photo,
        body: {
          title: values.title.trim(),
          description: optional(values.description),
          address_text: optional(values.address_text),
          latitude: optional(values.latitude),
          longitude: optional(values.longitude),
          estimated_weight_kg: optional(values.weight),
        },
      },
      { onSuccess: onClose },
    );
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Report waste"
      description="Describe what needs collecting. A photo helps reviewers and can be classified."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!valid} onClick={submit}>Submit report</Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Title">{(c) => <Input {...c} data-autofocus {...bind('title')} />}</Field>
        <Field label="Address or landmark">{(c) => <Input {...c} {...bind('address_text')} />}</Field>
        <Field label="Latitude (optional)" error={coordsOk ? undefined : 'Give both latitude and longitude, or neither.'}>{(c) => <Input {...c} inputMode="decimal" {...bind('latitude')} />}</Field>
        <Field label="Longitude (optional)">{(c) => <Input {...c} inputMode="decimal" {...bind('longitude')} />}</Field>
        <Field label="Estimated weight, kg (optional)">{(c) => <Input {...c} inputMode="decimal" {...bind('weight')} />}</Field>
        <Field label="Photo (optional)" hint="JPEG, PNG or WebP. Location metadata is removed.">
          {(c) => <Input {...c} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />}
        </Field>
      </div>
      <Field label="Description (optional)">{(c) => <Textarea {...c} maxLength={4000} {...bind('description')} />}</Field>
      {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
    </Dialog>
  );
}

export function ReportDialog({ reportId, onClose }: { reportId: string; onClose: () => void }) {
  const query = useReport(reportId);
  return (
    <Dialog open wide onClose={onClose} title="Waste report" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <QueryBoundary query={query} label="the report">{(report) => <ReportBody report={report} />}</QueryBoundary>
    </Dialog>
  );
}

const REVIEW_TARGETS = ['under_review', 'verified', 'rejected', 'closed'] as const;

function ReportBody({ report }: { report: Report }) {
  const { can } = useAuth();
  const [reviewing, setReviewing] = useState(false);
  const [creatingTask, setCreatingTask] = useState(false);

  return (
    <div className="stack stack--tight">
      <div>
        <h3 className="task__title">{report.title}</h3>
        <ReportStatusBadge value={report.status} />
      </div>
      <dl className="detail-list">
        <dt>Reported</dt><dd>{formatDateTime(report.reported_at)}</dd>
        <dt>Place</dt><dd>{report.address_text ?? (report.latitude !== null ? `${report.latitude}, ${report.longitude}` : '—')}</dd>
        <dt>Estimated weight</dt><dd>{report.estimated_weight_kg === null ? 'Not given' : formatKg(report.estimated_weight_kg)}</dd>
        {report.description && (<><dt>Description</dt><dd>{report.description}</dd></>)}
      </dl>

      <section aria-label="Photos">
        <h4>Photos</h4>
        {report.media.length === 0 ? <p className="muted">No photo attached.</p> : report.media.map((m, i) => (
          <div key={m.id} className="stack stack--tight">
            <AuthImage contentPath={m.content_path} alt={`Photo ${i + 1} for ${report.title}`} width={m.width_px ?? undefined} height={m.height_px ?? undefined} />
            {can('classification:predict') && <ClassifyPhoto mediaId={m.id} />}
          </div>
        ))}
      </section>

      <div className="row-actions">
        {can('waste_reports:review') && report.status !== 'closed' && (
          <Button variant="secondary" onClick={() => setReviewing(true)}>Review report</Button>
        )}
        {can('collection:manage') && report.status === 'verified' && <Button onClick={() => setCreatingTask(true)}>Create collection task</Button>}
      </div>

      {reviewing && <ReviewDialog report={report} onClose={() => setReviewing(false)} />}
      {creatingTask && (
        <CreateTaskDialog wasteReportId={report.id} defaultTitle={report.title} defaultAddress={report.address_text ?? ''} onClose={() => setCreatingTask(false)} />
      )}
    </div>
  );
}

function ClassifyPhoto({ mediaId }: { mediaId: string }) {
  const classify = useMutation({ mutationFn: () => createPrediction(mediaId) });
  const p: Prediction | undefined = classify.data;
  return (
    <div>
      <Button variant="secondary" loading={classify.isPending} onClick={() => classify.mutate()}>Classify photo</Button>
      {classify.isError && <Alert tone="danger">{getErrorMessage(classify.error)}</Alert>}
      {p && (
        <p role="status">
          Suggested category: <strong>{p.material_category.name}</strong> ({Math.round(p.confidence * 100)}% calibrated confidence, model {p.model_name} {p.model_version}).
          {p.needs_review && ' Low confidence: a reviewer should check this.'}
        </p>
      )}
    </div>
  );
}

function ReviewDialog({ report, onClose }: { report: Report; onClose: () => void }) {
  const review = useReviewReport(report.id);
  const { values, bind } = useFields({ status: 'verified', reason: '' });
  const needsReason = values.status === 'rejected';
  const reason = values.reason.trim();
  return (
    <Dialog
      open
      onClose={onClose}
      title="Review report"
      description="Verified reports can be turned into collection tasks. Rejecting needs a reason, which is recorded."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={review.isPending}
            disabled={needsReason && reason.length < 3}
            onClick={() => review.mutate({ status: values.status, reason: reason || undefined }, { onSuccess: onClose })}
          >
            Save review
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="New status">
          {(c) => <Select {...c} data-autofocus {...bind('status')}>{REVIEW_TARGETS.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>}
        </Field>
        <Field label={needsReason ? 'Reason (required)' : 'Reason (optional)'}>{(c) => <Textarea {...c} maxLength={1000} {...bind('reason')} />}</Field>
        {review.isError && <Alert tone="danger">{getErrorMessage(review.error)}</Alert>}
      </div>
    </Dialog>
  );
}
