import { useState, type ComponentType } from 'react';
import { Armchair, Box, Container, Cpu, FileText, Leaf, Shirt, Store, TreePine, Wine, Wrench } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Choice';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select, Textarea } from '@/components/ui/Input';
import { ReasonDialog } from '@/components/ui/ReasonDialog';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination } from '@/components/ui/Table';
import { useFacilityOptions } from '@/features/facilities';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, formatNumber, humanize } from '@/utils/format';
import { CATEGORIES, CONDITIONS, UNITS, type Listing, type ListingRequest } from '../api/marketplace-api';
import {
  useAskForListing,
  useCloseListing,
  useDecideRequest,
  useListing,
  useListingRequests,
  useListings,
  useMyRequests,
  usePublishListing,
  useSaveListing,
} from '../hooks/useMarketplace';
import '../marketplace.css';

const ICONS: Record<string, ComponentType<{ size?: number }>> = {
  plastics: Container,
  metals: Wrench,
  paper: FileText,
  glass: Wine,
  e_waste: Cpu,
  organics: Leaf,
  textiles: Shirt,
  wood: TreePine,
  furniture: Armchair,
  other: Box,
};
const LISTING_TONES: Record<string, BadgeTone> = { draft: 'neutral', published: 'success', reserved: 'warning', closed: 'neutral' };
const REQUEST_TONES: Record<string, BadgeTone> = { pending: 'info', accepted: 'success', declined: 'neutral', withdrawn: 'neutral' };
const label = (category: string) => (category === 'e_waste' ? 'E-waste' : humanize(category));
const quantityText = (l: Listing) => `${formatNumber(l.quantity)} ${l.unit}`;

