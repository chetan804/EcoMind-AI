import { Box, Container, Cylinder, Newspaper, Trash2, Wine, type LucideIcon } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { ActiveModel, Prediction } from '../api/schemas';
import { percent, REVIEW_REASON_TEXT } from '../utils';

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  cardboard: Box,
  glass: Wine,
  metal: Cylinder,
  paper: Newspaper,
  plastic: Container,
  trash: Trash2,
};

const REVIEW_LABEL: Record<string, string> = {
  unreviewed: 'Not reviewed',
  confirmed: 'Confirmed by a reviewer',
  corrected: 'Corrected by a reviewer',
  rejected: 'Rejected by a reviewer',
};

/** The real model output: category, calibrated confidence, class distribution and review state. */
export function PredictionResult({ prediction, model }: { prediction: Prediction; model: ActiveModel['active'] }) {
  const Icon = CATEGORY_ICONS[prediction.material_category.code] ?? Box;
  const metrics = model?.evaluation_metrics;
  const ranked = Object.entries(prediction.class_probabilities).sort((a, b) => b[1] - a[1]);
  const reviewed = prediction.review.status !== 'unreviewed';
  return (
    <div className="result__stack">
      <div className="result__class">
        <span className="result__tile" aria-hidden="true">
          <Icon size={36} />
        </span>
        <div>
          <p className="result__name">{prediction.material_category.name}</p>
          <p className="result__caption">Suggested material category</p>
        </div>
      </div>

      <div>
        <ProgressBar
          label="Calibrated confidence"
          value={prediction.confidence * 100}
          tone={prediction.needs_review ? 'warning' : undefined}
        />
        <p className="result__confidence">
          <strong>{percent(prediction.confidence)}</strong> confidence{' '}
          <Badge tone={prediction.needs_review ? 'warning' : 'success'} dot>
            {prediction.needs_review ? 'Needs review' : 'Confident'}
          </Badge>
        </p>
      </div>

      {prediction.needs_review && (
        <ul className="result__reasons">
          {prediction.review_reasons.map((reason) => (
            <li key={reason}>{REVIEW_REASON_TEXT[reason] ?? reason}</li>
          ))}
        </ul>
      )}

      <div>
        <h3 className="result__subhead">All categories</h3>
        <ul className="result__probs">
          {ranked.map(([code, value]) => (
            <li key={code}>
              <span className="result__prob-name">{code}</span>
              <ProgressBar label={`${code} probability`} value={value * 100} />
              <span className="result__prob-value">{percent(value)}</span>
            </li>
          ))}
        </ul>
      </div>

      <dl className="result__facts">
        <div>
          <dt>Model</dt>
          <dd>
            {prediction.model_name} {prediction.model_version}
          </dd>
        </div>
        {metrics?.accuracy !== undefined && (
          <div>
            <dt>Evaluation</dt>
            <dd>
              {percent(metrics.accuracy)} accuracy on {metrics.n_test ?? 'held-out'} held-out studio photos. Not a field
              accuracy.
            </dd>
          </div>
        )}
        {prediction.inference_ms !== null && (
          <div>
            <dt>Analysis time</dt>
            <dd>{Math.round(prediction.inference_ms)} ms</dd>
          </div>
        )}
        <div>
          <dt>Review</dt>
          <dd>
            {REVIEW_LABEL[prediction.review.status] ?? prediction.review.status}
            {prediction.review.corrected_category && ` → ${prediction.review.corrected_category.name}`}
          </dd>
        </div>
      </dl>
      <p className="result__caveat">
        This is a suggestion from a model trained on studio photographs; it has not been measured on real-world
        photos{reviewed ? '' : ', so treat it as a starting point'}.
      </p>
    </div>
  );
}
