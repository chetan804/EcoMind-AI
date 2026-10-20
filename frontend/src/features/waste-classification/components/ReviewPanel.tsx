import { useId, useState, type FormEvent } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Radio, RadioGroup } from '@/components/ui/Choice';
import { Select, Textarea } from '@/components/ui/Input';
import { getErrorMessage } from '@/services/error-handler';
import type { Prediction, ReviewDecision } from '../api/schemas';
import { useReviewPrediction } from '../hooks/useClassification';

/**
 * Human review of one prediction (confirm, correct or reject). Only shown to roles that hold
 * `classification:review`; the server enforces the permission and allows one review per prediction.
 */
export function ReviewPanel({ prediction, onReviewed }: { prediction: Prediction; onReviewed: (p: Prediction) => void }) {
  const [decision, setDecision] = useState<ReviewDecision>('confirmed');
  const [category, setCategory] = useState('');
  const [notes, setNotes] = useState('');
  const [missingCategory, setMissingCategory] = useState(false);
  const review = useReviewPrediction(prediction.id);
  const name = useId();
  const options = Object.keys(prediction.class_probabilities)
    .filter((code) => code !== prediction.material_category.code)
    .sort();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (decision === 'corrected' && !category) {
      setMissingCategory(true);
      return;
    }
    setMissingCategory(false);
    review.mutate(
      {
        decision,
        ...(decision === 'corrected' ? { material_category_code: category } : {}),
        ...(notes.trim() ? { notes: notes.trim() } : {}),
      },
      { onSuccess: onReviewed },
    );
  };

  return (
    <form className="review" onSubmit={submit} aria-label="Review this result">
      <RadioGroup legend="Is the suggested category right?">
        <Radio name={name} label="Yes, confirm it" checked={decision === 'confirmed'} onChange={() => setDecision('confirmed')} />
        <Radio name={name} label="No, correct it" checked={decision === 'corrected'} onChange={() => setDecision('corrected')} />
        <Radio name={name} label="Reject (not usable)" checked={decision === 'rejected'} onChange={() => setDecision('rejected')} />
      </RadioGroup>
      {decision === 'corrected' && (
        <Field label="Correct category" required error={missingCategory ? 'Choose the correct category.' : undefined}>
          {(control) => (
            <Select {...control} value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">Select a category</option>
              {options.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      <Field label="Notes (optional)">
        {(control) => <Textarea {...control} rows={2} maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} />}
      </Field>
      {review.isError && <Alert tone="danger">{getErrorMessage(review.error)}</Alert>}
      <Button type="submit" loading={review.isPending}>
        Save review
      </Button>
    </form>
  );
}
