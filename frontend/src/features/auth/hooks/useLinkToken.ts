import { useEffect, useState } from 'react';
import { useLocation } from 'react-router';
import { tokenFromHash } from '../utils/auth-errors';

/**
 * The one-time token of an e-mailed link, read once from the URL fragment (`#token=...`). The
 * fragment is then removed from the address bar so the token is not left in history, a bookmark
 * or a screenshot; it stays in component state for the form to submit. Null = absent or malformed.
 */
export function useLinkToken(): string | null {
  const location = useLocation();
  const [token] = useState(() => tokenFromHash(location.hash));
  useEffect(() => {
    if (token !== null) window.history.replaceState(window.history.state, '', `${location.pathname}${location.search}`);
  }, [token, location.pathname, location.search]);
  return token;
}
