import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { errorReply, page, routeApi } from '../helpers/api-mock';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const id = (n: number) => `${String(n).repeat(8)}-${String(n).repeat(4)}-4${String(n).repeat(3)}-8${String(n).repeat(3)}-${String(n).repeat(12)}`;

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

const message = (over: Record<string, unknown> = {}) => ({
  id: id(1), role: 'assistant', kind: 'knowledge', content: 'Open Reports and choose New report.', sources: [{ kind: 'article', id: id(5), title: 'Report a problem' }],
  helpful: null, created_at: '2026-10-21T08:00:00Z', ...over,
});
const answer = (reply: Record<string, unknown>, over: Record<string, unknown> = {}) => ({
  conversation_id: id(7),
  question: message({ id: id(2), role: 'user', kind: 'question', content: 'How do I report?', sources: [] }),
  reply: message(reply),
  suggest_ticket: reply.kind === 'no_answer',
  ...over,
});
const ticket = (over: Record<string, unknown> = {}) => ({
  id: id(3), user_id: id(9), requester_name: 'Asha Rao', subject: 'Missed pickup', status: 'open', assignee_id: null, assignee_name: null, reply_count: 0,
  conversation_shared: false, created_at: '2026-10-21T07:00:00Z', updated_at: '2026-10-21T07:00:00Z', resolved_at: null, ...over,
});
const detail = (over: Record<string, unknown> = {}) => ({ ...ticket(), body: 'The truck skipped our street.', replies: [], conversation: null, ...over });

const citizen = userWith(['support:ask'], { roles: ['citizen'] });
const manager = userWith(['support:ask', 'support:manage', 'knowledge:manage'], { roles: ['manager'] });

