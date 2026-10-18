import { useState } from 'react';
import { Search } from 'lucide-react';
import { PageSearch } from '@/components/navigation/PageSearch';
import { UserTools } from './UserTools';
import './layout.css';

/** Dashboard-style top bar: a page-search field in the centre, user tools on the right. */
export function Topbar() {
  const [open, setOpen] = useState(false);
  return (
    <div className="topbar">
      <div className="topbar__search">
        <button type="button" className="search-trigger" onClick={() => setOpen(true)} aria-haspopup="dialog">
          <Search size={20} aria-hidden="true" />
          Search pages…
        </button>
      </div>
      <UserTools showSearch={false} />
      <PageSearch open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
