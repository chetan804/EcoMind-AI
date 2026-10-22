import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider } from 'react-router/dom';
import { createTestRouter } from '@/app/router';
import { authResponse, dataCalls, resetSession, signInViaRefresh, testUser } from '../helpers/session';

const fetchSpy = vi.fn();

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() }));
});
afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createTestRouter([path])} />
    </QueryClientProvider>,
  );
}

describe('landing page', () => {
  it('renders the hero without the application shell and links to sign-up', async () => {
    renderAt('/');
    expect(await screen.findByRole('heading', { level: 1, name: /Waste Management/ })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Get started' })).toHaveAttribute('href', '/sign-up');
    expect(screen.getByRole('link', { name: 'Explore platform' })).toHaveAttribute('href', '/dashboard');
  });

  it('does not claim unavailable things: the demo is unavailable and facts are not performance claims', async () => {
    renderAt('/');
    const demo = await screen.findByRole('button', { name: 'Watch demo' });
    expect(demo).toHaveAttribute('aria-disabled', 'true');
    expect(demo).toHaveAccessibleDescription('No product demo is available yet.');
    expect(screen.getByText('Classifiers approved for use')).toBeInTheDocument();
    expect(screen.queryByText(/accuracy/i)).not.toBeInTheDocument();
    expect(screen.getByText(/under active development/i)).toBeInTheDocument();
  });

  it('exposes in-page section links that have a target', async () => {
    renderAt('/');
    await screen.findByRole('heading', { level: 1 });
    const nav = screen.getByRole('navigation', { name: 'Sections' });
    for (const link of within(nav).getAllByRole('link')) {
      const id = link.getAttribute('href')?.slice(1) ?? '';
      expect(document.getElementById(id), `target for ${link.textContent}`).not.toBeNull();
    }
  });
});

describe('application navigation', () => {
  beforeEach(() => signInViaRefresh(fetchSpy));

  it('lists the primary destinations and never includes Smart Bins & Telemetry', async () => {
    renderAt('/dashboard');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const labels = within(nav).getAllByRole('link').map((a) => a.textContent ?? '');
    expect(labels.some((l) => l.startsWith('Dashboard'))).toBe(true);
    expect(labels.some((l) => l.startsWith('Classification'))).toBe(true);
    expect(document.body.textContent).not.toMatch(/smart bins?|telemetry/i);
    expect(labels.join(' ')).not.toMatch(/\bbins?\b/i);
  });

  it('marks the current page, and no destination is flagged "Soon" now that every entry is built', async () => {
    renderAt('/dashboard');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: /^Dashboard/ })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: /^Marketplace/ })).not.toHaveTextContent('Soon');
    expect(within(nav).getByRole('link', { name: /^Marketplace/ })).toHaveAttribute('href', '/marketplace');
    for (const link of within(nav).getAllByRole('link')) expect(link).not.toHaveTextContent('Soon');
  });

  it('the mobile drawer opens, and closes with Escape', async () => {
    renderAt('/dashboard');
    const open = await screen.findByRole('button', { name: 'Open navigation' });
    expect(open).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(open);
    expect(open).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'Close navigation' })).toHaveFocus();
    await userEvent.keyboard('{Escape}');
    expect(open).toHaveAttribute('aria-expanded', 'false');
    expect(open).toHaveFocus();
  });

  it('page search filters pages and navigates', async () => {
    renderAt('/dashboard');
    await userEvent.click(await screen.findByRole('button', { name: 'Search pages…' }));
    const dialog = screen.getByRole('dialog', { name: 'Search pages' });
    await userEvent.type(within(dialog).getByRole('searchbox', { name: 'Page name' }), 'market');
    const results = within(dialog).getByRole('list', { name: 'Pages' });
    expect(within(results).getAllByRole('link')).toHaveLength(1);
    await userEvent.click(within(results).getByRole('link', { name: /Marketplace/ }));
    expect(await screen.findByRole('heading', { name: 'Circular surplus marketplace' })).toBeInTheDocument();
  });

  it('page search reports when nothing matches', async () => {
    renderAt('/dashboard');
    await userEvent.click(await screen.findByRole('button', { name: 'Search pages…' }));
    await userEvent.type(screen.getByRole('searchbox', { name: 'Page name' }), 'zzz');
    expect(screen.getByRole('status')).toHaveTextContent('No page matches');
  });

  it('the account menu shows the real signed-in user and offers only what exists', async () => {
    renderAt('/classify');
    const trigger = await screen.findByRole('button', { name: /account menu/i });
    expect(trigger).toHaveTextContent('Asha Verma');
    expect(trigger).toHaveTextContent('Citizen');
    expect(trigger).not.toHaveTextContent('Guest');
    await userEvent.click(trigger);
    const menu = screen.getByRole('menu');
    expect(within(menu).getAllByRole('menuitem').map((i) => i.textContent)).toEqual([
      'System status',
      'Use light theme',
      'Sign out',
    ]);
  });

  it('the theme choice is stored, applied while signed in, and dropped on public pages', async () => {
    window.localStorage.removeItem('ecomind.theme');
    renderAt('/classify');
    expect(document.documentElement.dataset.theme).toBe('dark');
    await userEvent.click(await screen.findByRole('button', { name: /account menu/i }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Use light theme' }));
    expect(window.localStorage.getItem('ecomind.theme')).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    await userEvent.click(screen.getByRole('button', { name: /account menu/i }));
    expect(screen.getByRole('menuitem', { name: 'Use dark theme' })).toBeInTheDocument();
    window.localStorage.removeItem('ecomind.theme');
  });

  it('signing out ends the session, calls the server and returns to sign-in', async () => {
    signInViaRefresh(fetchSpy, testUser, (url) =>
      url.endsWith('/auth/logout') ? new Response(null, { status: 204 }) : new Response('{}', { status: 404 }),
    );
    renderAt('/classify');
    await userEvent.click(await screen.findByRole('button', { name: /account menu/i }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    const logout = fetchSpy.mock.calls.find(([url]) => String(url).endsWith('/auth/logout'));
    expect(logout?.[1]).toMatchObject({ method: 'POST', headers: { 'X-CSRF-Protection': '1' } });
    expect(window.localStorage.getItem('ecomind.session-hint')).toBeNull();
  });
});

describe('dashboard', () => {
  beforeEach(() => signInViaRefresh(fetchSpy));

  it('shows a citizen only the destinations they may use, and requests no data', async () => {
    renderAt('/dashboard');
    expect(await screen.findByRole('heading', { level: 1, name: /Good (morning|afternoon|evening), Asha Verma/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Classify an item' })).toHaveAttribute('href', '/classify');
    expect(screen.queryByRole('link', { name: 'Collections' })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/demonstration data/i);
    expect(dataCalls(fetchSpy)).toEqual([]);
  });
});

describe('sign-in', () => {
  it('validates fields and shows accessible errors', async () => {
    renderAt('/sign-in');
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Email address/)).toHaveAttribute('aria-invalid', 'true');
  });

  const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
    Response.json(body, { status, headers });
  const apiError = (code: string, message = 'x', details: unknown = null) => ({
    error: { code, message, details, request_id: 'req-test' },
  });

  async function submitSignIn(email = 'asha@example.org', password = 'a long passphrase 1') {
    await userEvent.type(await screen.findByLabelText(/Email address/), email);
    await userEvent.type(screen.getByLabelText(/^Password/), password);
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  }

  it('signs in through the API, keeps no token in storage and lands on the dashboard', async () => {
    fetchSpy.mockImplementation((url: string) =>
      Promise.resolve(url.endsWith('/auth/login') ? json(authResponse()) : new Response('{}', { status: 404 })),
    );
    renderAt('/sign-in');
    await submitSignIn();
    expect(await screen.findByRole('heading', { level: 1, name: /Good (morning|afternoon|evening)/ })).toBeInTheDocument();
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/auth/login');
    expect(JSON.parse(String(init.body))).toEqual({ email: 'asha@example.org', password: 'a long passphrase 1' });
    expect(init.credentials).toBe('include');
    // Only the non-secret hint is persisted; the access token is memory-only.
    const stored = JSON.stringify({ ...window.localStorage });
    expect(stored).not.toContain('test-access-token');
    expect(window.localStorage.getItem('ecomind.session-hint')).toBe('1');
    expect(JSON.stringify({ ...window.sessionStorage })).not.toContain('test-access-token');
  });

  it('shows a generic message for wrong credentials and stays on the form', async () => {
    fetchSpy.mockResolvedValue(json(apiError('invalid_credentials'), 401));
    renderAt('/sign-in');
    await submitSignIn();
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.');
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled();
    expect(window.localStorage.getItem('ecomind.session-hint')).toBeNull();
  });

  it('tells the user how long to wait when rate limited', async () => {
    fetchSpy.mockResolvedValue(json(apiError('rate_limited'), 429, { 'Retry-After': '600' }));
    renderAt('/sign-in');
    await submitSignIn();
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Try again in 10 minutes.');
  });

  it('reports an unreachable server without claiming the password was wrong', async () => {
    fetchSpy.mockRejectedValue(new TypeError('Failed to fetch'));
    renderAt('/sign-in');
    await submitSignIn();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('could not reach the server');
    expect(alert).not.toHaveTextContent('Incorrect');
  });

  it('prevents a double submit while the request is in flight', async () => {
    let release: (r: Response) => void = () => undefined;
    fetchSpy.mockImplementation(() => new Promise<Response>((resolve) => (release = resolve)));
    renderAt('/sign-in');
    await submitSignIn();
    const button = await screen.findByRole('button', { name: 'Sign in' });
    await vi.waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'));
    await userEvent.click(button);
    await userEvent.click(button);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    release(json(apiError('invalid_credentials'), 401));
  });

  it('returns a signed-in user to the page they originally asked for', async () => {
    fetchSpy.mockImplementation((url: string) =>
      Promise.resolve(url.endsWith('/auth/login') ? json(authResponse()) : new Response('{}', { status: 404 })),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createTestRouter(['/classify']);
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await submitSignIn();
    expect(await screen.findByRole('heading', { level: 1, name: 'AI waste classification' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/classify');
  });

  it('a signed-in user visiting sign-in is sent to the dashboard', async () => {
    signInViaRefresh(fetchSpy);
    renderAt('/sign-in');
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Welcome back' })).not.toBeInTheDocument();
  });

  it('social sign-in is visibly unavailable, and password reset is a real link', async () => {
    renderAt('/sign-in');
    for (const name of ['Google', 'Microsoft']) {
      expect(await screen.findByRole('button', { name })).toHaveAttribute('aria-disabled', 'true');
    }
    expect(screen.getByRole('link', { name: 'Forgot password?' })).toHaveAttribute('href', '/forgot-password');
  });

  it('switches to sign-up and validates the confirmation', async () => {
    renderAt('/sign-in');
    await userEvent.click(await screen.findByRole('link', { name: 'Sign up' }));
    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Full name/), 'Asha');
    await userEvent.type(screen.getByLabelText(/Email address/), 'asha@example.org');
    await userEvent.type(screen.getByLabelText(/^Password/), 'a-long-passphrase');
    await userEvent.type(screen.getByLabelText(/Confirm password/), 'different');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('The passwords do not match.')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe('sign-up', () => {
  const apiError = (code: string, message = 'x', details: unknown = null) => ({
    error: { code, message, details, request_id: 'req-test' },
  });

  async function fillAndSubmit(password = 'a long passphrase 1') {
    await userEvent.type(await screen.findByLabelText(/Full name/), 'Asha Verma');
    await userEvent.type(screen.getByLabelText(/Email address/), 'asha@example.org');
    await userEvent.type(screen.getByLabelText(/^Password/), password);
    await userEvent.type(screen.getByLabelText(/Confirm password/), password);
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
  }

  it('creates the account, sends no role, and signs the user in', async () => {
    fetchSpy.mockImplementation((url: string) =>
      Promise.resolve(url.endsWith('/auth/register') ? Response.json(authResponse(), { status: 201 }) : new Response('{}', { status: 404 })),
    );
    renderAt('/sign-up');
    await fillAndSubmit();
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/auth/register');
    expect(JSON.parse(String(init.body))).toEqual({
      email: 'asha@example.org',
      password: 'a long passphrase 1',
      full_name: 'Asha Verma',
    });
  });

  it('shows a duplicate email on the email field', async () => {
    fetchSpy.mockResolvedValue(Response.json(apiError('email_already_registered'), { status: 409 }));
    renderAt('/sign-up');
    await fillAndSubmit();
    expect(await screen.findByText(/An account with this email already exists/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email address/)).toHaveAttribute('aria-invalid', 'true');
  });

  it("shows the server's password-policy message on the password field", async () => {
    fetchSpy.mockResolvedValue(
      Response.json(
        apiError('weak_password', 'Password does not meet the password policy', [
          { location: ['body', 'password'], message: 'This password is too common or too repetitive.', type: 'policy' },
        ]),
        { status: 422 },
      ),
    );
    renderAt('/sign-up');
    await fillAndSubmit('password123456');
    expect(await screen.findByText('This password is too common or too repetitive.')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute('aria-invalid', 'true');
  });
});

describe('classification', () => {
  const model = {
    id: 'model-1',
    name: 'waste-material-classifier',
    version: '1.0.0',
    status: 'active',
    evaluation_metrics: { accuracy: 0.9, n_test: 400, dataset: 'test fixture' },
  };
  const category = (code: string, name: string) => ({ id: `cat-${code}`, code, name });
  const prediction = (over: Record<string, unknown> = {}) => ({
    id: 'pred-1',
    model_name: model.name,
    model_version: model.version,
    material_category: category('plastic', 'Plastic'),
    confidence: 0.91,
    class_probabilities: { cardboard: 0.01, glass: 0.04, metal: 0.03, paper: 0.01, plastic: 0.91, trash: 0 },
    needs_review: false,
    review_reasons: [],
    inference_ms: 24.4,
    review: { status: 'unreviewed', corrected_category: null, notes: null },
    ...over,
  });
  const json = (body: unknown, status = 200) => Response.json(body, { status });
  const apiError = (status: number, code: string, message: string) => json({ error: { code, message, request_id: 'r1' } }, status);

  interface Backend {
    active?: typeof model | null;
    predict?: () => Response;
    review?: () => Response;
  }
  function useBackend(options: Backend = {}, user = testUser) {
    const { active = model, predict = () => json(prediction(), 201), review = () => json(prediction()) } = options;
    signInViaRefresh(fetchSpy, user, (url, init) => {
      const method = init?.method ?? 'GET';
      if (url.endsWith('/classification/model')) return json({ active, scope: 'material_category', note: 'n' });
      if (url.includes('/waste-reports/media') && method === 'POST') return json({ id: 'media-1' }, 201);
      if (url.endsWith('/classification/predictions') && method === 'POST') return predict();
      if (url.endsWith('/review') && method === 'POST') return review();
      return new Response('{}', { status: 404 });
    });
  }
  const callsTo = (suffix: string) => dataCalls(fetchSpy).filter(([url]) => String(url).includes(suffix));

  const png = () => new File(['x'], 'bottle.png', { type: 'image/png' });

  async function pick(file: File) {
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    if (!input) throw new Error('file input missing');
    await userEvent.upload(input, file, { applyAccept: false });
  }

  it('starts empty, asks the server which model is active and uploads nothing', async () => {
    useBackend();
    renderAt('/classify');
    expect(await screen.findByRole('heading', { level: 1, name: 'AI waste classification' })).toBeInTheDocument();
    expect(await screen.findByText('No image yet')).toBeInTheDocument();
    expect(callsTo('/classification/model')).toHaveLength(1);
    expect(callsTo('/waste-reports/media')).toHaveLength(0);
  });

  it('says so when no model is active: no classify button, no upload, no prediction', async () => {
    useBackend({ active: null });
    renderAt('/classify');
    expect(await screen.findByText('No classification model is active')).toBeInTheDocument();
    await pick(png());
    expect(await screen.findByRole('img', { name: 'Selected image: bottle.png' })).toHaveAttribute('src', 'blob:preview');
    expect(screen.queryByRole('button', { name: 'Classify image' })).not.toBeInTheDocument();
    expect(callsTo('/waste-reports/media')).toHaveLength(0);
    expect(callsTo('/classification/predictions')).toHaveLength(0);
  });

  it('reports a model-status failure and lets the user retry', async () => {
    let fail = true;
    signInViaRefresh(fetchSpy, testUser, (url) =>
      url.endsWith('/classification/model') && fail
        ? apiError(400, 'bad_request', 'Model status is unavailable.')
        : json({ active: model, scope: 'material_category', note: 'n' }),
    );
    renderAt('/classify');
    expect(await screen.findByText('Could not check the classification model')).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('No image yet')).toBeInTheDocument();
  });

  it('rejects an unsupported file with an error before anything is sent', async () => {
    useBackend();
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(new File(['x'], 'notes.pdf', { type: 'application/pdf' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Use a JPEG, PNG or WebP image.');
    expect(callsTo('/waste-reports/media')).toHaveLength(0);
  });

  it('uploads the image as a raw body, classifies it, and shows the server result', async () => {
    useBackend();
    renderAt('/classify');
    await screen.findByText('No image yet');
    const file = png();
    await pick(file);
    await userEvent.click(await screen.findByRole('button', { name: 'Classify image' }));

    expect(await screen.findByText('Plastic', { selector: 'p' })).toBeInTheDocument();
    const [uploadUrl, uploadInit] = callsTo('/waste-reports/media')[0] as [string, RequestInit];
    expect(uploadUrl).toContain('filename=bottle.png');
    expect(uploadInit.body).toBe(file);
    expect(uploadInit.headers).toMatchObject({ 'Content-Type': 'image/png', Authorization: 'Bearer test-access-token' });
    const [, predictInit] = callsTo('/classification/predictions')[0] as [string, RequestInit];
    expect(JSON.parse(String(predictInit.body))).toEqual({ media_id: 'media-1' });

    expect(screen.getByText('91%', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('Confident')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Calibrated confidence' })).toHaveAttribute('aria-valuenow', '91');
    expect(screen.getByRole('progressbar', { name: 'glass probability' })).toHaveAttribute('aria-valuenow', '4');
    expect(screen.getByText(/waste-material-classifier 1\.0\.0/)).toBeInTheDocument();
    expect(screen.getByText(/90% accuracy on 400 held-out photos from the model's own training dataset/)).toBeInTheDocument();
    expect(screen.getByText(/has not been evaluated on local field photographs/)).toBeInTheDocument();
    expect(screen.queryByRole('form', { name: 'Review this result' })).not.toBeInTheDocument();
  });

  it('flags a low-confidence result for review with the reasons', async () => {
    useBackend({
      predict: () =>
        json(prediction({ confidence: 0.52, needs_review: true, review_reasons: ['low_confidence', 'unfamiliar_image'] }), 201),
    });
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(png());
    await userEvent.click(await screen.findByRole('button', { name: 'Classify image' }));
    expect(await screen.findByText('Needs review')).toBeInTheDocument();
    expect(screen.getByText(/not confident enough/)).toBeInTheDocument();
    expect(screen.getByText(/unlike the photos the model was trained on/)).toBeInTheDocument();
  });

  it('shows a failure instead of a prediction, and a retry can succeed', async () => {
    let fail = true;
    useBackend({
      predict: () => (fail ? apiError(503, 'model_unavailable', 'x') : json(prediction(), 201)),
    });
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(png());
    await userEvent.click(await screen.findByRole('button', { name: 'Classify image' }));
    expect(await screen.findByText('The model is unavailable')).toBeInTheDocument();
    expect(screen.queryByText('Plastic', { selector: 'p' })).not.toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Plastic', { selector: 'p' })).toBeInTheDocument();
  });

  it('explains an image the server cannot decode, using the server message', async () => {
    useBackend({ predict: () => apiError(422, 'invalid_image', 'The image could not be read.') });
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(png());
    await userEvent.click(await screen.findByRole('button', { name: 'Classify image' }));
    expect(await screen.findByText('This image cannot be analysed')).toBeInTheDocument();
    expect(screen.getByText('The image could not be read.')).toBeInTheDocument();
  });

  it('keeps Classify image unavailable, with the reason, for a role without the permission', async () => {
    useBackend({}, { ...testUser, permissions: ['sorting_guide:read'] });
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(png());
    const button = await screen.findByRole('button', { name: 'Classify image' });
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(button).toHaveAccessibleDescription('Your role is not allowed to classify images.');
    await userEvent.click(button);
    expect(callsTo('/waste-reports/media')).toHaveLength(0);
  });

  it('lets a reviewer correct a prediction, requires the category, and shows the saved review', async () => {
    const reviewer = {
      ...testUser,
      roles: ['manager'],
      permissions: [...testUser.permissions, 'classification:review'],
    };
    useBackend(
      {
        review: () =>
          json(prediction({ review: { status: 'corrected', corrected_category: category('glass', 'Glass'), notes: null } })),
      },
      reviewer,
    );
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(png());
    await userEvent.click(await screen.findByRole('button', { name: 'Classify image' }));
    const form = await screen.findByRole('form', { name: 'Review this result' });

    await userEvent.click(within(form).getByRole('radio', { name: 'No, correct it' }));
    await userEvent.click(within(form).getByRole('button', { name: 'Save review' }));
    expect(await within(form).findByText('Choose the correct category.')).toBeInTheDocument();
    expect(callsTo('/review')).toHaveLength(0);

    const select = within(form).getByRole('combobox', { name: /Correct category/ });
    expect(within(select).queryByRole('option', { name: 'plastic' })).not.toBeInTheDocument(); // not the predicted one
    await userEvent.selectOptions(select, 'glass');
    await userEvent.click(within(form).getByRole('button', { name: 'Save review' }));

    expect(await screen.findByText(/Corrected by a reviewer/)).toBeInTheDocument();
    const [, init] = callsTo('/review')[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ decision: 'corrected', material_category_code: 'glass' });
    expect(screen.queryByRole('form', { name: 'Review this result' })).not.toBeInTheDocument();
  });

  it('states the model scope: five material categories, not miscellaneous, organic, textile or e-waste', async () => {
    useBackend();
    renderAt('/classify');
    expect(await screen.findByRole('heading', { name: 'Material categories' })).toBeInTheDocument();
    expect(screen.getByText(/predicts these five material categories only\. It does not recognise miscellaneous waste, organic or\s+textile waste, e-waste or hazardous/)).toBeInTheDocument();
    expect(screen.queryByText(/Planned waste classes/)).not.toBeInTheDocument();
  });
});
