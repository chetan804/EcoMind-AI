import { ButtonLink } from '@/components/ui/Button';
import './feedback.css';

/** Shown when rendering a route throws. Never displays error internals to the user. */
export function RouteErrorFallback() {
  return (
    <section className="status-page" role="alert">
      <h1 className="status-page__title">Something went wrong</h1>
      <p className="status-page__text">An unexpected error occurred while displaying this page.</p>
      <ButtonLink to="/" variant="secondary">
        Go to the start page
      </ButtonLink>
    </section>
  );
}
