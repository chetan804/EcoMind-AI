import { useCallback, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import { Menu as MenuIcon } from 'lucide-react';
import { Sidebar } from '@/components/navigation/Sidebar';
import { IconButton } from '@/components/ui/IconButton';
import { BrandMark } from './BrandMark';
import { VerifyEmailBanner } from './VerifyEmailBanner';
import { useApplyTheme } from '@/services/theme/theme';
import { cx } from '@/utils/cx';
import './layout.css';

/** Authenticated-area shell: sidebar (drawer below 1024px) and the main content region. */
export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuButton = useRef<HTMLSpanElement>(null);
  const { pathname } = useLocation();
  useApplyTheme();

  // Close the drawer when the route changes (adjusting state during render, not in an effect).
  const [lastPath, setLastPath] = useState(pathname);
  if (lastPath !== pathname) {
    setLastPath(pathname);
    setDrawerOpen(false);
  }

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
    menuButton.current?.querySelector('button')?.focus();
  }, []);

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <div className="shell__bar">
        <span ref={menuButton}>
          <IconButton
            label="Open navigation"
            aria-expanded={drawerOpen}
            icon={<MenuIcon size={24} aria-hidden="true" />}
            onClick={() => setDrawerOpen(true)}
          />
        </span>
        <BrandMark />
      </div>
      <Sidebar open={drawerOpen} onClose={closeDrawer} />
      <div className={cx('shell__backdrop', drawerOpen && 'shell__backdrop--open')} onClick={closeDrawer} aria-hidden="true" />
      <main id="main" className="shell__main" tabIndex={-1}>
        <VerifyEmailBanner />
        <Outlet />
      </main>
    </div>
  );
}
