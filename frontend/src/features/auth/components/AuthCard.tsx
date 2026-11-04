import { useEffect, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router';
import { X } from 'lucide-react';
import { Brand } from '@/components/layout/BrandMark';
import { AuthIllustration } from './AuthIllustration';
import '../auth.css';

/**
 * Two-panel authentication layout: brand panel on the left, form panel on the right.
 *
 * The card behaves like a dialog over the public site: a visible close control (a real link back
 * to the home page, so it works without scripting and by keyboard) and Escape do the same thing.
 */
export function AuthCard({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) void navigate('/');
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [navigate]);

  return (
    <main className="auth-page" id="main">
      <div className={wide ? 'auth-card auth-card--wide' : 'auth-card'}>
        <Link to="/" className="auth-close" aria-label="Close and return to the home page" title="Close (Esc)">
          <X size={20} aria-hidden="true" />
        </Link>
        <section className="auth-card__brand" aria-label="EcoMind AI">
          <Link to="/" className="brand auth-card__logo" aria-label="EcoMind AI home">
            <Brand />
          </Link>
          <p className="auth-card__tagline">
            Clean cities.
            <br />
            Greener tomorrows.
          </p>
          <AuthIllustration />
        </section>
        <section className="auth-card__panel">{children}</section>
      </div>
    </main>
  );
}
