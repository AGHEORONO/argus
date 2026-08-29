import { test, expect } from '@playwright/test';
import { openApp, goToTab } from './fixtures.js';

/**
 * Lista completă de anomalii, în `<dialog>`.
 *
 * Elementul nativ aduce capcana de focus, Escape și `inert` pe fundal — inclusiv peste DOM-ul
 * injectat de MapLibre. Testele de aici verifică exact ce s-ar pierde dacă cineva l-ar
 * înlocui cu un `<div>` stilizat, plus regresia din 2026-08-26: `display: flex` care
 * suprascria `dialog:not([open]) { display: none }` și picta panoul permanent peste hartă.
 */

test.beforeEach(async ({ page }) => {
  await openApp(page);
  await goToTab(page, 'Anomalii');
});

const deschide = (page) => page.getByRole('button', { name: /vezi lista completă/i });

test('închis, dialogul chiar e invizibil — nu doar [open]=false', async ({ page }) => {
  // Regresia din 2026-08-26: testul de atunci verifica `.open === false`, ceea ce era
  // adevărat, și nu s-a uitat niciodată dacă elementul e VIZIBIL. Era pictat 1440x675 px
  // peste hartă.
  const dialog = page.locator('dialog.anomalies-sheet');
  await expect(dialog).toHaveCount(1);
  await expect(dialog).toBeHidden();
  const afisare = await dialog.evaluate((el) => getComputedStyle(el).display);
  expect(afisare, 'un dialog închis cu display != none e pictat peste hartă').toBe('none');
});

test('deschiderea duce focusul pe titlu, nu pe butonul de închidere', async ({ page }) => {
  // <dialog> ar focusa singur primul descendent focusabil. Titlul e locul corect: spune
  // unde ai ajuns.
  await deschide(page).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('#sheet-heading')).toBeFocused();
});

test('Escape închide și întoarce focusul pe butonul care a deschis', async ({ page }) => {
  await deschide(page).click();
  await expect(page.getByRole('dialog')).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(deschide(page)).toBeFocused();
});

test('butonul de închidere întoarce și el focusul', async ({ page }) => {
  await deschide(page).click();
  await page.getByRole('button', { name: 'Închide lista' }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(deschide(page)).toBeFocused();
});

test('cât e deschis, niciun control din fundal nu primește focus', async ({ page }) => {
  // Formularea contează. Un <dialog> nativ trece o dată prin <body> între cicluri — asta e
  // comportamentul browserului, nu o scăpare, și nu are rost combătută. Ce nu are voie să se
  // întâmple e ca focusul să ajungă pe un control din spate: o filă, sliderul, o casetă.
  await deschide(page).click();
  await expect(page.getByRole('dialog')).toBeVisible();

  const vizitate = [];
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press('Tab');
    vizitate.push(await page.evaluate(() => {
      const a = document.activeElement;
      const d = document.querySelector('dialog.anomalies-sheet');
      return {
        inDialog: d?.contains(a) ?? false,
        peBody: a === document.body,
        // `.workspace` e tot fundalul: bara de activități, raftul de unelte, harta.
        inFundal: !!a?.closest?.('.workspace'),
        descriere: `${a?.tagName}.${(a?.className || '').toString().slice(0, 30)}`,
      };
    }));
  }

  const scapari = vizitate.filter((v) => v.inFundal);
  expect(scapari.map((v) => v.descriere), 'focus pe un control din fundal').toEqual([]);
  for (const v of vizitate) expect(v.inDialog || v.peBody).toBe(true);

  // Și chiar e un ciclu, nu o ieșire: după <body>, următorul Tab intră înapoi în dialog.
  const iesire = vizitate.findIndex((v) => v.peBody);
  if (iesire >= 0 && iesire + 1 < vizitate.length) {
    expect(vizitate[iesire + 1].inDialog, 'după body, focusul trebuie să revină în dialog').toBe(true);
  }
});

test('tabelele din listă au titlu și antete pe coloane', async ({ page }) => {
  await deschide(page).click();
  const tabele = page.getByRole('dialog').locator('table');
  const n = await tabele.count();
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    await expect(tabele.nth(i).locator('caption')).toHaveCount(1);
    expect(await tabele.nth(i).locator('th[scope="col"]').count()).toBeGreaterThan(0);
  }
});

test('zonele derulabile de tabel sunt accesibile de la tastatură', async ({ page }) => {
  // Un container cu overflow trebuie să fie focusabil, altfel conținutul derulat e
  // inaccesibil fără mouse (2.1.1).
  await deschide(page).click();
  const zone = page.getByRole('dialog').locator('.table-scroll');
  const n = await zone.count();
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    await expect(zone.nth(i)).toHaveAttribute('tabindex', '0');
    await expect(zone.nth(i)).toHaveRole('region');
    await expect(zone.nth(i)).not.toHaveAccessibleName('');
  }
});
