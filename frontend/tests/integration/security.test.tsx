import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { authResponse } from '../helpers/session';
import { errorReply, page, routeApi } from '../helpers/api-mock';
import { renderAt, userWith } from '../helpers/render';
import { resetSession, testUser } from '../helpers/session';

const fetchSpy = vi.fn();
const status = (over: Record<string, unknown> = {}) => ({ enabled: false, pending_enrollment: false, enabled_at: null, recovery_codes_remaining: 0, ...over });
const enrollment = {
  secret: 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP',
  otpauth_uri: 'otpauth://totp/EcoMind:asha@example.org?secret=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP&issuer=EcoMind',
  issuer: 'EcoMind',
  algorithm: 'SHA1',
  digits: 6,
  period_seconds: 30,
};
const user = userWith([], { roles: ['citizen'] });

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

describe('sign-in with two-step verification', () => {
  const submitPassword = async () => {
    await userEvent.type(await screen.findByLabelText(/Email address/), 'asha@example.org');
    await userEvent.type(screen.getByLabelText(/^Password/), 'a long passphrase 1');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  };

  it('asks for the code after the password and only then signs in', async () => {
    const calls: Array<[string, unknown]> = [];
    fetchSpy.mockImplementation((url: string, init?: RequestInit) => {
      calls.push([url, init?.body ? JSON.parse(String(init.body)) : null]);
      if (url.endsWith('/auth/login')) return Promise.resolve(Response.json({ mfa_required: true, mfa_token: 'challenge-1', expires_in: 300 }));
      if (url.endsWith('/auth/mfa/verify')) return Promise.resolve(Response.json(authResponse(testUser)));
      return Promise.resolve(Response.json({}, { status: 404 }));
    });
    renderAt('/sign-in');
    await submitPassword();
    expect(await screen.findByRole('heading', { name: 'Two-step verification' })).toBeInTheDocument();
    expect(window.localStorage.getItem('ecomind.session-hint')).toBeNull();
    await userEvent.type(screen.getByLabelText('Verification code'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Verify and sign in' }));
    expect(await screen.findByRole('heading', { level: 1, name: /Good (morning|afternoon|evening)/ })).toBeInTheDocument();
    expect(calls.find(([u]) => u.endsWith('/auth/mfa/verify'))?.[1]).toEqual({ mfa_token: 'challenge-1', code: '123456' });
    expect(window.localStorage.getItem('ecomind.session-hint')).toBe('1');
  });

  it('shows a clear message for a wrong code, stays on the step, and can go back', async () => {
    fetchSpy.mockImplementation((url: string) => {
      if (url.endsWith('/auth/login')) return Promise.resolve(Response.json({ mfa_required: true, mfa_token: 'c', expires_in: 300 }));
      return Promise.resolve(errorReply(401, 'invalid_mfa_code', 'Invalid code'));
    });
    renderAt('/sign-in');
    await submitPassword();
    await userEvent.type(await screen.findByLabelText('Verification code'), '000000');
    await userEvent.click(screen.getByRole('button', { name: 'Verify and sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/code was not accepted/);
    expect(window.localStorage.getItem('ecomind.session-hint')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Back to sign in' }));
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });
});

describe('security page', () => {
  it('walks through enrolment, shows recovery codes once and requires confirmation', async () => {
    let enabled = false;
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/auth/mfa': () => status(enabled ? { enabled: true, enabled_at: '2026-10-20T00:00:00Z', recovery_codes_remaining: 2 } : {}),
        'POST /api/v1/auth/mfa/enroll': enrollment,
        'POST /api/v1/auth/mfa/activate': () => {
          enabled = true;
          return { recovery_codes: ['AAAA-BBBB-CCCC', 'DDDD-EEEE-FFFF'] };
        },
      },
      user,
    );
    renderAt('/settings/security');
    await userEvent.click(await screen.findByRole('button', { name: 'Set up two-step verification' }));
    expect(await screen.findByRole('img', { name: 'QR code for your authenticator app' })).toBeInTheDocument();
    expect(screen.getByText('JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP')).toBeInTheDocument();
    const confirm = screen.getByRole('button', { name: 'Confirm and turn on' });
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Code from your app'), '654321');
    await userEvent.click(confirm);
    const codes = await screen.findByRole('list', { name: 'Recovery codes' });
    expect(within(codes).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['AAAA-BBBB-CCCC', 'DDDD-EEEE-FFFF']);
    expect(api.calls.find((c) => c.key.endsWith('/activate'))?.body).toEqual({ code: '654321' });
    const done = screen.getByRole('button', { name: 'Done' });
    expect(done).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: /I have saved these codes/ }));
    await userEvent.click(done);
    expect(await screen.findByText(/2 recovery codes left/)).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Recovery codes' })).not.toBeInTheDocument();
  });

  it('turning off needs the password and a code, and reports a refusal', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/auth/mfa': status({ enabled: true, enabled_at: '2026-10-01T00:00:00Z', recovery_codes_remaining: 1 }),
        'POST /api/v1/auth/mfa/disable': errorReply(422, 'invalid_mfa_code', 'That code was not accepted.'),
      },
      user,
    );
    renderAt('/settings/security');
    expect(await screen.findByText(/running low on recovery codes/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Turn off two-step verification' }));
    const submit = screen.getByRole('button', { name: 'Turn off' });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getAllByLabelText(/^Password/)[0] as HTMLElement, 'my password 123');
    await userEvent.type(screen.getByLabelText('Authenticator or recovery code'), '111111');
    await userEvent.click(submit);
    expect(await screen.findByText('That code was not accepted.')).toBeInTheDocument();
    expect(api.calls.find((c) => c.key.endsWith('/disable'))?.body).toEqual({ password: 'my password 123', code: '111111' });
  });

  it('changes the password and refuses mismatched confirmation', async () => {
    const api = routeApi(
      fetchSpy,
      { 'GET /api/v1/auth/mfa': status(), 'POST /api/v1/auth/change-password': authResponse(testUser) },
      user,
    );
    renderAt('/settings/security');
    await screen.findByRole('button', { name: 'Set up two-step verification' });
    await userEvent.type(screen.getByLabelText('Current password'), 'old password 12345');
    await userEvent.type(screen.getByLabelText(/^New password/), 'a brand new passphrase');
    await userEvent.type(screen.getByLabelText('Repeat new password'), 'a brand new passphras');
    expect(screen.getByText('The passwords do not match.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Change password' })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Repeat new password'), 'e');
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByText(/Password changed/)).toBeInTheDocument();
    expect(api.calls.find((c) => c.key.endsWith('/change-password'))?.body).toEqual({ current_password: 'old password 12345', new_password: 'a brand new passphrase' });
  });
});

