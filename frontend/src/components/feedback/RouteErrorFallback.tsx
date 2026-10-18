import { Link } from 'react-router';

/** Shown when rendering a route throws. Never displays error internals to the user. */
export function RouteErrorFallback() {
  return (
    <section role="alert">
      <h1>Something went wrong</h1>
      <p>An unexpected error occurred while displaying this page.</p>
      <Link to="/">Go to the start page</Link>
    </section>
  );
}
