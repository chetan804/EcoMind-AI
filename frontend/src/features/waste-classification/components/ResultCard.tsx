import { useId, type ReactNode } from 'react';
import { ScanSearch } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Spinner } from '@/components/feedback/Loading';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import type { ActiveModel, Prediction } from '../api/schemas';
import { PredictionResult } from './PredictionResult';
import { ReviewPanel } from './ReviewPanel';

export type ResultView =
  | { kind: 'model-loading' }
  | { kind: 'model-error'; message: string; onRetry: () => void }
  | { kind: 'no-model' }
  | { kind: 'empty' }
  | { kind: 'ready'; fileName: string; unavailableReason?: string; onClassify: () => void }
  | { kind: 'analysing'; fileName: string }
  | { kind: 'error'; title: string; detail: string; onRetry: () => void }
  | { kind: 'result'; prediction: Prediction; model: ActiveModel['active']; canReview: boolean; onReviewed: (p: Prediction) => void };

/** The result panel. Every state shown here comes from the real API; nothing is a placeholder result. */
export function ResultCard({ view, onReset }: { view: ResultView; onReset: () => void }) {
  const titleId = useId();
  let body: ReactNode;
  switch (view.kind) {
    case 'model-loading':
      body = (
        <div className="result__stack" aria-busy="true">
          <Spinner label="Checking the classification model" />
          <p>Checking whether a classification model is active…</p>
        </div>
      );
      break;
    case 'model-error':
      body = (
        <div className="result__stack">
          <Alert tone="danger" title="Could not check the classification model">
            {view.message}
          </Alert>
          <Button variant="secondary" onClick={view.onRetry}>
            Try again
          </Button>
        </div>
      );
      break;
    case 'no-model':
      body = (
        <Alert tone="warning" title="No classification model is active">
          Images cannot be analysed until an administrator activates a trained model. You can still choose an image to preview it;
          nothing is uploaded.
        </Alert>
      );
      break;
    case 'empty':
      body = <EmptyState icon={<ScanSearch size={24} />} title="No image yet" description="Choose an image, then select Classify image." />;
      break;
    case 'ready':
      body = (
        <div className="result__stack">
          <p>
            “{view.fileName}” is ready. Classifying uploads the image to the server (location metadata is removed) and stores the
            result with it.
          </p>
          <div className="result__actions">
            <Button unavailableReason={view.unavailableReason} onClick={view.onClassify}>
              Classify image
            </Button>
            <Button variant="secondary" onClick={onReset}>
              Choose another image
            </Button>
          </div>
        </div>
      );
      break;
    case 'analysing':
      body = (
        <div className="result__stack" aria-busy="true">
          <Spinner label="Analysing the image" />
          <p role="status">Analysing “{view.fileName}”…</p>
        </div>
      );
      break;
    case 'error':
      body = (
        <div className="result__stack">
          <Alert tone="danger" title={view.title}>
            {view.detail}
          </Alert>
          <div className="result__actions">
            <Button onClick={view.onRetry}>Try again</Button>
            <Button variant="secondary" onClick={onReset}>
              Choose another image
            </Button>
          </div>
        </div>
      );
      break;
    case 'result':
      body = (
        <div className="result__stack">
          <PredictionResult prediction={view.prediction} model={view.model} />
          {view.canReview && view.prediction.review.status === 'unreviewed' && (
            <ReviewPanel prediction={view.prediction} onReviewed={view.onReviewed} />
          )}
          <Button variant="secondary" onClick={onReset}>
            Classify another image
          </Button>
        </div>
      );
      break;
  }
  return (
    <Card aria-labelledby={titleId} className="result">
      <CardHeader title="Classification result" titleId={titleId} />
      {body}
    </Card>
  );
}
