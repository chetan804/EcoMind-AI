import { MAX_IMAGE_BYTES, validateImageFile } from '@/features/waste-classification/schemas/image-file';

const file = (type: string, size: number) => new File([new Uint8Array(size)], 'x', { type });

describe('validateImageFile', () => {
  it.each(['image/jpeg', 'image/png', 'image/webp'])('accepts %s', (type) => {
    expect(validateImageFile(file(type, 10))).toBeNull();
  });

  it('rejects other types', () => {
    expect(validateImageFile(file('application/pdf', 10))).toBe('Use a JPEG, PNG or WebP image.');
    expect(validateImageFile(file('image/gif', 10))).toBe('Use a JPEG, PNG or WebP image.');
  });

  it('rejects empty and oversized files, accepting exactly the limit', () => {
    expect(validateImageFile(file('image/png', 0))).toBe('The file is empty.');
    expect(validateImageFile(file('image/png', MAX_IMAGE_BYTES + 1))).toMatch(/larger than 5 MB/);
    expect(validateImageFile(file('image/png', MAX_IMAGE_BYTES))).toBeNull();
  });
});
