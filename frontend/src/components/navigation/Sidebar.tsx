import { useEffect, useRef } from 'react';
import { Link, NavLink } from 'react-router';
import { X } from 'lucide-react';
import { cx } from '@/utils/cx';
import { Brand } from '@/components/layout/BrandMark';
import { IconButton } from '@/components/ui/IconButton';
import { primaryNav, secondaryNav, type NavItem } from './nav-items';
import '@/components/layout/layout.css';

function NavEntry({ item }: { item: NavItem }) {
  const Icon = item.icon;
  const planned = item.status === 'planned';
  return (
    <NavLink to={item.to} className={cx('nav-link', planned && 'nav-link--planned')}>
      <Icon size={20} aria-hidden="true" />
      {item.label}
      {planned && (
        <span className="nav-link__soon" title="Planned: not built yet">
          Soon
        </span>
      )}
    </NavLink>
  );
}

/**
 * Primary navigation. Below 1024px it is an off-canvas drawer controlled by the shell
 * (`open`/`onClose`); while closed it is `visibility: hidden`, so it is not focusable.
 */
export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <aside className={cx('sidebar', open && 'sidebar--open')} aria-label="Primary">
      <div className="sidebar__brand">
        <Link to="/" className="brand" aria-label="EcoMind AI home">
          <Brand />
        </Link>
        <span className="sidebar__close">
          <IconButton ref={closeRef} label="Close navigation" icon={<X size={20} aria-hidden="true" />} onClick={onClose} />
        </span>
      </div>
      <nav className="sidebar__nav" aria-label="Main">
        {primaryNav.map((item) => (
          <NavEntry key={item.id} item={item} />
        ))}
      </nav>
      <nav className="sidebar__footer" aria-label="Account and settings">
        {secondaryNav.map((item) => (
          <NavEntry key={item.id} item={item} />
        ))}
      </nav>
    </aside>
  );
}
