import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Link } from 'react-router';
import { ChevronDown } from 'lucide-react';
import { cx } from '@/utils/cx';
import './overlay.css';

export interface MenuItem {
  id: string;
  label: string;
  icon?: ReactNode;
  /** Navigates to a route. */
  to?: string;
  /** Runs an action. Exactly one of `to` or `onSelect` should be given. */
  onSelect?: () => void;
}

/** Dropdown menu button (WAI-ARIA menu button pattern): arrows, Home/End, Escape, outside click. */
export function Menu({
  label,
  trigger,
  items,
  align = 'start',
}: {
  /** Accessible name of the trigger button. */
  label: string;
  /** Visible trigger content (an avatar, text, ...). */
  trigger: ReactNode;
  items: MenuItem[];
  align?: 'start' | 'end';
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLElement | null>>([]);
  /** Index to focus once the list has rendered (set when opened from the keyboard). */
  const pendingFocus = useRef<number | null>(null);

  const count = items.length;
  const focusItem = useCallback(
    (index: number) => itemRefs.current[(index + count) % count]?.focus(),
    [count],
  );

  useEffect(() => {
    if (open && pendingFocus.current !== null) {
      focusItem(pendingFocus.current);
      pendingFocus.current = null;
    }
  }, [open, focusItem]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  const close = (restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  };

  const onTriggerKey = (event: KeyboardEvent) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      pendingFocus.current = event.key === 'ArrowDown' ? 0 : -1;
      setOpen(true);
    }
  };

  const onListKey = (event: KeyboardEvent) => {
    const current = itemRefs.current.indexOf(document.activeElement as HTMLElement);
    if (event.key === 'ArrowDown') focusItem(current + 1);
    else if (event.key === 'ArrowUp') focusItem(current - 1);
    else if (event.key === 'Home') focusItem(0);
    else if (event.key === 'End') focusItem(-1);
    else if (event.key === 'Tab') close(false);
    else return;
    if (event.key !== 'Tab') event.preventDefault();
  };

  return (
    <div
      className="menu"
      ref={root}
      onKeyDown={(event) => {
        // Escape closes the menu wherever focus is (trigger or item) and returns focus to the trigger.
        if (open && event.key === 'Escape') {
          event.preventDefault();
          close(true);
        }
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        className="menu__trigger"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={(event) => {
          // detail === 0: activated from the keyboard (Enter/Space), so move focus into the menu.
          if (!open && event.detail === 0) pendingFocus.current = 0;
          setOpen((o) => !o);
        }}
        onKeyDown={onTriggerKey}
      >
        {trigger}
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      {open && (
        <div id={id} role="menu" aria-label={label} className={cx('menu__list', align === 'end' && 'menu__list--end')} onKeyDown={onListKey}>
          {items.map((item, index) => {
            const common = {
              role: 'menuitem',
              tabIndex: -1,
              className: 'menu__item',
              ref: (node: HTMLElement | null) => {
                itemRefs.current[index] = node;
              },
            } as const;
            const content = (
              <>
                {item.icon}
                {item.label}
              </>
            );
            return item.to ? (
              <Link key={item.id} {...common} to={item.to} onClick={() => close(false)}>
                {content}
              </Link>
            ) : (
              <button
                key={item.id}
                {...common}
                type="button"
                onClick={() => {
                  item.onSelect?.();
                  close(true);
                }}
              >
                {content}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
