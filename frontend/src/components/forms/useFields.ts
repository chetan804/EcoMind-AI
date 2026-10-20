import { useState, type ChangeEvent } from 'react';

type El = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

/** Small controlled-form helper: `bind('name')` gives `value` + `onChange` for Input/Select/Textarea. */
export function useFields<T extends Record<string, string>>(initial: T) {
  const [values, setValues] = useState<T>(initial);
  const bind = (name: keyof T & string) => ({
    value: values[name],
    onChange: (e: ChangeEvent<El>) => setValues((v) => ({ ...v, [name]: e.target.value })),
  });
  return { values, bind, set: (patch: Partial<T>) => setValues((v) => ({ ...v, ...patch })) };
}

/** Optional text field: trimmed, or undefined when blank so the API receives no key. */
export const optional = (value: string): string | undefined => (value.trim() === '' ? undefined : value.trim());
