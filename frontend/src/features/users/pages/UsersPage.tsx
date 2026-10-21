import { useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Choice';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { SearchInput, Select, Textarea } from '@/components/ui/Input';
import { Pagination, Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, humanize } from '@/utils/format';
import type { AdminUser, UserAction } from '../api/users-api';
import { SettingsNav } from '@/features/settings';
import { useRoles, useUserChange, useUsers } from '../hooks/useUsers';

type Pending = { user: AdminUser; kind: 'roles' } | { user: AdminUser; kind: UserAction };

const TITLES: Record<UserAction | 'roles', string> = {
  roles: 'Change roles',
  deactivate: 'Deactivate account',
  activate: 'Reactivate account',
  'reset-mfa': 'Reset two-step verification',
};

export function UsersPage() {
  const { can, user: me } = useAuth();
  const [filters, setFilters] = useState({ page: 1, q: '', role: '', is_active: '' });
  const [pending, setPending] = useState<Pending | null>(null);
  const query = useUsers(filters);
  const roles = useRoles();
  const manage = can('users:manage');
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  return (
    <section aria-labelledby="users-title" className="stack stack--tight">
      <PageHeader title="Users" titleId="users-title" subtitle="Accounts, roles and sign-in security" />
      <SettingsNav />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Name or email" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Role">
          {(c) => (
            <Select {...c} value={filters.role} onChange={(e) => set({ role: e.target.value })}>
              <option value="">All roles</option>
              {(roles.data ?? []).map((r) => (
                <option key={r.name} value={r.name}>{humanize(r.name)}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Account">
          {(c) => (
            <Select {...c} value={filters.is_active} onChange={(e) => set({ is_active: e.target.value })}>
              <option value="">Active and inactive</option>
              <option value="true">Active</option>
              <option value="false">Deactivated</option>
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="users">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="No users match" description="Try a different search or filter." />
          ) : (
            <>
              <Table caption="Users">
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Roles</th>
                    <th scope="col">Status</th>
                    <th scope="col">Email</th>
                    <th scope="col">Two-step</th>
                    <th scope="col">Last sign-in</th>
                    {manage && (
                      <th scope="col">
                        <span className="visually-hidden">Actions</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((u) => (
                    <tr key={u.id}>
                      <th scope="row">
                        {u.full_name}
                        <p className="muted">{u.email}</p>
                      </th>
                      <td>{u.roles.map(humanize).join(', ') || '—'}</td>
                      <td>{u.is_active ? <Badge tone="success">Active</Badge> : <Badge tone="neutral">Deactivated</Badge>}</td>
                      <td>{u.email_verified ? <Badge tone="success">Verified</Badge> : <Badge tone="neutral">Not verified</Badge>}</td>
                      <td>{u.mfa_enabled ? <Badge tone="success">On</Badge> : <Badge tone="neutral">Off</Badge>}</td>
                      <td>{formatDateTime(u.last_login_at)}</td>
                      {manage && (
                        <td>
                          {u.id === me?.id ? (
                            <span className="muted">You</span>
                          ) : (
                            <div className="row-actions">
                              <Button variant="secondary" onClick={() => setPending({ user: u, kind: 'roles' })} aria-label={`Change roles: ${u.full_name}`}>Roles</Button>
                              <Button variant="secondary" onClick={() => setPending({ user: u, kind: u.is_active ? 'deactivate' : 'activate' })} aria-label={`${u.is_active ? 'Deactivate' : 'Reactivate'}: ${u.full_name}`}>
                                {u.is_active ? 'Deactivate' : 'Reactivate'}
                              </Button>
                              {u.mfa_enabled && (
                                <Button variant="secondary" onClick={() => setPending({ user: u, kind: 'reset-mfa' })} aria-label={`Reset two-step verification: ${u.full_name}`}>Reset two-step</Button>
                              )}
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} user${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {pending && <ChangeDialog key={`${pending.user.id}${pending.kind}`} pending={pending} roleNames={(roles.data ?? []).map((r) => r.name)} onClose={() => setPending(null)} />}
    </section>
  );
}

function ChangeDialog({ pending, roleNames, onClose }: { pending: Pending; roleNames: string[]; onClose: () => void }) {
  const { user, kind } = pending;
  const [selected, setSelected] = useState<string[]>(user.roles);
  const [reason, setReason] = useState('');
  const mutation = useUserChange();
  const valid = reason.trim().length >= 3 && (kind !== 'roles' || selected.length > 0);
  const submit = () =>
    mutation.mutate(kind === 'roles' ? { id: user.id, roles: selected, reason: reason.trim() } : { id: user.id, action: kind, reason: reason.trim() }, { onSuccess: onClose });
  return (
    <Dialog
      open
      onClose={onClose}
      title={TITLES[kind]}
      description={`${user.full_name} (${user.email}). The reason is recorded in the audit log.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant={kind === 'deactivate' || kind === 'reset-mfa' ? 'danger' : 'primary'} loading={mutation.isPending} disabled={!valid} onClick={submit}>
            {TITLES[kind]}
          </Button>
        </>
      }
    >
      {kind === 'roles' && (
        <fieldset className="settings-form">
          <legend>Roles</legend>
          {roleNames.map((r) => (
            <Checkbox
              key={r}
              label={humanize(r)}
              checked={selected.includes(r)}
              onChange={(e) => setSelected((s) => (e.target.checked ? [...s, r] : s.filter((x) => x !== r)))}
            />
          ))}
        </fieldset>
      )}
      <Field label="Reason (required)">{(c) => <Textarea {...c} data-autofocus value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />}</Field>
      {mutation.isError && <Alert tone="danger">{getErrorMessage(mutation.error)}</Alert>}
    </Dialog>
  );
}
