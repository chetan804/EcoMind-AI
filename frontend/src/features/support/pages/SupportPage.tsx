import { PageHeader } from '@/components/layout/PageHeader';
import { ButtonLink } from '@/components/ui/Button';
import { Tabs } from '@/components/ui/Tabs';
import { useAuth } from '@/services/session';
import { ArticlesTab, UsageTab } from '../components/ArticleTabs';
import { MyRequestsTab, QueueTab } from '../components/TicketTabs';
import '../support.css';

/** Support requests for everyone; the queue, help articles and assistant usage for the people who run the desk. */
export function SupportPage() {
  const { can } = useAuth();
  const tabs = [
    ...(can('support:ask') ? [{ id: 'mine', label: 'My requests', panel: <MyRequestsTab /> }] : []),
    ...(can('support:manage') ? [{ id: 'queue', label: 'Support queue', panel: <QueueTab /> }, { id: 'usage', label: 'Assistant usage', panel: <UsageTab /> }] : []),
    ...(can('knowledge:manage') ? [{ id: 'articles', label: 'Help articles', panel: <ArticlesTab /> }] : []),
  ];
  return (
    <section aria-labelledby="support-title" className="stack stack--tight">
      <PageHeader
        title="Support"
        titleId="support-title"
        subtitle="Ask the support team a question and follow the answer. Staff handle the queue and keep the help articles up to date."
        actions={can('support:ask') ? <ButtonLink variant="secondary" to="/assistant">Ask the help assistant</ButtonLink> : null}
      />
      <Tabs label="Support views" items={tabs} />
    </section>
  );
}
