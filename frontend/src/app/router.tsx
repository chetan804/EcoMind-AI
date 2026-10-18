import { createBrowserRouter, createMemoryRouter, Navigate, type RouteObject } from 'react-router';
import { AppLayout } from '@/components/layout/AppLayout';
import { NotFound } from '@/components/feedback/NotFound';
import { RouteErrorFallback } from '@/components/feedback/RouteErrorFallback';
import { SystemStatusPage } from '@/features/settings';

/** The single route table. Feature routes are added here as features are implemented. */
export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    errorElement: <RouteErrorFallback />,
    children: [
      { index: true, element: <Navigate to="/settings/system-status" replace /> },
      { path: 'settings/system-status', element: <SystemStatusPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(routes);
export const createTestRouter = (initialEntries: string[]) =>
  createMemoryRouter(routes, { initialEntries });
