import { cloneElement, useEffect, useId, useState, type ReactElement } from 'react';
import './overlay.css';

/**
 * Descriptive tooltip for a focusable child. Shown on hover and keyboard focus, dismissible
 * with Escape (WCAG 1.4.13). Never put essential information only in a tooltip.
 */
export function Tooltip({
  content,
  children,
}: {
  content: string;
  children: ReactElement<{ 'aria-describedby'?: string }>;
}) {
  const id = useId();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!visible) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setVisible(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [visible]);

  return (
    <span
      className="tooltip"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {cloneElement(children, { 'aria-describedby': id })}
      <span id={id} role="tooltip" className="tooltip__bubble" hidden={!visible}>
        {content}
      </span>
    </span>
  );
}
