import { useState } from 'react';
import { BookOpen } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { MetricTile } from '@/components/data-display/MetricTile';
import { useFields } from '@/components/forms/useFields';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Choice';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select, Textarea } from '@/components/ui/Input';
import { Pagination, Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { formatDate, formatNumber, formatPercent } from '@/utils/format';
import type { Article } from '../api/support-api';
import { useArticles, useCategories, useSaveArticle, useStats } from '../hooks/useSupport';

const pageCount = (d: { total: number; page_size: number }) => Math.max(1, Math.ceil(d.total / d.page_size));
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** The articles the assistant quotes. Editing them changes what people are told, so each change is audited server-side. */
export function ArticlesTab() {
  const [filters, setFilters] = useState({ page: 1, q: '', category: '', include_unpublished: true });
  const [editing, setEditing] = useState<Article | 'new' | null>(null);
  const categories = useCategories();
  const query = useArticles(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  return (
    <div className="stack stack--tight">
      <p className="muted">
        The assistant answers only from these articles and from the sorting guide. Add the words people actually use under keywords: they are searched but not shown. Unpublished articles are never quoted.
      </p>
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} value={filters.q} maxLength={100} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Category">
          {(c) => (
            <Select {...c} value={filters.category} onChange={(e) => set({ category: e.target.value })}>
              <option value="">All categories</option>
              {(categories.data ?? []).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Button onClick={() => setEditing('new')}>New article</Button>
      </div>
      <QueryBoundary query={query} label="the articles">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<BookOpen size={28} />} title="No articles" description="Run `python -m app.cli seed-support-knowledge` to load the starter set, or add an article." />
          ) : (
            <>
              <Table caption="Help articles">
                <thead>
                  <tr>
                    <th scope="col">Title</th>
                    <th scope="col">Category</th>
                    <th scope="col">Source</th>
                    <th scope="col">Status</th>
                    <th scope="col">Updated</th>
                    <th scope="col">
                      <span className="visually-hidden">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((a) => (
                    <tr key={a.id}>
                      <td>{a.title}</td>
                      <td>{a.category}</td>
                      <td>{a.source}</td>
                      <td>{a.published ? <Badge tone="success">Published</Badge> : <Badge tone="neutral">Unpublished</Badge>}</td>
                      <td>{formatDate(a.updated_at)}</td>
                      <td>
                        <Button variant="secondary" onClick={() => setEditing(a)} aria-label={`Edit article: ${a.title}`}>
                          Edit
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={data.page} pageCount={pageCount(data)} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} summary={`${data.total} articles`} />
            </>
          )
        }
      </QueryBoundary>
      {editing && <ArticleDialog article={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ArticleDialog({ article, onClose }: { article: Article | null; onClose: () => void }) {
  const { values, bind, set } = useFields({
    slug: article?.slug ?? '',
    title: article?.title ?? '',
    body: article?.body ?? '',
    category: article?.category ?? '',
    source: article?.source ?? '',
    keywords: article?.keywords ?? '',
    published: article ? (article.published ? 'yes' : '') : 'yes',
  });
  const save = useSaveArticle();
  const valid =
    values.title.trim().length >= 3 &&
    values.body.trim().length >= 20 &&
    values.category.trim().length >= 2 &&
    values.source.trim().length >= 3 &&
    (article !== null || SLUG.test(values.slug));
  const submit = () =>
    save.mutate(
      {
        id: article?.id ?? null,
        slug: values.slug,
        input: {
          title: values.title.trim(),
          body: values.body.trim(),
          category: values.category.trim(),
          source: values.source.trim(),
          keywords: values.keywords.trim(),
          published: values.published === 'yes',
        },
      },
      { onSuccess: onClose },
    );
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={article ? 'Edit article' : 'New article'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={save.isPending} unavailableReason={valid ? undefined : 'Complete the required fields'} onClick={submit}>
            Save article
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        {!article && (
          <Field label="Slug" required hint="Lowercase letters, digits and hyphens; cannot be changed later">
            {(c) => <Input {...c} data-autofocus maxLength={100} {...bind('slug')} />}
          </Field>
        )}
        <Field label="Title" required>
          {(c) => <Input {...c} maxLength={200} {...bind('title')} />}
        </Field>
        <Field label="Answer text" required hint="Plain text, 20 to 8000 characters. This is what the assistant quotes.">
          {(c) => <Textarea {...c} rows={7} maxLength={8000} {...bind('body')} />}
        </Field>
        <Field label="Category" required>
          {(c) => <Input {...c} maxLength={60} {...bind('category')} />}
        </Field>
        <Field label="Source" required hint="Where this content comes from: a policy, a document or the screen it describes">
          {(c) => <Input {...c} maxLength={200} {...bind('source')} />}
        </Field>
        <Field label="Keywords" hint="Other words people use for this topic, separated by spaces. Searched, not shown.">
          {(c) => <Textarea {...c} rows={2} maxLength={500} {...bind('keywords')} />}
        </Field>
        <Checkbox label="Published (the assistant may quote it)" checked={values.published === 'yes'} onChange={(e) => set({ published: e.target.checked ? 'yes' : '' })} />
        {save.isError && <Alert tone="danger">{getErrorMessage(save.error)}</Alert>}
      </div>
    </Dialog>
  );
}

/** How the assistant is doing, from what people asked and how they rated the answers. */
export function UsageTab() {
  const [days, setDays] = useState(30);
  const query = useStats(days);
  return (
    <div className="stack stack--tight">
      <div className="filter-bar">
        <Field label="Period">
          {(c) => (
            <Select {...c} value={String(days)} onChange={(e) => setDays(Number(e.target.value))}>
              {[7, 30, 90, 365].map((d) => (
                <option key={d} value={d}>
                  Last {d} days
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="assistant usage">
        {(s) => (
          <>
            <div className="grid-3">
              <MetricTile icon={<BookOpen size={22} />} label="Questions asked" value={formatNumber(s.questions)} />
              <MetricTile
                icon={<BookOpen size={22} />}
                tone="blue"
                label="Answered from articles or accounts"
                value={formatNumber(s.answered_from_knowledge + s.answered_from_account)}
                note={`${formatNumber(s.answered_from_knowledge)} articles, ${formatNumber(s.answered_from_account)} accounts`}
              />
              <MetricTile icon={<BookOpen size={22} />} tone="amber" label="Not answered" value={formatNumber(s.no_answer)} note={`${formatNumber(s.not_permitted)} refused for role`} />
              <MetricTile
                icon={<BookOpen size={22} />}
                tone="teal"
                label="Rated helpful"
                value={s.rated === 0 ? 'n/a' : formatPercent(s.rated_helpful / s.rated)}
                note={`${formatNumber(s.rated)} answers rated`}
              />
            </div>
            <p className="muted">Ratings come from the people who chose to give one, so they are not a measure of every answer. Questions that went unanswered are the best list of articles to write.</p>
          </>
        )}
      </QueryBoundary>
    </div>
  );
}
