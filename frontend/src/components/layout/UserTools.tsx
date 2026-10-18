import { useState } from 'react';
import { Bell, LogIn, Search, Activity } from 'lucide-react';
import { Avatar } from '@/components/ui/Avatar';
import { IconButton, IconLink } from '@/components/ui/IconButton';
import { Menu } from '@/components/ui/Menu';
import { PageSearch } from '@/components/navigation/PageSearch';
import './layout.css';

/**
 * Search, notifications and account controls. There is no authentication yet, so the account
 * menu offers only what exists (sign in, system status) and never shows a made-up user.
 */
export function UserTools({ showSearch = true }: { showSearch?: boolean }) {
  const [searchOpen, setSearchOpen] = useState(false);
  return (
    <div className="user-tools">
      {showSearch && (
        <IconButton label="Search pages" icon={<Search size={20} aria-hidden="true" />} onClick={() => setSearchOpen(true)} />
      )}
      <IconLink label="Notifications" to="/notifications" icon={<Bell size={20} aria-hidden="true" />} />
      <Menu
        label="Account menu"
        align="end"
        trigger={
          <>
            <Avatar />
            <span className="user-tools__name">Guest</span>
          </>
        }
        items={[
          { id: 'sign-in', label: 'Sign in', to: '/sign-in', icon: <LogIn size={16} aria-hidden="true" /> },
          { id: 'status', label: 'System status', to: '/settings/system-status', icon: <Activity size={16} aria-hidden="true" /> },
        ]}
      />
      <PageSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
