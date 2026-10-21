import '../notifications.css';
import { useState } from 'react';
import { BellOff } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Table';
import { Switch } from '@/components/ui/Choice';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { getErrorMessage } from '@/services/error-handler';
import { formatDateTime, humanize } from '@/utils/format';
import { useMarkAllRead, useMarkRead, useNotifications } from '../hooks/useNotifications';

const CATEGORIES = ['collection', 'report', 'incident', 'anomaly', 'reward', 'system'];

export function NotificationsPage() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [category, setCategory] = useState('');
  const query = useNotifications({ page, unread_only: unreadOnly, category });
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  return (
    <section aria-labelledby="notifications-title" className="stack stack--tight">
      <PageHeader
        title="Notifications"
        titleId="notifications-title"
        subtitle="Updates about your reports, tasks, incidents and rewards"
        actions={
          <Button variant="secondary" loading={markAll.isPending} onClick={() => markAll.mutate()}>
            Mark all as read
          </Button>
        }
      />
      {(markRead.isError || markAll.isError) && (
        <Alert tone="danger">{getErrorMessage(markRead.error ?? markAll.error)}</Alert>
      )}
      <div className="filter-bar">
        <Field label="Category">
          {(control) => (
            <Select
              {...control}
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All categories</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {humanize(c)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Switch
          label="Unread only"
          checked={unreadOnly}
          onChange={(e) => {
            setUnreadOnly(e.target.checked);
            setPage(1);
          }}
        />
      </div>
      <QueryBoundary query={query} label="notifications">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState
              icon={<BellOff size={24} />}
              title={unreadOnly || category ? 'No notifications match these filters' : 'No notifications yet'}
              description="Updates appear here when something changes on an item you reported or work on."
            />
          ) : (
            <>
              <ul className="notification-list">
                {data.items.map((n) => (
                  <li key={n.id}>
                    <Card className={n.read_at ? 'notification' : 'notification notification--unread'}>
                      <div>
                        <p className="notification__title">
                          {n.read_at ? null : <Badge tone="info">New</Badge>} {n.title}
                        </p>
                        {n.body && <p className="muted">{n.body}</p>}
                        <p className="muted">
                          {humanize(n.category)} · {formatDateTime(n.created_at)}
                        </p>
                      </div>
                      {!n.read_at && (
                        <Button variant="ghost" onClick={() => markRead.mutate(n.id)} aria-label={`Mark as read: ${n.title}`}>
                          Mark as read
                        </Button>
                      )}
                    </Card>
                  </li>
                ))}
              </ul>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={setPage}
                summary={`${data.total} notification${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
    </section>
  );
}