export function MarketplacePage() {
  const { can } = useAuth();
  const canCreate = can('marketplace:create');
  const [filters, setFilters] = useState({ page: 1, q: '', category: '', mine: false });
  const [open, setOpen] = useState<Listing | null>(null);
  const [editing, setEditing] = useState<Listing | 'new' | null>(null);
  const query = useListings(filters);
  const mine = useMyRequests(can('marketplace:request'));
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  return (
    <section aria-labelledby="market-title" className="stack stack--tight">
      <PageHeader
        title="Circular surplus marketplace"
        titleId="market-title"
        subtitle="Offer surplus material for reuse and ask for what you can use. There is no payment or delivery here: owners and requesters arrange hand-over themselves."
        actions={canCreate ? <Button onClick={() => setEditing('new')}>New listing</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Title, description or city" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        {canCreate && <Switch label="My listings only" checked={filters.mine} onChange={(e) => set({ mine: e.target.checked })} />}
      </div>
      <div className="chips" role="group" aria-label="Category">
        {[['', 'All'], ...CATEGORIES.map((c) => [c, label(c)])].map(([value, text]) => (
          <button key={value} type="button" className="chip" aria-pressed={filters.category === value} onClick={() => set({ category: value ?? '' })}>
            {text}
          </button>
        ))}
      </div>
      <QueryBoundary query={query} label="listings">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState
              icon={<Store size={24} />}
              title="No listings"
              description={canCreate ? 'Nothing matches these filters. Use "New listing" to offer surplus material.' : 'Nothing matches these filters yet.'}
            />
          ) : (
            <>
              <ul className="listing-grid" aria-label="Listings" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {data.items.map((l) => {
                  const Icon = ICONS[l.category] ?? Box;
                  return (
                    <li key={l.id} className="listing">
                      <div className="listing__art" aria-hidden="true"><Icon size={40} /></div>
                      <div className="listing__body">
                        <h3 className="listing__title">{l.title}</h3>
                        <p className="muted">{quantityText(l)} · {humanize(l.condition)} condition</p>
                        <div className="listing__meta">
                          <StatusBadge value={l.status} tones={LISTING_TONES} />
                          <span className="muted">{label(l.category)}</span>
                          {l.is_mine && <span className="muted">Yours</span>}
                        </div>
                        <p className="muted">{l.facility_name ?? l.pickup_city ?? l.owner_name}</p>
                        <div className="listing__actions">
                          <Button variant="secondary" onClick={() => setOpen(l)} aria-label={`Open listing: ${l.title}`}>Open</Button>
                          {l.pending_request_count ? <span className="muted">{l.pending_request_count} pending request{l.pending_request_count === 1 ? '' : 's'}</span> : null}
                          {l.my_request_status && <StatusBadge value={l.my_request_status} tones={REQUEST_TONES} />}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} listing${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {mine.data && mine.data.items.length > 0 && (
        <section aria-labelledby="my-requests-title" className="stack stack--tight">
          <h2 id="my-requests-title" className="card__title">My requests</h2>
          <ul className="request-list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {mine.data.items.map((r) => (
              <li key={r.id} className="request">
                <div><strong>{r.listing_title}</strong> <StatusBadge value={r.status} tones={REQUEST_TONES} /></div>
                <p className="muted">Asked {formatDateTime(r.created_at)}{r.decided_at ? ` · decided ${formatDateTime(r.decided_at)}` : ''}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
      {open && <ListingDialog listing={open} onClose={() => setOpen(null)} onEdit={(l) => { setOpen(null); setEditing(l); }} />}
      {editing && <EditDialog listing={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

function EditDialog({ listing, onClose }: { listing: Listing | null; onClose: () => void }) {
  const save = useSaveListing();
  const facilities = useFacilityOptions();
  const { values, bind } = useFields({
    title: listing?.title ?? '',
    description: listing?.description ?? '',
    category: listing?.category ?? 'furniture',
    quantity: listing ? String(listing.quantity) : '',
    unit: listing?.unit ?? 'units',
    condition: listing?.condition ?? 'good',
    facility_id: listing?.facility_id ?? '',
    pickup_city: listing?.pickup_city ?? '',
  });
  const quantity = Number(values.quantity);
  const valid = values.title.trim().length >= 3 && Number.isFinite(quantity) && quantity > 0;
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={listing ? 'Edit listing' : 'New listing'}
      description={listing ? undefined : 'The listing starts as a draft that only you and managers can see. Publish it when it is ready.'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={save.isPending}
            disabled={!valid}
            onClick={() =>
              save.mutate(
                {
                  id: listing?.id,
                  body: {
                    title: values.title.trim(),
                    description: optional(values.description),
                    category: values.category,
                    quantity: values.quantity.trim(),
                    unit: values.unit,
                    condition: values.condition,
                    facility_id: values.facility_id || null,
                    pickup_city: optional(values.pickup_city),
                  },
                },
                { onSuccess: onClose },
              )
            }
          >
            {listing ? 'Save changes' : 'Create draft'}
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Title">{(c) => <Input {...c} data-autofocus maxLength={200} {...bind('title')} />}</Field>
        <Field label="Category">{(c) => <Select {...c} {...bind('category')}>{CATEGORIES.map((v) => <option key={v} value={v}>{label(v)}</option>)}</Select>}</Field>
        <Field label="Quantity">{(c) => <Input {...c} inputMode="decimal" {...bind('quantity')} />}</Field>
        <Field label="Unit">{(c) => <Select {...c} {...bind('unit')}>{UNITS.map((v) => <option key={v} value={v}>{v}</option>)}</Select>}</Field>
        <Field label="Condition">{(c) => <Select {...c} {...bind('condition')}>{CONDITIONS.map((v) => <option key={v} value={v}>{humanize(v)}</option>)}</Select>}</Field>
        <Field label="Facility (optional)">
          {(c) => (
            <Select {...c} {...bind('facility_id')}>
              <option value="">None</option>
              {(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Pickup city (optional)">{(c) => <Input {...c} maxLength={120} {...bind('pickup_city')} />}</Field>
      </div>
      <Field label="Description (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('description')} />}</Field>
      {save.isError && <Alert tone="danger">{getErrorMessage(save.error)}</Alert>}
    </Dialog>
  );
}

function ListingDialog({ listing, onClose, onEdit }: { listing: Listing; onClose: () => void; onEdit: (l: Listing) => void }) {
  const { can } = useAuth();
  const { data: current } = useListing(listing);
  const controls = current.is_mine || can('marketplace:manage');
  const requests = useListingRequests(current.id, controls);
  const ask = useAskForListing();
  const publish = usePublishListing();
  const close = useCloseListing();
  const decide = useDecideRequest();
  const [closing, setClosing] = useState(false);
  const { values, bind } = useFields({ message: '' });
  const mineStatus = current.my_request_status;
  const canAsk = !current.is_mine && can('marketplace:request') && current.status === 'published' && (mineStatus === null || mineStatus === 'withdrawn');
  const editable = controls && (current.status === 'draft' || current.status === 'published');
  const error = ask.error ?? publish.error ?? decide.error;

  return (
    <>
      <Dialog open wide onClose={onClose} title={current.title} footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
        <div className="stack stack--tight">
          <div className="listing__meta">
            <StatusBadge value={current.status} tones={LISTING_TONES} />
            <span className="muted">{label(current.category)}</span>
          </div>
          <dl className="detail-list">
            <dt>Quantity</dt><dd>{quantityText(current)}</dd>
            <dt>Condition</dt><dd>{humanize(current.condition)}</dd>
            <dt>Offered by</dt><dd>{current.owner_name}</dd>
            {current.facility_name && (<><dt>Facility</dt><dd>{current.facility_name}</dd></>)}
            {current.pickup_city && (<><dt>Pickup city</dt><dd>{current.pickup_city}</dd></>)}
            {current.description && (<><dt>Description</dt><dd>{current.description}</dd></>)}
            {current.published_at && (<><dt>Published</dt><dd>{formatDateTime(current.published_at)}</dd></>)}
            {current.close_reason && (<><dt>Closed because</dt><dd>{current.close_reason}</dd></>)}
          </dl>

          {controls && current.status !== 'closed' && (
            <div className="listing__actions" role="group" aria-label="Listing actions">
              {current.status === 'draft' && <Button loading={publish.isPending} onClick={() => publish.mutate(current.id)}>Publish</Button>}
              {editable && <Button variant="secondary" onClick={() => onEdit(current)}>Edit</Button>}
              <Button variant="danger" onClick={() => setClosing(true)}>Close listing</Button>
            </div>
          )}

          {controls && (
            <section aria-label="Requests" className="stack stack--tight">
              <h3 className="task__title">Requests</h3>
              {requests.isError && <Alert tone="danger">{getErrorMessage(requests.error)}</Alert>}
              {requests.data?.length === 0 && <p className="muted">Nobody has asked for this listing yet.</p>}
              <ul className="request-list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {(requests.data ?? []).map((r) => (
                  <RequestRow key={r.id} request={r} busy={decide.isPending} onDecide={(action) => decide.mutate({ id: r.id, action })} />
                ))}
              </ul>
            </section>
          )}

          {!controls && mineStatus && (
            <div className="stack stack--tight">
              <p>Your request: <StatusBadge value={mineStatus} tones={REQUEST_TONES} /></p>
              {(mineStatus === 'pending' || mineStatus === 'accepted') && (
                <RequestWithdraw listingId={current.id} />
              )}
            </div>
          )}

          {canAsk && (
            <div className="stack stack--tight" role="group" aria-label="Ask for this listing">
              <Field label="Message to the owner (optional)" hint="Your e-mail address is shared with the owner so you can arrange pickup.">
                {(c) => <Textarea {...c} maxLength={2000} {...bind('message')} />}
              </Field>
              <div>
                <Button loading={ask.isPending} onClick={() => ask.mutate({ id: current.id, message: optional(values.message) })}>Request this</Button>
              </div>
            </div>
          )}
          {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
        </div>
      </Dialog>
      {closing && (
        <ReasonDialog
          title="Close this listing?"
          description="Pending requests are declined and the listing leaves the marketplace. This cannot be undone."
          required={false}
          submitLabel="Close listing"
          destructive
          pending={close.isPending}
          error={close.error}
          onSubmit={(reason) => close.mutate({ id: current.id, reason: reason || undefined }, { onSuccess: () => setClosing(false) })}
          onClose={() => setClosing(false)}
        />
      )}
    </>
  );
}

function RequestWithdraw({ listingId }: { listingId: string }) {
  const requests = useMyRequests(true);
  const decide = useDecideRequest();
  const mine = requests.data?.items.find((r) => r.listing_id === listingId);
  if (!mine) return null;
  return (
    <div>
      <Button variant="secondary" loading={decide.isPending} onClick={() => decide.mutate({ id: mine.id, action: 'withdraw' })}>Withdraw request</Button>
      {decide.isError && <Alert tone="danger">{getErrorMessage(decide.error)}</Alert>}
    </div>
  );
}

function RequestRow({ request, busy, onDecide }: { request: ListingRequest; busy: boolean; onDecide: (a: 'accept' | 'decline') => void }) {
  return (
    <li className="request">
      <div>
        <strong>{request.requester_name}</strong> <StatusBadge value={request.status} tones={REQUEST_TONES} />
        {request.requester_email && <p className="muted">{request.requester_email}</p>}
      </div>
      {request.message && <p>{request.message}</p>}
      <p className="muted">Asked {formatDateTime(request.created_at)}</p>
      <div className="listing__actions">
        {request.status === 'pending' && (
          <>
            <Button disabled={busy} onClick={() => onDecide('accept')} aria-label={`Accept request from ${request.requester_name}`}>Accept</Button>
            <Button variant="secondary" disabled={busy} onClick={() => onDecide('decline')} aria-label={`Decline request from ${request.requester_name}`}>Decline</Button>
          </>
        )}
        {request.status === 'accepted' && (
          <Button variant="secondary" disabled={busy} onClick={() => onDecide('decline')} aria-label={`Release reservation for ${request.requester_name}`}>Release reservation</Button>
        )}
      </div>
    </li>
  );
}
