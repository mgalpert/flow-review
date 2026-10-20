import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testMatch: '*.spec.mjs',
  fullyParallel: true,
  use: { baseURL: 'http://127.0.0.1:8351', headless: true, viewport: { width: 1700, height: 1100 } },
  webServer: { command: 'python3 -m http.server 8351 --bind 127.0.0.1', url: 'http://127.0.0.1:8351/examples/onboarding.html', reuseExistingServer: !process.env.CI },
  reporter: 'list'
});
