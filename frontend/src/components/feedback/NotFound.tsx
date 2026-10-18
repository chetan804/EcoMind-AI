import { ButtonLink } from '@/components/ui/Button';
import './feedback.css';

export function NotFound() {
  return (
    <section className="status-page">
      <h1 className="status-page__title">Page not found</h1>
      <p className="status-page__text">The page you requested does not exist.</p>
      <ButtonLink to="/" variant="secondary">
        Go to the start page
      </ButtonLink>
    </section>
  );
}
