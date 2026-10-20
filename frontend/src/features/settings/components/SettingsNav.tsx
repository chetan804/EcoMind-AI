import { NavLink } from 'react-router';
import { useAuth } from '@/services/session';
import './settings.css';

const LINKS = [
  { to: '/settings/security', label: 'Security', permission: null },
  { to: '/settings/system-status', label: 'System status', permission: null },
  { to: '/settings/users', label: 'Users', permission: 'users:read' },
  { to: '/settings/audit', label: 'Audit log', permission: 'audit:read' },
];

/** Section links for the settings pages; entries appear only for permissions the user holds. */
export function SettingsNav() {
  const { can } = useAuth();
  return (
    <nav aria-label="Settings sections" className="settings-nav">
      {LINKS.filter((l) => l.permission === null || can(l.permission)).map((l) => (
        <NavLink key={l.to} to={l.to} className="settings-nav__link">
          {l.label}
        </NavLink>
      ))}
    </nav>
  );
}
