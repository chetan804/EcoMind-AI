import { FlaskConical } from 'lucide-react';
import './feedback.css';

/**
 * Marks content that is illustrative sample data, not live operational data. Every region that
 * renders fixtures must show this (or sit directly under a region that does).
 */
export function DemoDataNotice({ children = 'Demonstration data, not live' }: { children?: string }) {
  return (
    <span className="demo-notice">
      <FlaskConical size={14} aria-hidden="true" />
      {children}
    </span>
  );
}
