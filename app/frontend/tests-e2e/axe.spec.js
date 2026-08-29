import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { openApp, goToTab } from './fixtures.js';

/**
 * Scanare automată cu axe-core.
 *
 * De reținut ce NU face: axe prinde vreo treime din problemele WCAG, și niciuna dintre cele
 * care contează cel mai mult aici (ordinea de citire, dacă un anunț are sens, dacă harta are
 * un echivalent textual util). Testele din `shell.spec.js` și `view-strip.spec.js` sunt cele
 * care verifică afirmațiile proiectului. Asta e doar plasa de dedesubt: prinde regresiile
 * ieftine — o etichetă pierdută la un refactor, un id duplicat, un contrast scăzut.
 */

const ETICHETE = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const FILE = ['Ingestie', 'Comparație', 'Anomalii'];

/** Raport citibil: axe scoate obiecte imense, iar mesajul implicit e nefolositor. */
function raport(incalcari) {
  return incalcari.map((v) =>
    `\n[${v.impact}] ${v.id}: ${v.help}\n  ${v.nodes.length} element(e): `
    + v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')
  ).join('');
}

for (const nume of FILE) {
  test(`axe: fila ${nume} fără încălcări`, async ({ page }) => {
    await openApp(page);
    await goToTab(page, nume);

    const rezultat = await new AxeBuilder({ page })
      .withTags(ETICHETE)
      // Canvasul MapLibre e DOM injectat de bibliotecă. Echivalentul textual al hărții e
      // testat separat, pe conținutul nostru; regulile axe pe interiorul canvasului ar
      // raporta lucruri pe care nu le putem repara și ar ascunde regresiile noastre.
      .exclude('.maplibregl-map')
      .analyze();

    expect(rezultat.violations, raport(rezultat.violations)).toEqual([]);
  });
}

test('axe: lista completă de anomalii, cu dialogul deschis', async ({ page }) => {
  await openApp(page);
  await goToTab(page, 'Anomalii');

  // Numele accesibil complet e "Vezi lista completă, N anomalii detectate".
  await page.getByRole('button', { name: /vezi lista completă/i }).click();
  await expect(page.getByRole('dialog')).toBeVisible();

  const rezultat = await new AxeBuilder({ page })
    .withTags(ETICHETE)
    .exclude('.maplibregl-map')
    .analyze();

  expect(rezultat.violations, raport(rezultat.violations)).toEqual([]);
});

test('axe: la 320px', async ({ page }) => {
  // Contrastul și mărimea țintelor se pot schimba la reflow, deci scanarea de desktop nu
  // acoperă lățimea îngustă.
  await page.setViewportSize({ width: 320, height: 800 });
  await openApp(page);

  const rezultat = await new AxeBuilder({ page })
    .withTags(ETICHETE)
    .exclude('.maplibregl-map')
    .analyze();

  expect(rezultat.violations, raport(rezultat.violations)).toEqual([]);
});