describe('help assistant', () => {
  it('shows an answer with its origin and sources, and lets the person rate it', async () => {
    const api = routeApi(fetchSpy, {
      'POST /api/v1/support/assistant/messages': answer({}),
      [`POST /api/v1/support/assistant/messages/${id(1)}/feedback`]: message({ helpful: true }),
    }, citizen);
    renderAt('/assistant');
    await userEvent.type(await screen.findByLabelText(/Your question/), 'How do I report?');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText('Open Reports and choose New report.')).toBeInTheDocument();
    expect(screen.getByText('From the help articles')).toBeInTheDocument();
    expect(screen.getByText('Report a problem')).toBeInTheDocument();
    expect(api.calls[0]?.body).toEqual({ message: 'How do I report?' });

    await userEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Helpful' })).toHaveAttribute('aria-pressed', 'true'));
    expect(api.calls.at(-1)?.body).toEqual({ helpful: true });
  });

  it('continues the same conversation on the next question', async () => {
    let turn = 0;
    const api = routeApi(fetchSpy, {
      'POST /api/v1/support/assistant/messages': () => {
        turn += 1;
        return answer({ id: id(2 + turn) }, { question: message({ id: id(5 + turn), role: 'user', kind: 'question', content: `q${turn}`, sources: [] }) });
      },
    }, citizen);
    renderAt('/assistant');
    const box = await screen.findByLabelText(/Your question/);
    await userEvent.type(box, 'first question');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await screen.findByText('From the help articles');
    await userEvent.type(screen.getByLabelText(/Your question/), 'second question');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(api.calls).toHaveLength(2));
    expect(api.calls[1]?.body).toEqual({ message: 'second question', conversation_id: id(7) });
  });

  it('says plainly when it has no answer, offers related articles, and hands the question to staff only with consent', async () => {
    const api = routeApi(fetchSpy, {
      'POST /api/v1/support/assistant/messages': answer({
        kind: 'no_answer', content: 'I could not find a reliable answer to that.', sources: [{ kind: 'article', id: id(6), title: 'Missed collections' }],
      }),
      'POST /api/v1/support/tickets': detail({ conversation_shared: true }),
      'GET /api/v1/support/tickets/mine': page([]),
    }, citizen);
    renderAt('/assistant');
    await userEvent.type(await screen.findByLabelText(/Your question/), 'my lorry did not come today');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText('No answer found')).toBeInTheDocument();
    expect(screen.getByText(/may be related \(not confirmed answers\)/)).toBeInTheDocument();
    expect(screen.getByText('Missed collections')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Send this to the support team' }));
    const dialog = await screen.findByRole('dialog', { name: 'Ask the support team' });
    const share = within(dialog).getByRole('checkbox', { name: /read my chat/ });
    expect(share).not.toBeChecked(); // never on by default
    await userEvent.click(share);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Send request' }));
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/support/tickets')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/support/tickets')?.body).toEqual({
      // The question text is what the server stored for the last question (the mock echoes a fixed one).
      subject: 'How do I report?', body: 'How do I report?', conversation_id: id(7), share_conversation: true,
    });
  });

  it('renders replies as text, never as markup', async () => {
    routeApi(fetchSpy, { 'POST /api/v1/support/assistant/messages': answer({ content: '<img src=x onerror=alert(1)> <b>bold</b>', sources: [] }) }, citizen);
    renderAt('/assistant');
    await userEvent.type(await screen.findByLabelText(/Your question/), 'anything');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText('<img src=x onerror=alert(1)> <b>bold</b>')).toBeInTheDocument();
    expect(document.querySelector('.chat__text img, .chat__text b')).toBeNull();
  });

  it('shows the server message when it refuses, for example after too many questions', async () => {
    routeApi(fetchSpy, { 'POST /api/v1/support/assistant/messages': errorReply(429, 'rate_limited', 'You are asking too fast. Try again in a few minutes.') }, citizen);
    renderAt('/assistant');
    await userEvent.type(await screen.findByLabelText(/Your question/), 'anything');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText('You are asking too fast. Try again in a few minutes.')).toBeInTheDocument();
  });

  it('does not let the ask button send an empty question', async () => {
    const api = routeApi(fetchSpy, {}, citizen);
    renderAt('/assistant');
    await screen.findByLabelText(/Your question/);
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(api.calls).toHaveLength(0);
  });

  it('is not available to someone without the permission', async () => {
    routeApi(fetchSpy, {}, userWith(['rewards:read_own'], { roles: ['citizen'] }));
    renderAt('/assistant');
    expect(await screen.findByRole('heading', { name: /not allowed|permission|access/i })).toBeInTheDocument();
  });
});

describe('support requests', () => {
  it('lists my requests and opens one with its replies', async () => {
    routeApi(fetchSpy, {
      'GET /api/v1/support/tickets/mine': page([ticket({ reply_count: 1 })]),
      [`GET /api/v1/support/tickets/${id(3)}`]: detail({
        status: 'in_progress', assignee_name: 'Sam Lee', replies: [{ id: id(4), author_id: id(8), author_name: 'Sam Lee', is_staff: true, body: 'We are checking the route.', created_at: '2026-10-21T09:00:00Z' }],
      }),
    }, citizen);
    renderAt('/support');
    expect(screen.queryByRole('tab', { name: 'Support queue' })).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Open request: Missed pickup' }));
    const dialog = await screen.findByRole('dialog', { name: 'Missed pickup' });
    expect(await within(dialog).findByText('We are checking the route.')).toBeInTheDocument();
    expect(within(dialog).getByText('Support team')).toBeInTheDocument();
    expect(within(dialog).queryByLabelText('Change status')).not.toBeInTheDocument(); // staff control
    expect(within(dialog).getByRole('button', { name: 'Close this request' })).toBeInTheDocument();
  });

  it('shows an honest empty state', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/support/tickets/mine': page([]) }, citizen);
    renderAt('/support');
    expect(await screen.findByRole('heading', { name: 'You have no support requests' })).toBeInTheDocument();
  });

  it('creates a request and refuses a too-short one before calling the server', async () => {
    const api = routeApi(fetchSpy, { 'GET /api/v1/support/tickets/mine': page([]), 'POST /api/v1/support/tickets': detail() }, citizen);
    renderAt('/support');
    await userEvent.click(await screen.findByRole('button', { name: 'New request' }));
    const dialog = await screen.findByRole('dialog', { name: 'Ask the support team' });
    expect(within(dialog).queryByRole('checkbox')).not.toBeInTheDocument(); // no chat to share from here
    await userEvent.type(within(dialog).getByLabelText(/Subject/), 'Hi');
    await userEvent.type(within(dialog).getByLabelText(/What do you need help with/), 'short');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Send request' }));
    expect(api.calls.filter((c) => c.key === 'POST /api/v1/support/tickets')).toHaveLength(0);

    await userEvent.type(within(dialog).getByLabelText(/Subject/), ' there');
    await userEvent.type(within(dialog).getByLabelText(/What do you need help with/), ' and more detail');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Send request' }));
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/support/tickets')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/support/tickets')?.body).toMatchObject({ subject: 'Hi there', share_conversation: false });
  });
});

