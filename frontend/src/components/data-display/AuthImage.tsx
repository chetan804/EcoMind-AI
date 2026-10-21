import { useQuery } from '@tanstack/react-query';
import { apiBlob } from '@/services/api-client';
import { getErrorMessage } from '@/services/error-handler';

async function toDataUrl(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return `data:${blob.type || 'application/octet-stream'};base64,${btoa(binary)}`;
}

/**
 * Shows a stored photo. The file endpoints need the session's bearer token, so a plain `<img src>`
 * would be refused; the bytes are fetched through `apiBlob` and shown as a data URL (no object URL
 * to revoke, so it is safe under React StrictMode).
 */
export function AuthImage({
  contentPath,
  alt,
  width,
  height,
  className = 'photo-thumb',
}: {
  contentPath: string;
  alt: string;
  width?: number;
  height?: number;
  className?: string;
}) {
  const image = useQuery({
    queryKey: ['media', contentPath],
    queryFn: async ({ signal }) => toDataUrl(await apiBlob(contentPath, { versioned: false, signal })),
    staleTime: Infinity,
    gcTime: 60_000,
  });
  if (image.isError) return <p className="muted">Photo unavailable: {getErrorMessage(image.error)}</p>;
  if (!image.data) return <p className="muted" role="status">Loading photo…</p>;
  return <img className={className} src={image.data} alt={alt} width={width} height={height} />;
}
