import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from './fixtures';

/**
 * Classification against the real stack. What the page shows depends on whether the environment
 * has an ACTIVE model, so each test checks the server first and is skipped (visibly, with the
 * reason) when it does not apply. Model weights are not in git, so CI normally runs the
 * "no active model" test; the "real model" test needs an activated artifact and a sample photo
 * (E2E_SAMPLE_IMAGE, default: a TrashNet plastic image fetched by ml/waste_classification/data/fetch).
 */
const SAMPLE_IMAGE =
  process.env.E2E_SAMPLE_IMAGE ??
  resolve(process.cwd(), '../../datasets/external/trashnet/dataset-resized/plastic/plastic1.jpg');
const CATEGORIES = ['Cardboard', 'Glass', 'Metal', 'Paper', 'Plastic', 'Other waste', 'Residual / other waste'];

async function activeModel(page: import('@playwright/test').Page): Promise<boolean> {
  const response = await page.request.post('/api/v1/auth/refresh', { headers: { 'X-CSRF-Protection': '1' } });
  const token = ((await response.json()) as { access_token: string }).access_token;
  const model = await page.request.get('/api/v1/classification/model', { headers: { Authorization: `Bearer ${token}` } });
  return ((await model.json()) as { active: unknown }).active !== null;
}

test('without an active model the page says so and offers no classification', async ({ page }) => {
  test.skip(await activeModel(page), 'a model is active in this environment; see the real-model test');
  await page.goto('/classify');
  await expect(page.getByText('No classification model is active')).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: 'tiny.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
      'base64',
    ),
  });
  await expect(page.getByRole('img', { name: 'Selected image: tiny.png' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Classify image' })).toHaveCount(0);
});

test('with a real model: upload a photo, get a stored prediction with calibrated confidence', async ({ page }) => {
  test.skip(!(await activeModel(page)), 'no model is activated in this environment (artifacts are not stored in git)');
  test.skip(!existsSync(SAMPLE_IMAGE), `sample image not found at ${SAMPLE_IMAGE}; set E2E_SAMPLE_IMAGE`);
  await page.goto('/classify');
  await page.locator('input[type="file"]').setInputFiles(SAMPLE_IMAGE);
  await page.getByRole('button', { name: 'Classify image' }).click();

  const result = page.getByRole('region', { name: 'Classification result' });
  await expect(result.locator('.result__name')).toBeVisible({ timeout: 30_000 });
  expect(CATEGORIES).toContain(await result.locator('.result__name').innerText());
  await expect(result.getByRole('progressbar', { name: 'Calibrated confidence' })).toBeVisible();
  await expect(result.getByText(/confidence/).first()).toBeVisible();
  await expect(result.getByText(/not been measured on real-world/)).toBeVisible();
  // A citizen has no review permission: no review form is offered.
  await expect(page.getByRole('form', { name: 'Review this result' })).toHaveCount(0);
  await page.screenshot({ path: process.env.E2E_SHOT ?? 'test-results/classification-result.png', fullPage: true });
});
