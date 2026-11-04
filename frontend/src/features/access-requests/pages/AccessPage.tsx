import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader } from '@/components/ui/Card';
import { SettingsNav } from '@/features/settings';
import { useAuth } from '@/services/session';
import { humanize } from '@/utils/format';
import { MyRequests } from '../components/MyRequests';
import { RoleGuide } from '../components/RoleGuide';
import { RoleRequestForm } from '../components/RoleRequestForm';
import '../access.css';

/** Settings, Access: the roles you hold, how to ask for another one, and what each role can do. */
export function AccessPage() {
  const { user } = useAuth();
  const held = user?.roles ?? [];
  const canRequest = !held.includes('administrator');
  return (
    <section aria-labelledby="access-title" className="stack stack--tight">
      <PageHeader title="Access and roles" titleId="access-title" subtitle="Your roles, and how to ask for an operational role" />
      <SettingsNav />
      <Card aria-labelledby="your-roles">
        <CardHeader title="Your roles" titleId="your-roles" />
        <p>{held.length ? held.map(humanize).join(', ') : 'No roles assigned.'}</p>
        <p className="muted">Roles are assigned by an administrator. Choosing a role never grants it: the server checks every request.</p>
      </Card>
      {canRequest && (
        <div className="access-grid">
          <Card aria-labelledby="request-role">
            <CardHeader title="Request an operational role" titleId="request-role" />
            <RoleRequestForm held={held} />
          </Card>
          <Card aria-labelledby="my-requests">
            <CardHeader title="Your requests" titleId="my-requests" />
            <MyRequests />
          </Card>
        </div>
      )}
      <Card aria-labelledby="role-guide">
        <CardHeader title="What each role can do" titleId="role-guide" />
        <RoleGuide />
      </Card>
    </section>
  );
}
