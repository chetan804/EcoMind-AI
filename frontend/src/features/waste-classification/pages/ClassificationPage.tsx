import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { UserTools } from '@/components/layout/UserTools';
import { Switch } from '@/components/ui/Choice';
import { ClassGrid } from '../components/ClassGrid';
import { ResultCard, type ResultView } from '../components/ResultCard';
import { UploadDropzone } from '../components/UploadDropzone';
import { validateImageFile } from '../schemas/image-file';
import '../classification.css';

interface Selection {
  file: File;
  url: string;
}

/**
 * Image upload and result layout. Selecting an image validates and previews it locally. There is
 * no classification service yet, so no prediction is produced; the page says so instead.
 */
export function ClassificationPage() {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layoutPreview, setLayoutPreview] = useState(false);

  useEffect(() => {
    const url = selection?.url;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [selection]);

  const onFile = (file: File) => {
    const problem = validateImageFile(file);
    setError(problem);
    if (!problem) setSelection({ file, url: URL.createObjectURL(file) });
  };

  const reset = () => {
    setSelection(null);
    setError(null);
  };

  const view: ResultView = layoutPreview
    ? { kind: 'sample' }
    : selection
      ? { kind: 'unavailable', fileName: selection.file.name }
      : { kind: 'empty' };

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
          showSample={layoutPreview && !selection}
          onFile={onFile}
        />
        <div className="classify__side">
          <ResultCard view={view} onReset={reset} />
          <Switch
            label="Show layout preview (sample content, not a model output)"
            checked={layoutPreview}
            onChange={(event) => setLayoutPreview(event.target.checked)}
          />
        </div>
        <div className="classify__wide">
          <ClassGrid />
        </div>
      </div>
    </>
  );
}
