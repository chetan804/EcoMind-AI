import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { Sidebar } from '@/components/navigation/Sidebar';
import { getSessionState, signIn } from '@/services/session/session-store';
import { authResponse, resetSession, testUser } from '../helpers/session';

beforeEach(() => {
  resetSession();
  vi.stubGlobal('fetch', vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

const renderSidebar = () =>
  render(
    <MemoryRouter initialEntries={['/settings/security']}>
      <Routes>
        <Route path="/settings/security" element={<Sidebar open={false} onClose={() => undefined} />} />
        <Route path="/sign-in" element={<p>Sign-in page</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe('sign out from the sidebar', () => {
  it('is available on every authenticated page (not only the dashboard), and signs out', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json(authResponse({ ...testUser, permissions: [] })));
    await signIn('a@b.co', 'pw');
    renderSidebar();
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByText('Sign-in page')).toBeInTheDocument();
    await waitFor(() => expect(getSessionState().status).toBe('anonymous'));
  });

  it('is not offered when nobody is signed in', () => {
    renderSidebar();
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  });
});
