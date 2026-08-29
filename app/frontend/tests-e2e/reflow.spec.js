import { test, expect } from '@playwright/test';
import { openApp, goToTab } from './fixtures.js';

/**
 * WCAG 1.4.10 Reflow: la 320 px lățime (echivalentul a 400% zoom pe un ecran de 1280),
 * conținutul nu are voie să ceară derulare pe orizontală.
 *
 * Verificat manual pe 2026-08-26 cu un script de unică folosință. Refactorizarea a adăugat
 * o a treia coloană în grid (bara de activități) și o bandă poziționată absolut pe hartă —
 * exact tipul de schimbare care sparge reflow-ul fără să spargă build-ul.
 */

const LATIMI = [320, 480, 900, 1280];
const FILE = ['Ingestie', 'Comparație', 'Anomalii'];

for (const latime of LATIMI) {
  test(`fără derulare orizontală la ${latime}px, pe toate filele`, async ({ page }) => {
    await page.setViewportSize({ width: latime, height: 800 });
    await openApp(page);

    for (const nume of FILE) {
      await goToTab(page, nume);
      const depaseste = await page.evaluate(() =>
        document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      expect(depaseste, `fila ${nume} depășește viewportul`).toBe(false);
    }
  });
}

test('la 320px filele rămân operabile, nu doar prezente', async ({ page }) => {
  // O bară care intră sub viewport e „prezentă în DOM" și complet inutilizabilă.
  await page.setViewportSize({ width: 320, height: 800 });
  await openApp(page);

  for (const nume of FILE) {
    const fila = page.getByRole('tab', { name: nume });
    await expect(fila).toBeVisible();
    const box = await fila.boundingBox();
    expect(box.x, `fila ${nume} începe în afara ecranului`).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width, `fila ${nume} iese din ecran`).toBeLessThanOrEqual(321);
    // 2.5.8 Target Size (Minimum), AA: 24x24 CSS px.
    expect(Math.min(box.width, box.height), `ținta filei ${nume} e sub 24px`).toBeGreaterThanOrEqual(24);
  }
});

test('sub 900px bara de activități devine orizontală și banda iese de pe hartă', async ({ page }) => {
  // Cele două reguli din media query. Dacă cineva le șterge, aspectul cade tăcut înapoi
  // pe varianta de desktop într-un ecran îngust.
  await page.setViewportSize({ width: 480, height: 800 });
  await openApp(page);

  const directie = await page.locator('.activity-bar').evaluate((el) => getComputedStyle(el).flexDirection);
  expect(directie).toBe('row');

  const pozitie = await page.locator('.view-strip').evaluate((el) => getComputedStyle(el).position);
  expect(pozitie, 'banda absolută peste o hartă îngustă ar acoperi harta').toBe('static');
});

test('banda de comenzi nu iese din zona hărții pe desktop', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openApp(page);

  const harta = await page.locator('#viewport').boundingBox();
  const banda = await page.locator('.view-strip').boundingBox();
  expect(banda.x).toBeGreaterThanOrEqual(harta.x - 1);
  expect(banda.x + banda.width).toBeLessThanOrEqual(harta.x + harta.width + 1);
  expect(banda.y + banda.height).toBeLessThanOrEqual(harta.y + harta.height + 1);
});
