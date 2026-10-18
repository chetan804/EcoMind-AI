import { createContext, useContext } from 'react';
import type { AlertTone } from './Alert';

export interface ToastInput {
  tone?: AlertTone;
  title: string;
  description?: string;
}

export const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

export function useToast() {
  const push = useContext(ToastContext);
  if (!push) throw new Error('useToast must be used inside <ToastProvider>');
  return push;
}
