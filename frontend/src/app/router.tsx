import { createBrowserRouter, createMemoryRouter, type RouteObject } from 'react-router';
import { NotFound } from '@/components/feedback/NotFound';
import { PlannedFeaturePage } from '@/components/feedback/PlannedFeaturePage';
import { RouteErrorFallback } from '@/components/feedback/RouteErrorFallback';
import { AppShell } from '@/components/layout/AppShell';
import { primaryNav } from '@/components/navigation/nav-items';
import { SignInPage, SignUpPage } from '@/features/auth';
import { DashboardPage } from '@/features/dashboard';
import { LandingPage } from '@/features/landing';
import { SystemStatusPage } from '@/features/settings';
import { ClassificationPage } from '@/features/waste-classification';

/** Navigation entries whose feature is not built get a page that says so (see PlannedFeaturePage). */
const plannedRoutes: RouteObject[] = primaryNav
  .filter((item) => item.status === 'planned')
  .map((item) => ({ path: item.to.slice(1), element: <PlannedFeaturePage /> }));

/**
 * The single route table. Public pages (landing, sign-in, sign-up) render without the app shell;
 * everything else lives inside it. Feature routes are added here as features are implemented.
 */
export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage />, errorElement: <RouteErrorFallback /> },
  { path: '/sign-in', element: <SignInPage />, errorElement: <RouteErrorFallback /> },
  { path: '/sign-up', element: <SignUpPage />, errorElement: <RouteErrorFallback /> },
  {
    element: <AppShell />,
    errorElement: <RouteErrorFallback />,
    children: [
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'classify', element: <ClassificationPage /> },
      { path: 'settings/system-status', element: <SystemStatusPage /> },
      ...plannedRoutes,
      { path: '*', element: <NotFound /> },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(routes);
export const createTestRouter = (initialEntries: string[]) =>
  createMemoryRouter(routes, { initialEntries });
