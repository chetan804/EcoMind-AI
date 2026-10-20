import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { UserTools } from '@/components/layout/UserTools';
import { useAuth } from '@/services/session';
import { getErrorMessage } from '@/services/error-handler';
import type { Prediction } from '../api/schemas';
import { ClassGrid } from '../components/ClassGrid';
import { ResultCard, type ResultView } from '../components/ResultCard';
import { UploadDropzone } from '../components/UploadDropzone';
import { useActiveModel, useClassifyImage } from '../hooks/useClassification';
import { validateImageFile } from '../schemas/image-file';
import { describeClassifyError } from '../utils';
import '../classification.css';

interface Selection {
  file: File;
  url: string;
}

/**
 * Classify an uploaded photo with the model the server has activated. Every result shown is the
 * server's response; with no active model, or on failure, the page says so and shows no prediction.
 */
export function ClassificationPage() {
  const { can } = useAuth();
  const model = useActiveModel();
  const classify = useClassifyImage();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState<Prediction | null>(null);

  useEffect(() => {
    const url = selection?.url;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [selection]);

  const onFile = (file: File) => {
    const problem = validateImageFile(file);
    setError(problem);
    if (problem) return;
    classify.reset();
    setReviewed(null);
    setSelection({ file, url: URL.createObjectURL(file) });
  };

  const reset = () => {
    classify.reset();
    setReviewed(null);
    setSelection(null);
    setError(null);
  };

  const activeModel = model.data?.active ?? null;
  const allowed = can('classification:predict') && can('waste_reports:create');
  const run = () => selection && classify.mutate(selection.file);
  const prediction = reviewed ?? classify.data ?? null;

  let view: ResultView;
  if (model.isPending) view = { kind: 'model-loading' };
  else if (model.isError) view = { kind: 'model-error', message: getErrorMessage(model.error), onRetry: () => void model.refetch() };
  else if (!activeModel) view = { kind: 'no-model' };
  else if (classify.isPending && selection) view = { kind: 'analysing', fileName: selection.file.name };
  else if (classify.isError) view = { kind: 'error', ...describeClassifyError(classify.error), onRetry: run };
  else if (prediction)
    view = {
      kind: 'result',
      prediction,
      model: activeModel,
      canReview: can('classification:review'),
      onReviewed: setReviewed,
    };
  else if (selection)
    view = {
      kind: 'ready',
      fileName: selection.file.name,
      unavailableReason: allowed ? undefined : 'Your role is not allowed to classify images.',
      onClassify: run,
    };
  else view = { kind: 'empty' };

  return (
    <>
      <PageHeader
        title="AI waste classification"
        subtitle="Upload an image to identify the waste material."
        actions={<UserTools />}
      />
      <div className="classify">
        <UploadDropzone
          previewUrl={selection?.url ?? null}
          fileName={selection?.file.name ?? null}
          error={error}
          busy={classify.isPending}
          onFile={onFile}
        />
        <div className="classify__side">
          <ResultCard view={view} onReset={reset} />
        </div>
        <div className="classify__wide">
          <ClassGrid />
        </div>
      </div>
    </>
  );
}
