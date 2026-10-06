import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', workers: 2, retries: process.env.CI ? 1 : 0,
  use: { baseURL: 'http://127.0.0.1:8772', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true } },
  ],
  webServer: { command: 'npm run preview -- --host 127.0.0.1 --port 8772 --strictPort', url: 'http://127.0.0.1:8772', reuseExistingServer: false },
});