import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { cx } from '@/utils/cx';
import './overlay.css';

export interface TabItem {
  id: string;
  label: ReactNode;
  panel: ReactNode;
}

/** Accessible tabs: roving tabindex, arrow/Home/End keys, automatic activation. */
export function Tabs({
  items,
  label,
  defaultId,
  className,
}: {
  items: TabItem[];
  label: string;
  defaultId?: string;
  className?: string;
}) {
  const base = useId();
  const [activeId, setActiveId] = useState(defaultId ?? items[0]?.id);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const move = (event: KeyboardEvent, index: number) => {
    const last = items.length - 1;
    const target =
      event.key === 'ArrowRight' ? (index === last ? 0 : index + 1)
      : event.key === 'ArrowLeft' ? (index === 0 ? last : index - 1)
      : event.key === 'Home' ? 0
      : event.key === 'End' ? last
      : null;
    if (target === null) return;
    event.preventDefault();
    const next = items[target];
    if (!next) return;
    setActiveId(next.id);
    refs.current[next.id]?.focus();
  };

  return (
    <div className={cx('tabs', className)}>
      <div role="tablist" aria-label={label} className="tabs__list">
        {items.map((item, index) => (
          <button
            key={item.id}
            ref={(node) => {
              refs.current[item.id] = node;
            }}
            role="tab"
            type="button"
            id={`${base}-tab-${item.id}`}
            aria-selected={item.id === activeId}
            aria-controls={`${base}-panel-${item.id}`}
            tabIndex={item.id === activeId ? 0 : -1}
            className="tabs__tab"
            onClick={() => setActiveId(item.id)}
            onKeyDown={(event) => move(event, index)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {items.map((item) => (
        <div
          key={item.id}
          role="tabpanel"
          id={`${base}-panel-${item.id}`}
          aria-labelledby={`${base}-tab-${item.id}`}
          hidden={item.id !== activeId}
          tabIndex={0}
          className="tabs__panel"
        >
          {item.id === activeId ? item.panel : null}
        </div>
      ))}
    </div>
  );
}