const row = (over: Record<string, unknown> = {}) => ({
  id: '77777777-7777-4777-8777-777777777777',
  email: 'ravi@example.org',
  full_name: 'Ravi Kumar',
  is_active: true,
  mfa_enabled: true,
  roles: ['collector'],
  created_at: '2026-09-01T00:00:00Z',
  last_login_at: null,
  ...over,
});
const adminUser = userWith(['users:read', 'users:manage', 'audit:read'], { roles: ['administrator'] });
const roleList = [
  { name: 'collector', description: null, is_system: true, user_count: 1, permissions: [] },
  { name: 'manager', description: null, is_system: true, user_count: 1, permissions: [] },
];

describe('users administration', () => {
  it('is forbidden without users:read', async () => {
    const api = routeApi(fetchSpy, {}, user);
    renderAt('/settings/users');
    expect(await screen.findByRole('heading', { name: 'You do not have access to this page' })).toBeInTheDocument();
    expect(api.calls).toEqual([]);
  });

  it('read-only viewers see users but no actions', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/admin/users': page([row()]), 'GET /api/v1/admin/roles': roleList }, userWith(['users:read']));
    renderAt('/settings/users');
    expect(await screen.findByText('Ravi Kumar')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Deactivate|Roles|Reset/ })).not.toBeInTheDocument();
  });

  it('deactivation needs a reason and sends it', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/admin/users': page([row()]),
        'GET /api/v1/admin/roles': roleList,
        'POST /api/v1/admin/users/77777777-7777-4777-8777-777777777777/deactivate': row({ is_active: false }),
      },
      adminUser,
    );
    renderAt('/settings/users');
    await userEvent.click(await screen.findByRole('button', { name: 'Deactivate: Ravi Kumar' }));
    const dialog = screen.getByRole('dialog', { name: 'Deactivate account' });
    const submit = within(dialog).getByRole('button', { name: 'Deactivate account' });
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Reason (required)'), 'Left the organisation');
    await userEvent.click(submit);
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.calls.find((c) => c.key.endsWith('/deactivate'))?.body).toEqual({ reason: 'Left the organisation' });
  });

  it('changes roles with a reason', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/admin/users': page([row()]),
        'GET /api/v1/admin/roles': roleList,
        'PUT /api/v1/admin/users/77777777-7777-4777-8777-777777777777/roles': row({ roles: ['collector', 'manager'] }),
      },
      adminUser,
    );
    renderAt('/settings/users');
    await userEvent.click(await screen.findByRole('button', { name: 'Change roles: Ravi Kumar' }));
    const dialog = screen.getByRole('dialog', { name: 'Change roles' });
    await userEvent.click(within(dialog).getByRole('checkbox', { name: 'Manager' }));
    await userEvent.type(within(dialog).getByLabelText('Reason (required)'), 'Promoted to depot manager');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Change roles' }));
    await vi.waitFor(() => expect(api.calls.some((c) => c.key.startsWith('PUT'))).toBe(true));
    expect(api.calls.find((c) => c.key.startsWith('PUT'))?.body).toEqual({ roles: ['collector', 'manager'], reason: 'Promoted to depot manager' });
  });

  it('shows the server reason when the last administrator cannot be changed', async () => {
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/admin/users': page([row({ roles: ['administrator'] })]),
        'GET /api/v1/admin/roles': roleList,
        'POST /api/v1/admin/users/77777777-7777-4777-8777-777777777777/deactivate': errorReply(409, 'last_administrator', 'The last administrator cannot be deactivated.'),
      },
      adminUser,
    );
    renderAt('/settings/users');
    await userEvent.click(await screen.findByRole('button', { name: 'Deactivate: Ravi Kumar' }));
    const dialog = screen.getByRole('dialog', { name: 'Deactivate account' });
    await userEvent.type(within(dialog).getByLabelText('Reason (required)'), 'Cleanup');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Deactivate account' }));
    expect(await within(dialog).findByText(/last administrator cannot be deactivated/)).toBeInTheDocument();
  });

  it('lists audit entries with filters', async () => {
    const entry = { id: '88888888-8888-4888-8888-888888888888', occurred_at: '2026-10-20T01:00:00Z', action: 'auth.login_failed', entity_type: 'user', entity_id: null, actor_id: null, actor_email: null, request_id: 'req-1', ip_address: null, changes: null };
    const api = routeApi(fetchSpy, { 'GET /api/v1/admin/audit-logs': page([entry]) }, adminUser);
    renderAt('/settings/audit');
    expect(await screen.findByText('auth.login_failed')).toBeInTheDocument();
    expect(screen.getByText('system or anonymous')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/^Action/), 'auth');
    await vi.waitFor(() => expect(api.calls.some((c) => c.query.get('action') === 'auth')).toBe(true));
  });

  it('settings navigation shows admin sections only to those who hold the permission', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/auth/mfa': status() }, user);
    renderAt('/settings/security');
    const nav = await screen.findByRole('navigation', { name: 'Settings sections' });
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Security', 'System status']);
  });
});
