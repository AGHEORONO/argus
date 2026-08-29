import { defineConfig, devices } from '@playwright/test';

/**
 * Testele rulează peste build-ul de producție servit de `vite preview`, nu peste serverul
 * de dezvoltare: de patru ori într-o singură zi un server pornit înainte de o modificare a
 * servit cod vechi și a făcut să pară că un fix nu funcționează (vezi Jurnal 2026-08-26).
 * `npm run build` la fiecare pornire face imposibilă situația aia.
 *
 * `VITE_API_BASE` e fixat aici ca adresa spre care pleacă cererile să fie cunoscută și în
 * test, nu moștenită din mediu.
 */
const PORT = 4180;
const API = 'http://127.0.0.1:8077';

export default defineConfig({
  testDir: './tests-e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',

  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // MapLibre e WebGL. Fără swiftshader, harta nu se inițializează în CI și jumătate
        // din aplicație dispare din DOM fără ca vreun test să spună de ce.
        launchOptions: { args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] },
      },
    },
  ],

  webServer: {
    command: `npm run build && npx vite preview --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { VITE_API_BASE: API },
  },
});
