import { useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { AuthImage } from '@/components/data-display/AuthImage';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { getErrorMessage } from '@/services/error-handler';
import { MAX_PHOTOS, photoContentPath, type Listing } from '../api/marketplace-api';
import { useDeletePhoto, useUploadPhoto } from '../hooks/useMarketplace';

const altText = (listing: Listing, index: number, caption: string | null) => caption ?? `Photo ${index + 1} of ${listing.title}`;

/** The listing's photos, as everyone who can see the listing sees them. */
export function PhotoGallery({ listing }: { listing: Listing }) {
  if (listing.photos.length === 0) return null;
  return (
    <ul className="listing-photos" aria-label="Photos" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {listing.photos.map((photo, index) => (
        <li key={photo.id} className="listing-photos__item">
          <AuthImage contentPath={photoContentPath(photo.id)} alt={altText(listing, index, photo.caption)} width={photo.width_px} height={photo.height_px} />
          {photo.caption && <p className="muted">{photo.caption}</p>}
        </li>
      ))}
    </ul>
  );
}

/** Add and remove photos (owner and managers, while the listing is a draft or published). */
export function PhotoManager({ listing }: { listing: Listing }) {
  const upload = useUploadPhoto();
  const remove = useDeletePhoto();
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState('');
  const [inputKey, setInputKey] = useState(0);
  const full = listing.photos.length >= MAX_PHOTOS;
  const error = upload.error ?? remove.error;

  return (
    <section aria-label="Manage photos" className="stack stack--tight">
      <h3 className="task__title">Photos ({listing.photos.length} of {MAX_PHOTOS})</h3>
      {listing.photos.length > 0 && (
        <ul className="request-list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {listing.photos.map((photo, index) => (
            <li key={photo.id} className="request listing-photos__row">
              <span>{photo.caption ?? `Photo ${index + 1}`}</span>
              <Button
                variant="secondary"
                disabled={remove.isPending}
                onClick={() => remove.mutate({ id: listing.id, photoId: photo.id })}
                aria-label={`Remove ${photo.caption ?? `photo ${index + 1}`}`}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
      {full ? (
        <p className="muted">A listing can have up to {MAX_PHOTOS} photos. Remove one to add another.</p>
      ) : (
        <div className="stack stack--tight">
          <Field label="Photo" hint="JPEG, PNG or WebP. Location data in the photo is removed when it is stored.">
            {(c) => <Input {...c} key={inputKey} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
          </Field>
          <Field label="Caption (optional)">{(c) => <Input {...c} maxLength={200} value={caption} onChange={(e) => setCaption(e.target.value)} />}</Field>
          <div>
            <Button
              loading={upload.isPending}
              disabled={!file}
              onClick={() => {
                if (!file) return;
                upload.mutate(
                  { id: listing.id, file, caption: caption.trim() || undefined },
                  {
                    onSuccess: () => {
                      setFile(null);
                      setCaption('');
                      setInputKey((k) => k + 1);
                    },
                  },
                );
              }}
            >
              Add photo
            </Button>
          </div>
        </div>
      )}
      {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
    </section>
  );
}
