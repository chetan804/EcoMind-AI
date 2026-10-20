import type { ComponentType } from 'react';
import { createBrowserRouter, createMemoryRouter, type RouteObject } from 'react-router';
import { NotFound } from '@/components/feedback/NotFound';
import { PlannedFeaturePage } from '@/components/feedback/PlannedFeaturePage';
import { RouteErrorFallback } from '@/components/feedback/RouteErrorFallback';
import { PageLoading } from '@/components/feedback/Loading';
import { primaryNav } from '@/components/navigation/nav-items';
import { RequireAuth } from './guards/RequireAuth';

/**
 * Route-level code splitting: each screen is fetched when its route is first visited, so for
 * example the public landing page does not download the dashboard charts or the classification
 * workflow. A failed chunk load surfaces through the route's errorElement.
 */
function lazyPage<K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K): RouteObject['lazy'] {
  return async () => ({ Component: (await load())[name] });
}

/** Navigation entries whose feature is not built get a page that says so (see PlannedFeaturePage). */
const plannedRoutes: RouteObject[] = primaryNav
  .filter((item) => item.status === 'planned')
  .map((item) => ({ path: item.to.slice(1), element: <PlannedFeaturePage /> }));

/**
 * The single route table. Public pages (landing, sign-in, sign-up) render without the app shell;
 * everything else requires a signed-in user (`RequireAuth`) and lives inside the shell. Feature
 * routes are added here as features are implemented; gate role-specific ones with
 * `RequirePermission`.
 */
export const routes: RouteObject[] = [
  { path: '/', lazy: lazyPage(() => import('@/features/landing'), 'LandingPage'), errorElement: <RouteErrorFallback />, HydrateFallback: PageLoading },
  { path: '/sign-in', lazy: lazyPage(() => import('@/features/auth'), 'SignInPage'), errorElement: <RouteErrorFallback />, HydrateFallback: PageLoading },
  { path: '/sign-up', lazy: lazyPage(() => import('@/features/auth'), 'SignUpPage'), errorElement: <RouteErrorFallback />, HydrateFallback: PageLoading },
  {
    element: <RequireAuth />,
    errorElement: <RouteErrorFallback />,
    children: [
      {
        lazy: lazyPage(() => import('@/components/layout/AppShell'), 'AppShell'),
        HydrateFallback: PageLoading,
        children: [
          { path: 'dashboard', lazy: lazyPage(() => import('@/features/dashboard'), 'DashboardPage') },
          { path: 'classify', lazy: lazyPage(() => import('@/features/waste-classification'), 'ClassificationPage') },
          { path: 'settings/system-status', lazy: lazyPage(() => import('@/features/settings'), 'SystemStatusPage') },
          ...plannedRoutes,
          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(routes);
export const createTestRouter = (initialEntries: string[]) =>
  createMemoryRouter(routes, { initialEntries });
