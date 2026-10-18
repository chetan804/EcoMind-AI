import { useId, useRef, useState, type DragEvent } from 'react';
import { ImagePlus, Upload } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { cx } from '@/utils/cx';
import { ACCEPTED_IMAGE_TYPES } from '../schemas/image-file';
import { SampleBottle } from './SampleBottle';

/**
 * Image picker with drag and drop. It validates and previews the file locally; it does not upload
 * anything. `previewUrl` is an object URL owned by the page.
 */
export function UploadDropzone({
  previewUrl,
  fileName,
  error,
  showSample,
  onFile,
}: {
  previewUrl: string | null;
  fileName: string | null;
  error: string | null;
  showSample: boolean;
  onFile: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const [dragging, setDragging] = useState(false);

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div
      className={cx('dropzone', dragging && 'dropzone--active')}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className="dropzone__stage">
        {previewUrl ? (
          <img className="dropzone__preview" src={previewUrl} alt={`Selected image: ${fileName ?? 'upload'}`} />
        ) : showSample ? (
          <SampleBottle />
        ) : (
          <span className="dropzone__placeholder" aria-hidden="true">
            <ImagePlus size={56} />
          </span>
        )}
      </div>
      <p className="dropzone__title" id={hintId}>
        {fileName ? fileName : 'Drag and drop an image here'}
      </p>
      <p className="dropzone__sub">JPEG, PNG or WebP, up to 5 MB</p>
      <input
        ref={inputRef}
        type="file"
        hidden
        accept={ACCEPTED_IMAGE_TYPES.join(',')}
        aria-describedby={hintId}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = ''; // allow choosing the same file again
        }}
      />
      <Button size="lg" fullWidth icon={<Upload size={20} aria-hidden="true" />} onClick={() => inputRef.current?.click()}>
        {previewUrl ? 'Choose another image' : 'Choose image'}
      </Button>
      {error && <Alert tone="danger">{error}</Alert>}
    </div>
  );
}
