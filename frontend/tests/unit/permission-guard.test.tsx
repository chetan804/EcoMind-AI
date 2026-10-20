import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { RequirePermission } from '@/app/guards/RequirePermission';
import { getSessionState, signIn } from '@/services/session/session-store';
import { authResponse, resetSession, testUser } from '../helpers/session';

beforeEach(() => {
  resetSession();
  vi.stubGlobal('fetch', vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

async function signInWithPermissions(permissions: string[]) {
  vi.mocked(fetch).mockResolvedValueOnce(Response.json(authResponse({ ...testUser, permissions })));
  await signIn('a@b.co', 'pw');
  expect(getSessionState().status).toBe('authenticated');
}

const renderGuarded = (permissions: string[]) =>
  render(
    <MemoryRouter>
      <RequirePermission permissions={permissions}>
        <p>Secret admin content</p>
      </RequirePermission>
    </MemoryRouter>,
  );

describe('RequirePermission', () => {
  it('renders the content when every permission is held', async () => {
    await signInWithPermissions(['users:read', 'users:manage']);
    renderGuarded(['users:read', 'users:manage']);
    expect(screen.getByText('Secret admin content')).toBeInTheDocument();
  });

  it('shows an explicit no-access state, not the content, when one is missing', async () => {
    await signInWithPermissions(['users:read']);
    renderGuarded(['users:read', 'users:manage']);
    expect(screen.queryByText('Secret admin content')).not.toBeInTheDocument();
    expect(screen.getByText('You do not have access to this page')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to dashboard' })).toHaveAttribute('href', '/dashboard');
  });

  it('denies by default when nobody is signed in', () => {
    renderGuarded(['users:read']);
    expect(screen.queryByText('Secret admin content')).not.toBeInTheDocument();
  });
});
