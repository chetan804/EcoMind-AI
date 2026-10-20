import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ClipboardCheck } from 'lucide-react';
import { AuthImage } from '@/components/data-display/AuthImage';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Table';
import { humanize } from '@/utils/format';
import { predictionImagePath, type QueueFilters } from '../api/classification-api';
import type { QueuedPrediction } from '../api/schemas';
import { ReviewPanel } from '../components/ReviewPanel';
import { useReviewQueue } from '../hooks/useClassification';
import { percent, REVIEW_REASON_TEXT } from '../utils';

const VIEWS: Array<{ value: QueueFilters['review_status']; label: string }> = [
  { value: 'unreviewed', label: 'Awaiting review' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'corrected', label: 'Corrected' },
  { value: 'rejected', label: 'Rejected' },
];

/** Work queue for reviewers: the model's suggestions that a person still has to judge (`classification:review`). */
export function ReviewQueuePage() {
  const [filters, setFilters] = useState<QueueFilters>({ page: 1, review_status: 'unreviewed' });
  const query = useReviewQueue(filters);
  const client = useQueryClient();

  return (
    <section aria-labelledby="queue-title" className="stack stack--tight">
      <PageHeader
        title="Prediction review queue"
        titleId="queue-title"
        subtitle="Judge the model's suggestions against the photo. Confirmed and corrected results are recorded; the model's own output is never rewritten."
      />
      <div className="filter-bar">
        <Field label="Show">
          {(c) => (
            <Select {...c} value={filters.review_status} onChange={(e) => setFilters({ page: 1, review_status: e.target.value as QueueFilters['review_status'] })}>
              {VIEWS.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="predictions to review">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState
              icon={<ClipboardCheck size={24} />}
              title={filters.review_status === 'unreviewed' ? 'Nothing is waiting for review' : 'No predictions here yet'}
              description={filters.review_status === 'unreviewed' ? 'Predictions the model is unsure about, or images unlike its training photos, appear here.' : 'No prediction has this review outcome.'}
            />
          ) : (
            <>
              <ul className="stack" aria-label="Predictions">
                {data.items.map((p) => (
                  <li key={p.id}>
                    <QueueItem prediction={p} onReviewed={() => void client.invalidateQueries({ queryKey: ['classification', 'queue'] })} />
                  </li>
                ))}
              </ul>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} prediction${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
    </section>
  );
}

function QueueItem({ prediction: p, onReviewed }: { prediction: QueuedPrediction; onReviewed: () => void }) {
  const reviewed = p.review.status !== 'unreviewed';
  return (
    <Card>
      <div className="review-item">
        <AuthImage contentPath={predictionImagePath(p.id)} alt={`Photo classified as ${humanize(p.material_category.code)}`} />
        <div className="stack stack--tight">
          <p>
            <strong>Suggested: {humanize(p.material_category.code)}</strong> at {percent(p.confidence)} calibrated confidence{' '}
            <Badge tone="neutral">{p.model_name} {p.model_version}</Badge>
          </p>
          {p.review_reasons.length > 0 && (
            <ul className="muted">
              {p.review_reasons.map((r) => <li key={r}>{REVIEW_REASON_TEXT[r] ?? humanize(r)}</li>)}
            </ul>
          )}
          {reviewed ? (
            <p>
              <Badge tone="info">{humanize(p.review.status)}</Badge>
              {p.review.corrected_category && <> as {humanize(p.review.corrected_category.code)}</>}
              {p.review.notes && <span className="muted"> · {p.review.notes}</span>}
            </p>
          ) : (
            <ReviewPanel prediction={p} onReviewed={onReviewed} />
          )}
        </div>
      </div>
    </Card>
  );
}
