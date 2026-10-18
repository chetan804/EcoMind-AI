import { expect, test } from '@playwright/test';

test('the start page shows a running API and a ready database', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveURL(/\/settings\/system-status$/);
  await expect(page.getByRole('heading', { name: 'System status' })).toBeVisible();
  await expect(page.getByText('Running')).toBeVisible();
  await expect(page.getByText('Ready', { exact: true })).toBeVisible();
  await expect(page.getByText('database', { exact: true })).toBeVisible();
  await expect(page.getByText('migrations', { exact: true })).toBeVisible();
});

test('unknown routes render the not-found page', async ({ page }) => {
  await page.goto('/no/such/page');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
});
