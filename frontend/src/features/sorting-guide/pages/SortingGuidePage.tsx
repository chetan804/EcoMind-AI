import { useState } from 'react';
import { BookOpen } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Switch } from '@/components/ui/Choice';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select, Textarea } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { humanize } from '@/utils/format';
import { DISPOSAL_METHODS, type Guidance } from '../api/guide-api';
import { useCategories, useCreateCategory, useCreateGuidance, useGuidance, useUpdateGuidance } from '../hooks/useGuide';

export function SortingGuidePage() {
  const { can } = useAuth();
  const manage = can('sorting_guide:manage');
  const [filters, setFilters] = useState({ page: 1, q: '', category_id: '', disposal_method: '', include_inactive: false });
  const [dialog, setDialog] = useState<'guidance' | 'category' | null>(null);
  const categories = useCategories(manage);
  const query = useGuidance(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const toggle = useUpdateGuidance();

  return (
    <section aria-labelledby="guide-title" className="stack stack--tight">
      <PageHeader
        title="Material sorting guide"
        titleId="guide-title"
        subtitle="How to prepare and dispose of each material. Every entry shows its source, or says it has none."
        actions={
          manage ? (
            <>
              <Button variant="secondary" onClick={() => setDialog('category')}>Add category</Button>
              <Button onClick={() => setDialog('guidance')}>Add guidance</Button>
            </>
          ) : undefined
        }
      />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Title or instructions" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Material">
          {(c) => (
            <Select {...c} value={filters.category_id} onChange={(e) => set({ category_id: e.target.value })}>
              <option value="">All materials</option>
              {(categories.data ?? []).map((cat) => <option key={cat.id} value={cat.id}>{cat.name}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Disposal">
          {(c) => (
            <Select {...c} value={filters.disposal_method} onChange={(e) => set({ disposal_method: e.target.value })}>
              <option value="">Any method</option>
              {DISPOSAL_METHODS.map((m) => <option key={m} value={m}>{humanize(m)}</option>)}
            </Select>
          )}
        </Field>
        {manage && <Switch label="Show inactive" checked={filters.include_inactive} onChange={(e) => set({ include_inactive: e.target.checked })} />}
      </div>
      {toggle.isError && <Alert tone="danger">{getErrorMessage(toggle.error)}</Alert>}
      <QueryBoundary query={query} label="sorting guidance">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState
              icon={<BookOpen size={24} />}
              title="No sorting guidance published"
              description={manage ? 'Add guidance for a material category and cite where the rule comes from.' : 'Nothing has been published yet. Local rules differ, so none is assumed here.'}
            />
          ) : (
            <>
              <div className="guide-grid">
                {data.items.map((g) => (
                  <GuidanceCard key={g.id} guidance={g} manage={manage} busy={toggle.isPending} onToggle={() => toggle.mutate({ id: g.id, body: { is_active: !g.is_active } })} />
                ))}
              </div>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} entr${data.total === 1 ? 'y' : 'ies'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {dialog === 'guidance' && <GuidanceDialog onClose={() => setDialog(null)} />}
      {dialog === 'category' && <CategoryDialog onClose={() => setDialog(null)} />}
    </section>
  );
}

function GuidanceCard({ guidance: g, manage, busy, onToggle }: { guidance: Guidance; manage: boolean; busy: boolean; onToggle: () => void }) {
  return (
    <Card aria-label={g.title}>
      <div className="guide-card__head">
        <Badge tone="info">{g.category_name}</Badge>
        <Badge tone="neutral">{humanize(g.disposal_method)}</Badge>
        {!g.is_active && <Badge tone="warning">Inactive</Badge>}
      </div>
      <h2 className="guide-card__title">{g.title}</h2>
      <p>{g.instructions}</p>
      {g.preparation_notes && <p><strong>Before you dispose:</strong> {g.preparation_notes}</p>}
      <p className="muted">{g.has_source ? `Source: ${g.source_reference}` : 'No source cited. Treat as unverified.'}</p>
      {manage && (
        <Button variant="secondary" loading={busy} onClick={onToggle}>
          {g.is_active ? 'Deactivate' : 'Activate'}
        </Button>
      )}
    </Card>
  );
}

function GuidanceDialog({ onClose }: { onClose: () => void }) {
  const categories = useCategories(false);
  const create = useCreateGuidance();
  const { values, bind } = useFields({ category: '', method: 'recycle', title: '', instructions: '', prep: '', source: '' });
  const valid = values.category !== '' && values.title.trim().length >= 3 && values.instructions.trim().length >= 3;
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Add sorting guidance"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={create.isPending}
            disabled={!valid}
            onClick={() =>
              create.mutate(
                { material_category_id: values.category, disposal_method: values.method, title: values.title.trim(), instructions: values.instructions.trim(), preparation_notes: optional(values.prep), source_reference: optional(values.source) },
                { onSuccess: onClose },
              )
            }
          >
            Add guidance
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Material">
          {(c) => <Select {...c} data-autofocus {...bind('category')}><option value="">Choose a material</option>{(categories.data ?? []).map((cat) => <option key={cat.id} value={cat.id}>{cat.name}</option>)}</Select>}
        </Field>
        <Field label="Disposal method">{(c) => <Select {...c} {...bind('method')}>{DISPOSAL_METHODS.map((m) => <option key={m} value={m}>{humanize(m)}</option>)}</Select>}</Field>
        <Field label="Title">{(c) => <Input {...c} {...bind('title')} />}</Field>
        <Field label="Instructions">{(c) => <Textarea {...c} maxLength={5000} {...bind('instructions')} />}</Field>
        <Field label="Preparation notes (optional)">{(c) => <Textarea {...c} maxLength={5000} {...bind('prep')} />}</Field>
        <Field label="Source (optional but expected)" hint="The regulation, municipal page or standard this rule comes from">{(c) => <Input {...c} maxLength={500} {...bind('source')} />}</Field>
        {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
      </div>
    </Dialog>
  );
}

function CategoryDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateCategory();
  const { values, bind } = useFields({ code: '', name: '', description: '' });
  return (
    <Dialog
      open
      onClose={onClose}
      title="Add material category"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={values.code.trim().length < 2 || values.name.trim().length < 2} onClick={() => create.mutate({ code: values.code.trim(), name: values.name.trim(), description: optional(values.description) }, { onSuccess: onClose })}>
            Add category
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Code" hint="Lower-case identifier, for example battery">{(c) => <Input {...c} data-autofocus {...bind('code')} />}</Field>
        <Field label="Name">{(c) => <Input {...c} {...bind('name')} />}</Field>
        <Field label="Description (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('description')} />}</Field>
        {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
      </div>
    </Dialog>
  );
}
