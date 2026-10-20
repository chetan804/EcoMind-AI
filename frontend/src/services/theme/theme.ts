import { useEffect, useSyncExternalStore } from 'react';

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'ecomind.theme';
const listeners = new Set<() => void>();

/** The stored display preference (non-secret). Dark is the default design. */
export function readTheme(): Theme {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

export function writeTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage can be blocked; the choice then lasts only for this page view.
    document.documentElement.dataset.theme = theme;
  }
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  window.addEventListener('storage', notify);
  return () => {
    listeners.delete(notify);
    window.removeEventListener('storage', notify);
  };
}

/** Current theme preference plus a setter. */
export function useThemePreference(): { theme: Theme; setTheme: (theme: Theme) => void } {
  const theme = useSyncExternalStore(subscribe, readTheme, () => 'dark' as Theme);
  return { theme, setTheme: writeTheme };
}

/**
 * Applies the preference to the document while the signed-in app is mounted. Public pages (landing,
 * sign in) are designed for the dark theme only, so the attribute is restored when the app unmounts.
 */
export function useApplyTheme(): void {
  const { theme } = useThemePreference();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    return () => {
      document.documentElement.dataset.theme = 'dark';
    };
  }, [theme]);
}
