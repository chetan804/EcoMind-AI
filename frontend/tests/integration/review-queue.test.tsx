import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { errorReply, page, routeApi } from '../helpers/api-mock';
import { renderAt, userWith } from '../helpers/render';
import { resetSession } from '../helpers/session';

const fetchSpy = vi.fn();
const PREDICTION_ID = '11111111-1111-4111-8111-111111111111';
const MEDIA_ID = '22222222-2222-4222-8222-222222222222';

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

const reviewer = userWith(['classification:review'], { roles: ['facility_operator'] });
const citizen = userWith(['classification:predict', 'waste_reports:create'], { roles: ['citizen'] });

const prediction = (over: Record<string, unknown> = {}) => ({
  id: PREDICTION_ID,
  media_asset_id: MEDIA_ID,
  model_name: 'waste-classifier',
  model_version: '1.0.0',
  material_category: { id: 'c1', code: 'plastic', name: 'Plastic' },
  confidence: 0.54,
  class_probabilities: { plastic: 0.54, glass: 0.3, metal: 0.16 },
  needs_review: true,
  review_reasons: ['low_confidence'],
  inference_ms: 22,
  review: { status: 'unreviewed', corrected_category: null, notes: null },
  ...over,
});
const image = () => new Response(new Uint8Array([1, 2, 3]), { headers: { 'Content-Type': 'image/png' } });

describe('prediction review queue', () => {
  it('lists unreviewed suggestions that need a person, with the photo, and sends a correction', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/classification/predictions': page([prediction()]),
        [`GET /api/v1/classification/predictions/${PREDICTION_ID}/image`]: image,
        [`POST /api/v1/classification/predictions/${PREDICTION_ID}/review`]: prediction({
          review: { status: 'corrected', corrected_category: { id: 'c2', code: 'glass', name: 'Glass' }, notes: null },
        }),
      },
      reviewer,
    );
    renderAt('/classify/review');
    expect(await screen.findByText('Suggested: Plastic')).toBeInTheDocument();
    expect(screen.getByText(/54% calibrated confidence/)).toBeInTheDocument();
    expect(screen.getByText('The model is not confident enough to accept this result on its own.')).toBeInTheDocument();
    expect(await screen.findByRole('img', { name: 'Photo classified as Plastic' })).toBeInTheDocument();

    const list = api.calls.find((c) => c.key === 'GET /api/v1/classification/predictions');
    expect(list?.query.get('review_status')).toBe('unreviewed');
    expect(list?.query.get('needs_review')).toBe('true');

    const form = screen.getByRole('form', { name: 'Review this result' });
    await userEvent.click(within(form).getByLabelText('No, correct it'));
    await userEvent.selectOptions(within(form).getByLabelText(/Correct category/), 'glass');
    await userEvent.click(within(form).getByRole('button', { name: 'Save review' }));
    const sent = api.calls.find((c) => c.key.startsWith('POST') && c.key.endsWith('/review'));
    expect(sent?.body).toEqual({ decision: 'corrected', material_category_code: 'glass' });
  });

  it('says so when nothing is waiting, and filters finished reviews by outcome', async () => {
    const api = routeApi(fetchSpy, { 'GET /api/v1/classification/predictions': page([]) }, reviewer);
    renderAt('/classify/review');
    expect(await screen.findByText('Nothing is waiting for review')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Show'), 'rejected');
    expect(await screen.findByText('No predictions here yet')).toBeInTheDocument();
    const last = api.calls[api.calls.length - 1];
    expect(last?.query.get('review_status')).toBe('rejected');
    expect(last?.query.get('needs_review')).toBeNull();
  });

  it('shows the outcome of a finished review without a form', async () => {
    routeApi(
      fetchSpy,
      {
        'GET /api/v1/classification/predictions': page([
          prediction({ review: { status: 'confirmed', corrected_category: null, notes: 'looks right' } }),
        ]),
        [`GET /api/v1/classification/predictions/${PREDICTION_ID}/image`]: image,
      },
      reviewer,
    );
    renderAt('/classify/review');
    const item = within(await screen.findByRole('list', { name: 'Predictions' }));
    expect(item.getByText('Confirmed')).toBeInTheDocument();
    expect(item.getByText(/looks right/)).toBeInTheDocument();
    expect(screen.queryByRole('form', { name: 'Review this result' })).not.toBeInTheDocument();
  });

  it('reports a server failure instead of an empty queue', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/classification/predictions': () => errorReply(500, 'internal_error', 'Something broke') }, reviewer);
    renderAt('/classify/review');
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('Nothing is waiting for review')).not.toBeInTheDocument();
  });

  it('is not offered to a person without the review permission', async () => {
    routeApi(fetchSpy, {}, citizen);
    renderAt('/classify/review');
    expect(await screen.findByRole('heading', { name: /permission|access/i })).toBeInTheDocument();
    expect(screen.queryByText('Prediction review queue')).not.toBeInTheDocument();
  });
});