describe('support desk (staff)', () => {
  const routes = () => ({
    'GET /api/v1/support/tickets/mine': page([]),
    'GET /api/v1/support/tickets': page([ticket()]),
    [`GET /api/v1/support/tickets/${id(3)}`]: detail({ conversation: [message({ id: id(2), role: 'user', kind: 'question', content: 'where is my truck', sources: [] })], conversation_shared: true }),
  });

  it('shows the queue with requesters, and the shared chat only inside a ticket', async () => {
    routeApi(fetchSpy, routes(), manager);
    renderAt('/support');
    await userEvent.click(await screen.findByRole('tab', { name: 'Support queue' }));
    expect(await screen.findByText('Asha Rao')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Open request: Missed pickup' }));
    const dialog = await screen.findByRole('dialog', { name: 'Missed pickup' });
    expect(await within(dialog).findByText('Chat the requester chose to share')).toBeInTheDocument();
    expect(within(dialog).getByText('where is my truck')).toBeInTheDocument();
  });

  it('offers only the allowed next statuses, assigns to me, and shows the server message when a change is refused', async () => {
    const api = routeApi(fetchSpy, {
      ...routes(),
      [`PATCH /api/v1/support/tickets/${id(3)}`]: (call: { body: unknown }) =>
        (call.body as { status?: string }).status === 'closed' ? errorReply(409, 'invalid_status_change', 'A ticket needs a reply before it is closed.') : detail({ assignee_id: id(9), assignee_name: 'Me' }),
    }, manager);
    renderAt('/support');
    await userEvent.click(await screen.findByRole('tab', { name: 'Support queue' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Open request: Missed pickup' }));
    const dialog = await screen.findByRole('dialog', { name: 'Missed pickup' });
    const status = await within(dialog).findByLabelText('Change status');
    expect(within(status).getAllByRole('option').map((o) => o.textContent)).toEqual(['Keep open', 'Mark as in progress', 'Mark as resolved', 'Mark as closed']);

    await userEvent.click(within(dialog).getByRole('button', { name: 'Assign to me' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.startsWith('PATCH'))).toBe(true));
    expect(api.calls.find((c) => c.key.startsWith('PATCH'))?.body).toEqual({ assign_to_me: true });

    await userEvent.selectOptions(status, 'closed');
    expect(await within(dialog).findByText('A ticket needs a reply before it is closed.')).toBeInTheDocument();
  });

  it('filters the queue on the server', async () => {
    const api = routeApi(fetchSpy, routes(), manager);
    renderAt('/support');
    await userEvent.click(await screen.findByRole('tab', { name: 'Support queue' }));
    await screen.findByText('Asha Rao');
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'resolved');
    await waitFor(() => expect(api.calls.some((c) => c.key === 'GET /api/v1/support/tickets' && c.query.get('status') === 'resolved')).toBe(true));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Unassigned' }));
    await waitFor(() => expect(api.calls.some((c) => c.query.get('unassigned') === 'true')).toBe(true));
  });

  it('shows assistant usage without inventing a rate when nothing was rated', async () => {
    routeApi(fetchSpy, {
      ...routes(),
      'GET /api/v1/support/assistant/stats': { since: '2026-09-21T00:00:00Z', questions: 12, answered_from_knowledge: 7, answered_from_account: 2, no_answer: 3, not_permitted: 0, rated: 0, rated_helpful: 0 },
    }, manager);
    renderAt('/support');
    await userEvent.click(await screen.findByRole('tab', { name: 'Assistant usage' }));
    expect(await screen.findByText('Questions asked')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('n/a')).toBeInTheDocument();
  });
});

describe('help article editor', () => {
  const article = (over: Record<string, unknown> = {}) => ({
    id: id(5), slug: 'report-a-problem', title: 'Report a problem', body: 'Open Reports and choose New report to describe the problem.', category: 'Reports',
    keywords: 'rubbish dump', source: 'Reports screen', published: true, updated_at: '2026-10-20T08:00:00Z', ...over,
  });
  const routes = () => ({
    'GET /api/v1/support/tickets/mine': page([]),
    'GET /api/v1/support/articles': page([article(), article({ id: id(6), title: 'Old draft', published: false })]),
    'GET /api/v1/support/articles/categories': ['Reports'],
  });

  it('lists published and unpublished articles and edits keywords', async () => {
    const api = routeApi(fetchSpy, { ...routes(), [`PATCH /api/v1/support/articles/${id(5)}`]: article({ keywords: 'rubbish dump litter' }) }, manager);
    renderAt('/support');
    await userEvent.click(await screen.findByRole('tab', { name: 'Help articles' }));
    expect(await screen.findByText('Old draft')).toBeInTheDocument();
    expect(screen.getByText('Unpublished')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Edit article: Report a problem' }));
    const dialog = await screen.findByRole('dialog', { name: 'Edit article' });
    expect(within(dialog).queryByLabelText(/Slug/)).not.toBeInTheDocument(); // fixed after creation
    await userEvent.type(within(dialog).getByLabelText('Keywords'), ' litter');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save article' }));
    await waitFor(() => expect(api.calls.some((c) => c.key.startsWith('PATCH'))).toBe(true));
    expect(api.calls.find((c) => c.key.startsWith('PATCH'))?.body).toMatchObject({ keywords: 'rubbish dump litter', published: true });
  });

  it('needs a valid slug and complete text before a new article can be saved', async () => {
    const api = routeApi(fetchSpy, { ...routes(), 'POST /api/v1/support/articles': article() }, manager);
    renderAt('/support');
    await userEvent.click(await screen.findByRole('tab', { name: 'Help articles' }));
    await userEvent.click(await screen.findByRole('button', { name: 'New article' }));
    const dialog = await screen.findByRole('dialog', { name: 'New article' });
    await userEvent.type(within(dialog).getByLabelText(/Slug/), 'Not A Slug');
    await userEvent.type(within(dialog).getByLabelText(/Title/), 'A new article');
    await userEvent.type(within(dialog).getByLabelText(/Answer text/), 'Enough words here to pass the minimum length.');
    await userEvent.type(within(dialog).getByLabelText(/Category/), 'Reports');
    await userEvent.type(within(dialog).getByLabelText(/^Source/), 'Policy 4');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save article' }));
    expect(api.calls.filter((c) => c.key.startsWith('POST'))).toHaveLength(0);
    await userEvent.clear(within(dialog).getByLabelText(/Slug/));
    await userEvent.type(within(dialog).getByLabelText(/Slug/), 'a-new-article');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save article' }));
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /api/v1/support/articles')).toBe(true));
    expect(api.calls.find((c) => c.key === 'POST /api/v1/support/articles')?.body).toMatchObject({ slug: 'a-new-article', published: true });
  });

  it('hides the editor from people who cannot manage articles', async () => {
    routeApi(fetchSpy, routes(), userWith(['support:ask', 'support:manage'], { roles: ['collector'] }));
    renderAt('/support');
    await screen.findByRole('tab', { name: 'Support queue' });
    expect(screen.queryByRole('tab', { name: 'Help articles' })).not.toBeInTheDocument();
  });
});
