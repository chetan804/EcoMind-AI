import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { Dialog } from '@/components/ui/Dialog';
import { SearchInput } from '@/components/ui/Input';
import { allNav } from './nav-items';
import '@/components/layout/layout.css';

/** Search over the application's pages (titles only). It navigates; it does not search data. */
export function PageSearch({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? allNav.filter((item) => item.label.toLowerCase().includes(q)) : allNav;
  }, [query]);

  return (
    <Dialog open={open} onClose={onClose} title="Search pages" description="Jump to a page by name.">
      <SearchInput
        aria-label="Page name"
        placeholder="Search pages…"
        data-autofocus
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {results.length === 0 ? (
        <p role="status">No page matches “{query}”.</p>
      ) : (
        <ul className="search-dialog__results" aria-label="Pages">
          {results.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <Link to={item.to} className="search-dialog__result" onClick={onClose}>
                  <Icon size={20} aria-hidden="true" />
                  {item.label}
                  {item.status === 'planned' && <span className="nav-link__soon">Soon</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Dialog>
  );
}
