/**
 * Backend simulat pentru testele de interfață.
 *
 * De ce simulat și nu backendul real: testele de aici verifică DOM și CSS, nu detecția.
 * Backendul are deja 74 de teste în `tests/`. Pornirea lui ar aduce în CI descărcarea
 * ortofotoplanului demo și minute de provisioning pentru a produce exact aceleași
 * răspunsuri JSON pe care le scriem aici în douăzeci de linii.
 *
 * Riscul real al simulării e ca formele să se depărteze de backend fără să observe nimeni.
 * De aceea `tests/test_api_contract.py` compară cheile din fișierul ăsta cu ce întoarce
 * backendul adevărat, și pică dacă vreuna dispare.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/**
 * Formele stau intr-un JSON, nu inline, ca sa poata fi citite si din Python:
 * `tests/test_api_contract.py` compara cheile de aici cu ce intoarce backendul adevarat.
 * Fara puntea asta, simularea s-ar putea departa de API fara sa observe nimeni.
 */
const F = JSON.parse(readFileSync(fileURLToPath(new URL('./fixtures.json', import.meta.url)), 'utf8'));

export const SITE = F.site;
export const CENTRU = [-78.43072, 0.01334];

/** PNG 1x1 transparent — MapLibre cere un răspuns valid de imagine, nu și conținut. */
const TILE_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

/** Pătrat mic în jurul unui punct, în grade. */
function patrat([lon, lat], d = 0.0004) {
  return {
    type: 'Polygon',
    coordinates: [[
      [lon - d, lat - d], [lon + d, lat - d],
      [lon + d, lat + d], [lon - d, lat + d],
      [lon - d, lat - d],
    ]],
  };
}

export const CAPTURI = F.captures;
export const COMPARATII = F.comparisons;

export const ANOMALII = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { ...F.anomaly_properties, rank: 1, anomaly_score: 0.9412 }, geometry: patrat([-78.4310, 0.0138]) },
    { type: 'Feature', properties: { ...F.anomaly_properties, rank: 2, anomaly_score: 0.8123 }, geometry: patrat([-78.4302, 0.0129]) },
    { type: 'Feature', properties: { ...F.anomaly_properties, rank: 3, anomaly_score: 0.6644 }, geometry: patrat([-78.4315, 0.0126]) },
  ],
};

export const ADEVAR = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { ...F.truth_properties, zone: 1, label: 'structură demolată' }, geometry: patrat([-78.4310, 0.0138]) },
    { type: 'Feature', properties: { ...F.truth_properties, zone: 2, label: 'obiect nou apărut' }, geometry: patrat([-78.4295, 0.0141]) },
  ],
};

export const ZBORURI = { flights: F.flights };

/**
 * Prinde tot ce iese spre backend. Deliberat generos la id-uri: testul nu trebuie să știe
 * ce zbor alege aplicația, doar că primește date coerente pentru oricare.
 */
export async function mockApi(page, { anomalii = ANOMALII, adevar = ADEVAR, capturi = CAPTURI } = {}) {
  const json = (route, body, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

  // Plasa de siguranță se înregistrează PRIMA, fiindcă în Playwright ultima rută
  // înregistrată câștigă. Pusă la sfârșit, ar înghiți toate răspunsurile de mai jos și
  // aplicația ar rula fără date — exact ce s-a întâmplat la prima rulare.
  await page.route('**/127.0.0.1:8077/**', (route) => json(route, { detail: 'rută neprevăzută' }, 404));

  await page.route('**/tiles/**', (route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: TILE_PNG }));

  await page.route('**/sites/*/captures', (route) => json(route, { site_id: SITE, captures: capturi }));
  await page.route('**/sites/*/comparisons', (route) => json(route, { comparisons: COMPARATII }));
  await page.route('**/flights', (route) => json(route, ZBORURI));
  await page.route('**/flights/*/result', (route) =>
    json(route, { id: 'test', status: 'done', result: anomalii }));
  await page.route('**/flights/*/truth', (route) =>
    (adevar ? json(route, adevar) : json(route, { detail: 'no truth' }, 404)));
  await page.route('**/flights/*/status', (route) => json(route, { id: 'test', status: 'done' }));
  await page.route('**/flights/*/validation', (route) => json(route, { detail: 'not found' }, 404));
}

/** Încarcă aplicația cu backendul simulat și așteaptă ca raftul de unelte să existe. */
export async function openApp(page, optiuni = {}) {
  await mockApi(page, optiuni);
  await page.goto('/');
  await page.getByRole('tablist', { name: 'Secțiuni de lucru' }).waitFor();
}

/** Comută pe o filă prin click și așteaptă ca panoul să se actualizeze. */
export async function goToTab(page, nume) {
  await page.getByRole('tab', { name: nume }).click();
  await page.getByRole('tab', { name: nume, selected: true }).waitFor();
}

/**
 * Așteaptă ca rețeaua să tacă efectiv, în loc de un cronometru fix.
 *
 * Varianta cu `waitForTimeout(1500)` a picat în CI la a doua rulare: cu mai mulți workeri
 * pe același CPU, tile-urile încă veneau după o secundă și jumătate și erau puse pe seama
 * drag-ului. Un test instabil e mai rău decât niciunul — învață oamenii să ignore roșul.
 */
export async function asteaptaLiniste(page, liniste = 800, plafon = 15000) {
  let ultima = Date.now();
  const marcheaza = () => { ultima = Date.now(); };
  page.on('request', marcheaza);
  const start = Date.now();
  try {
    while (Date.now() - ultima < liniste && Date.now() - start < plafon) {
      await page.waitForTimeout(100);
    }
  } finally {
    page.off('request', marcheaza);
  }
}
