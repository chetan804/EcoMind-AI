import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider } from 'react-router/dom';
import { createTestRouter } from '@/app/router';

const fetchSpy = vi.fn();

beforeEach(() => {
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
    expect(screen.getByText('Models trained so far')).toBeInTheDocument();
    expect(screen.queryByText(/accuracy/i)).not.toBeInTheDocument();
    expect(screen.getByText(/in early development/i)).toBeInTheDocument();
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
  it('lists the primary destinations and never includes Smart Bins & Telemetry', async () => {
    renderAt('/dashboard');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const labels = within(nav).getAllByRole('link').map((a) => a.textContent ?? '');
    expect(labels.some((l) => l.startsWith('Dashboard'))).toBe(true);
    expect(labels.some((l) => l.startsWith('Classification'))).toBe(true);
    expect(document.body.textContent).not.toMatch(/smart bins?|telemetry/i);
    expect(labels.join(' ')).not.toMatch(/\bbins?\b/i);
  });

  it('marks the current page and flags unbuilt destinations as "Soon"', async () => {
    renderAt('/dashboard');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: /^Dashboard/ })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: /^Analytics/ })).toHaveTextContent('Soon');
    expect(within(nav).getByRole('link', { name: /^Classification/ })).not.toHaveTextContent('Soon');
  });

  it('an unbuilt destination says plainly that it is not built yet', async () => {
    renderAt('/dashboard');
    await userEvent.click(await screen.findByRole('link', { name: /^Analytics/ }));
    expect(await screen.findByRole('heading', { name: 'Analytics is not built yet' })).toBeInTheDocument();
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
    await userEvent.type(within(dialog).getByRole('searchbox', { name: 'Page name' }), 'fore');
    const results = within(dialog).getByRole('list', { name: 'Pages' });
    expect(within(results).getAllByRole('link')).toHaveLength(1);
    await userEvent.click(within(results).getByRole('link', { name: /Forecasting/ }));
    expect(await screen.findByRole('heading', { name: 'Forecasting is not built yet' })).toBeInTheDocument();
  });

  it('page search reports when nothing matches', async () => {
    renderAt('/dashboard');
    await userEvent.click(await screen.findByRole('button', { name: 'Search pages…' }));
    await userEvent.type(screen.getByRole('searchbox', { name: 'Page name' }), 'zzz');
    expect(screen.getByRole('status')).toHaveTextContent('No page matches');
  });

  it('the account menu offers only what exists and shows no invented user', async () => {
    renderAt('/classify');
    await userEvent.click(await screen.findByRole('button', { name: 'Account menu' }));
    const menu = screen.getByRole('menu');
    expect(within(menu).getAllByRole('menuitem').map((i) => i.textContent)).toEqual(['Sign in', 'System status']);
  });
});

describe('dashboard', () => {
  it('labels all content as demonstration data and makes no network request', async () => {
    renderAt('/dashboard');
    expect(await screen.findByText(/Demonstration data, not live/)).toBeInTheDocument();
    expect(screen.getByRole('list', { name: /Key metrics \(demonstration data\)/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Waste generation trend.*demonstration data.*\(kg per day\)/i })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Not live data/ })).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
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

  it('a valid submission is NOT sent anywhere and says sign-in is unavailable', async () => {
    renderAt('/sign-in');
    await userEvent.type(await screen.findByLabelText(/Email address/), 'a@b.co');
    await userEvent.type(screen.getByLabelText(/^Password/), 'secret');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Sign-in is not available yet')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('social sign-in and password reset are visibly unavailable', async () => {
    renderAt('/sign-in');
    for (const name of ['Google', 'Microsoft', 'Forgot password?']) {
      expect(await screen.findByRole('button', { name })).toHaveAttribute('aria-disabled', 'true');
    }
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

describe('classification', () => {
  const png = () => new File(['x'], 'bottle.png', { type: 'image/png' });

  async function pick(file: File) {
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    if (!input) throw new Error('file input missing');
    await userEvent.upload(input, file, { applyAccept: false });
  }

  it('starts empty and says what will happen', async () => {
    renderAt('/classify');
    expect(await screen.findByRole('heading', { level: 1, name: 'AI waste classification' })).toBeInTheDocument();
    expect(screen.getByText('No image yet')).toBeInTheDocument();
    expect(screen.getByText(/No model has been trained yet/)).toBeInTheDocument();
  });

  it('rejects an unsupported file with an error', async () => {
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(new File(['x'], 'notes.pdf', { type: 'application/pdf' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Use a JPEG, PNG or WebP image.');
  });

  it('previews a valid image locally and reports that classification is unavailable (no upload, no result)', async () => {
    renderAt('/classify');
    await screen.findByText('No image yet');
    await pick(png());
    expect(await screen.findByRole('img', { name: 'Selected image: bottle.png' })).toHaveAttribute('src', 'blob:preview');
    expect(screen.getByText('Classification is not available yet')).toBeInTheDocument();
    expect(screen.getByText(/Nothing was uploaded/)).toBeInTheDocument();
    expect(screen.queryByText('Plastic', { selector: 'p' })).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Try another image' }));
    expect(screen.getByText('No image yet')).toBeInTheDocument();
  });

  it('the layout preview is labelled as a sample and shows no confidence or accuracy figure', async () => {
    renderAt('/classify');
    await userEvent.click(await screen.findByRole('switch', { name: /layout preview/i }));
    expect(screen.getByText('Sample layout')).toBeInTheDocument();
    expect(screen.getByText(/not a model result/i)).toBeInTheDocument();
    expect(screen.getByText('Not connected')).toBeInTheDocument();
    expect(screen.getByText('Not evaluated')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\d+(\.\d+)?\s*%\s*(confidence|accuracy)/i);
    const verify = screen.getByRole('button', { name: 'Verify result' });
    expect(verify).toHaveAttribute('aria-disabled', 'true');
    expect(verify).toHaveAccessibleDescription(/not built yet/);
  });

  it('states that the classes are planned, not supported', async () => {
    renderAt('/classify');
    expect(await screen.findByRole('heading', { name: 'Planned waste classes' })).toBeInTheDocument();
    expect(screen.queryByText(/supported waste classes/i)).not.toBeInTheDocument();
  });
});
