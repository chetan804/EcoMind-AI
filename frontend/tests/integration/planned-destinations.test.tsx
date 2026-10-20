import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Hammer } from 'lucide-react';
import type * as NavItems from '@/components/navigation/nav-items';
import { routeApi } from '../helpers/api-mock';
import { renderAt } from '../helpers/render';
import { resetSession } from '../helpers/session';

// Every real destination is built, so the "not built yet" mechanism is exercised with a synthetic
// entry added to the navigation table. It proves the label and page still behave honestly if a
// future entry is added as `planned`.
vi.mock('@/components/navigation/nav-items', async (importOriginal) => {
  const original = await importOriginal<typeof NavItems>();
  const primaryNav = [
    ...original.primaryNav,
    { id: 'future', label: 'Future area', to: '/future-area', icon: Hammer, status: 'planned' as const },
  ];
  const allNav = [...primaryNav, ...original.secondaryNav];
  return {
    ...original,
    primaryNav,
    allNav,
    findNavItem: (pathname: string) => allNav.find((item) => pathname === item.to || pathname.startsWith(`${item.to}/`)),
  };
});

const fetchSpy = vi.fn();

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

describe('planned destinations', () => {
  it('are labelled "Soon", and say plainly that they are not built yet', async () => {
    routeApi(fetchSpy, {});
    renderAt('/dashboard');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const link = within(nav).getByRole('link', { name: /^Future area/ });
    expect(link).toHaveTextContent('Soon');
    expect(within(nav).getByRole('link', { name: /^Marketplace/ })).not.toHaveTextContent('Soon');
    await userEvent.click(link);
    expect(await screen.findByRole('heading', { name: 'Future area is not built yet' })).toBeInTheDocument();
  });
});
