import { useState } from 'react';
import { Activity, Bell, LogIn, LogOut, Search } from 'lucide-react';
import { useNavigate } from 'react-router';
import { Avatar } from '@/components/ui/Avatar';
import { IconButton, IconLink } from '@/components/ui/IconButton';
import { Menu, type MenuItem } from '@/components/ui/Menu';
import { PageSearch } from '@/components/navigation/PageSearch';
import { useUnreadCount } from '@/features/notifications';
import { useAuth } from '@/services/session';
import './layout.css';

const ROLE_LABELS: Record<string, string> = {
  citizen: 'Citizen',
  collector: 'Collector',
  facility_operator: 'Facility operator',
  manager: 'Manager',
  administrator: 'Administrator',
};

/** Search, notifications and the account menu, showing the real signed-in user (or "Guest"). */
export function UserTools({ showSearch = true }: { showSearch?: boolean }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const { status, user, signOut, can } = useAuth();
  const unread = useUnreadCount(status === 'authenticated' && can('notifications:read_own')).data?.unread ?? 0;
  const navigate = useNavigate();

  const items: MenuItem[] =
    status === 'authenticated'
      ? [
          { id: 'status', label: 'System status', to: '/settings/system-status', icon: <Activity size={16} aria-hidden="true" /> },
          {
            id: 'sign-out',
            label: 'Sign out',
            icon: <LogOut size={16} aria-hidden="true" />,
            onSelect: () => {
              void signOut().then(() => navigate('/sign-in', { replace: true }));
            },
          },
        ]
      : [{ id: 'sign-in', label: 'Sign in', to: '/sign-in', icon: <LogIn size={16} aria-hidden="true" /> }];

  const role = user?.roles[0] ? (ROLE_LABELS[user.roles[0]] ?? user.roles[0]) : null;

  return (
    <div className="user-tools">
      {showSearch && (
        <IconButton label="Search pages" icon={<Search size={20} aria-hidden="true" />} onClick={() => setSearchOpen(true)} />
      )}
      <span className="user-tools__bell">
        <IconLink
          label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
          to="/notifications"
          icon={<Bell size={20} aria-hidden="true" />}
        />
        {unread > 0 && (
          <span className="user-tools__badge" aria-hidden="true">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </span>
      <Menu
        label="Account menu"
        align="end"
        trigger={
          <>
            <Avatar name={user?.full_name} />
            <span className="user-tools__name">
              {user?.full_name ?? 'Guest'}
              {role && <span className="user-tools__role">{role}</span>}
            </span>
          </>
        }
        items={items}
      />
      <PageSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
