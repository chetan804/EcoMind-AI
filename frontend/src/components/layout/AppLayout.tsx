import { Outlet } from 'react-router';

/** Application shell shared by all routes. Navigation entries are added with the features. */
export function AppLayout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-brand">EcoMind AI</span>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
