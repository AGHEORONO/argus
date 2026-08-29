import { test, expect } from '@playwright/test';
import { openApp, goToTab } from './fixtures.js';

/**
 * Echivalentul textual al hărții — punctul 8 din [[De facut]].
 *
 * Rezultatul central al aplicației e poziția geografică a fiecărei anomalii. Fără asta,
 * cineva care nu vede harta poate parcurge tot fluxul și nu poate consuma niciun rezultat.
 * Comentariile din cod spun că problema e rezolvată; testele de aici sunt singurul lucru
 * care poate contrazice asta după un refactor.
 *
 * Eticheta canvasului se scrie din patru locuri și a fost peticită cândva cu regex, care
 * prindea „14" din „14 martie 2026" în loc de numărul de anomalii. De aceea se verifică pe
 * conținut, nu pe existență.
 */

test.beforeEach(async ({ page }) => {
  await openApp(page);
});

const canvas = (page) => page.locator('#map canvas').first();

test('canvasul hărții are un nume care spune ce arată', async ({ page }) => {
  // Se așteaptă eticheta DETALIATĂ, nu prefixul. La inițializare MapLibre pune singur
  // `Map.Title` ("Hartă ortofotoplan cu anomalii detectate") pe canvas, iar eticheta noastră
  // o înlocuiește când sosesc rezultatele. Un `toContain('Hartă ortofotoplan')` trece pe
  // amândouă, deci ar fi trecut și dacă eticheta noastră n-ar fi fost aplicată niciodată.
  await expect.poll(async () => (await canvas(page).getAttribute('aria-label')) || '', { timeout: 15000 })
    .toMatch(/comparație între zborul inițial/);

  const eticheta = await canvas(page).getAttribute('aria-label');
  // Numărul de anomalii din fixtures, nu un număr oarecare cules dintr-o dată calendaristică.
  expect(eticheta).toMatch(/3 anomalii/);
  expect(eticheta, 'eticheta trebuie să trimită spre echivalentul în text').toMatch(/Anomalii detectate/);
});

test('eticheta se actualizează când se aprinde stratul de schimbări cunoscute', async ({ page }) => {
  const cunoscute = page.getByRole('checkbox', { name: 'Schimbări cunoscute' });
  await cunoscute.uncheck();
  await expect.poll(async () => await canvas(page).getAttribute('aria-label'))
    .not.toMatch(/galben/);

  await cunoscute.check();
  await expect.poll(async () => await canvas(page).getAttribute('aria-label'))
    .toMatch(/2 schimbări.*galben/);
});

test('fiecare anomalie are poziția scrisă în cuvinte, nu doar pe hartă', async ({ page }) => {
  await goToTab(page, 'Anomalii');
  const panou = page.getByRole('tabpanel');
  await expect(panou).toContainText(/anomalii/i);

  await page.getByRole('button', { name: /vezi lista completă/i }).click();
  const dialog = page.getByRole('dialog');

  // Trei anomalii, fiecare cu rând propriu în tabel.
  const randuri = dialog.locator('.anomalies-table tbody tr');
  expect(await randuri.count()).toBeGreaterThanOrEqual(3);

  // Poziția: o zonă numită și coordonate rostite. Un tabel care dă doar rangul și scorul
  // e exact gaura pe care punctul 8 o descria.
  const text = await dialog.innerText();
  expect(text, 'lipsește zona geografică').toMatch(/nord|sud|est|vest|centr/i);
  const coordonate = await dialog.locator('.sr-only').allInnerTexts();
  expect(coordonate.join(' '), 'lipsesc coordonatele rostite').toMatch(/grade|°|latitudine|nord|sud/i);
});

test('selectarea unei anomalii produce un anunț, nu doar o mișcare de hartă', async ({ page }) => {
  // C2 din revizuirea de accesibilitate: butoanele de candidat nu produceau niciun efect
  // perceptibil non-vizual — doar flyTo pe un canvas WebGL.
  await goToTab(page, 'Anomalii');
  await page.getByRole('button', { name: /vezi lista completă/i }).click();

  const status = page.locator('[role="status"]');
  await page.getByRole('button', { name: /selectează anomalia 2/i }).first().click();

  await expect.poll(async () => (await status.allInnerTexts()).join(' '))
    .toMatch(/anomali/i);
  const anunt = (await status.allInnerTexts()).join(' ');
  expect(anunt, 'anunțul trebuie să spună care anomalie').toMatch(/2/);
});

test('harta nu e singurul loc unde există numărul de anomalii', async ({ page }) => {
  await goToTab(page, 'Anomalii');
  await expect(page.getByRole('tabpanel')).toContainText(/3/);
});
