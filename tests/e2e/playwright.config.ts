import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests run against an already running stack (frontend + backend + migrated
 * PostgreSQL), for example `docker compose up` or the CI job in quality-gates.yml.
 * E2E_BASE_URL is the frontend origin; E2E_CHROMIUM_PATH optionally points at a system Chromium.
 */
export default defineConfig({
  testDir: './specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: process.env.E2E_CHROMIUM_PATH
          ? { executablePath: process.env.E2E_CHROMIUM_PATH }
          : {},
      },
    },
  ],
});
