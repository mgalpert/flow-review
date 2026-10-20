import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testMatch: '*.spec.mjs',
  fullyParallel: true,
  use: { baseURL: 'http://127.0.0.1:8351', headless: true, viewport: { width: 1700, height: 1100 } },
  webServer: { command: 'python3 skills/flow-review-canvas/scripts/serve_canvas.py examples/onboarding.html --port 8351', url: 'http://127.0.0.1:8351/', reuseExistingServer: false },
  reporter: 'list'
});
