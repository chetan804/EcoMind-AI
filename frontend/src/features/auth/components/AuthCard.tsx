import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Brand } from '@/components/layout/BrandMark';
import { AuthIllustration } from './AuthIllustration';
import '../auth.css';

/** Two-panel authentication layout: brand panel on the left, form panel on the right. */
export function AuthCard({ children }: { children: ReactNode }) {
  return (
    <main className="auth-page" id="main">
      <div className="auth-card">
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
