import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { page, routeApi } from '../helpers/api-mock';
import { notificationFixture } from '../helpers/fixtures';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const member = userWith(['notifications:read_own'], { roles: ['citizen'] });
const unread = notificationFixture();
const read = notificationFixture({ id: '55555555-5555-4555-8555-555555555555', title: 'Report verified', read_at: '2026-10-19T10:00:00Z' });

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

describe('notification bell', () => {
  it('shows the unread count from the server in the bell label', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/notifications/unread-count': { unread: 3 } }, member);
    renderAt('/dashboard');
    expect(await screen.findByRole('link', { name: 'Notifications, 3 unread' })).toHaveAttribute('href', '/notifications');
  });

  it('does not ask for a count when the user cannot read notifications', async () => {
    const api = routeApi(fetchSpy, {}, userWith(['classification:predict'], { roles: ['citizen'] }));
    renderAt('/dashboard');
    expect(await screen.findByRole('link', { name: 'Notifications' })).toBeInTheDocument();
    expect(api.calls).toEqual([]);
  });
});

describe('notifications page', () => {
  it('lists notifications, marks one as read and refreshes', async () => {
    let items = [unread, read];
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/notifications': () => page(items),
        'GET /api/v1/notifications/unread-count': () => ({ unread: items.filter((n) => !n.read_at).length }),
        [`POST /api/v1/notifications/${unread.id}/read`]: () => {
          items = [{ ...unread, read_at: '2026-10-20T00:00:00Z' }, read];
          return items[0];
        },
      },
      member,
    );
    renderAt('/notifications');
    const first = (await screen.findByText('Your pickup was collected')).closest('li');
    expect(first).not.toBeNull();
    expect(within(first as HTMLElement).getByText('New')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Mark "Your pickup was collected" as read' }));
    await vi.waitFor(() => expect(screen.queryByText('New')).not.toBeInTheDocument());
    expect(api.calls.filter((c) => c.key.startsWith('POST'))).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /Mark ".*" as read/ })).not.toBeInTheDocument();
  });

  it('sends filters to the server and shows a filtered empty state', async () => {
    const api = routeApi(
      fetchSpy,
      { 'GET /api/v1/notifications': () => page([]), 'GET /api/v1/notifications/unread-count': { unread: 0 } },
      member,
    );
    renderAt('/notifications');
    expect(await screen.findByText('No notifications yet')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('switch', { name: 'Unread only' }));
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'incident');
    expect(await screen.findByText('No notifications match these filters')).toBeInTheDocument();
    const last = [...api.calls].reverse().find((c) => c.key === 'GET /api/v1/notifications');
    expect(last?.query.get('unread_only')).toBe('true');
    expect(last?.query.get('category')).toBe('incident');
  });

  it('marks everything read', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/notifications': page([unread]),
        'GET /api/v1/notifications/unread-count': { unread: 1 },
        'POST /api/v1/notifications/read-all': { marked: 1 },
      },
      member,
    );
    renderAt('/notifications');
    await userEvent.click(await screen.findByRole('button', { name: 'Mark all as read' }));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/notifications/read-all')).toBe(true));
  });
});
