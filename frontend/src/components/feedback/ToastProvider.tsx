import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Alert } from './Alert';
import { ToastContext, type ToastInput } from './toast-context';
import './feedback.css';

interface ActiveToast extends ToastInput {
  id: number;
}

const DISMISS_AFTER_MS = 6000;
let nextId = 0;

/** Transient confirmations. Rendered in a polite live region; each toast dismisses itself. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ActiveToast[]>([]);
  const push = useCallback((toast: ToastInput) => {
    setToasts((current) => [...current, { ...toast, id: ++nextId }]);
  }, []);
  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((t) => t.id !== id)), []);

  return (
    <ToastContext value={push}>
      {children}
      <div className="toast-region" aria-live="polite">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDone={dismiss} />
        ))}
      </div>
    </ToastContext>
  );
}

function ToastItem({ toast, onDone }: { toast: ActiveToast; onDone: (id: number) => void }) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDone(toast.id), DISMISS_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, [toast.id, onDone]);
  return (
    <Alert className="toast" tone={toast.tone ?? 'info'} title={toast.title}>
      {toast.description}
    </Alert>
  );
}
