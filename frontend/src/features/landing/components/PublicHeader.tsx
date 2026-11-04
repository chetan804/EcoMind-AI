import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { Menu, X } from 'lucide-react';
import { Brand } from '@/components/layout/BrandMark';
import { ButtonLink } from '@/components/ui/Button';
import { SECTION_LINKS } from '../content';

/**
 * Sticky public-site header: brand, in-page section links, Sign in and Get started. Below the
 * desktop breakpoint the links move into a menu that opens with a button (aria-expanded), closes
 * with Escape or a link, and returns focus to the button.
 */
export function PublicHeader() {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      toggle.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className="public-header">
      <div className="public-header__bar">
        <Link to="/" className="brand" aria-label="EcoMind AI home">
          <Brand />
        </Link>
        <nav aria-label="Sections" className="public-header__nav">
          {SECTION_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="public-header__link">
              {link.label}
            </a>
          ))}
        </nav>
        <div className="public-header__actions">
          <Link to="/sign-in" className="public-header__signin">
            Sign in
          </Link>
          <ButtonLink to="/sign-up" className="public-header__cta">
            Get started
          </ButtonLink>
          <button
            ref={toggle}
            type="button"
            className="public-header__toggle"
            aria-expanded={open}
            aria-controls="public-menu"
            aria-label={open ? 'Close menu' : 'Open menu'}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}
          </button>
        </div>
      </div>
      {open && (
        <nav id="public-menu" aria-label="Menu sections" className="public-menu">
          {SECTION_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="public-menu__link" onClick={() => setOpen(false)}>
              {link.label}
            </a>
          ))}
          <Link to="/sign-in" className="public-menu__link">
            Sign in
          </Link>
        </nav>
      )}
    </header>
  );
}
