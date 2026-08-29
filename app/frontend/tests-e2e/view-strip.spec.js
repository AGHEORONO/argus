import { test, expect } from '@playwright/test';
import { openApp, asteaptaHartaNemiscata } from './fixtures.js';

/**
 * Banda de comenzi de vizualizare, mutată din panoul lateral pe hartă.
 *
 * Mutarea a fost făcută ca un control să stea lângă ce controlează. Testele de aici verifică
 * ce s-a pierdut sau nu în mutare: numele accesibile, operabilitatea de la tastatură,
 * legenda, și regresia T-08 (drag-ul sliderului nu are voie să ceară tile-uri).
 */

test.beforeEach(async ({ page }) => {
  await openApp(page);
});

const banda = (page) => page.getByRole('group', { name: 'Comenzi de vizualizare' });

test('banda e un grup cu nume, pe hartă', async ({ page }) => {
  await expect(banda(page)).toBeVisible();
  await expect(banda(page)).toHaveCount(1);
});

test('sliderul de amestec are nume, valoare în cuvinte, și merge de la tastatură', async ({ page }) => {
  const slider = page.getByRole('slider', { name: 'Amestec' });
  await expect(slider).toBeVisible();

  // aria-valuetext: "50%" singur nu spune 50% din ce. Textul zice ce zbor se vede.
  const text = await slider.getAttribute('aria-valuetext');
  expect(text, 'sliderul are nevoie de aria-valuetext, nu doar de procent').toBeTruthy();
  expect(text.length, 'valuetext trebuie să fie o frază, nu un număr').toBeGreaterThan(10);

  const inainte = await slider.inputValue();
  await slider.focus();
  await expect(slider).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await expect
    .poll(() => slider.inputValue(), { message: 'săgeata trebuie să miște sliderul' })
    .not.toBe(inainte);

  // Valuetext-ul se actualizează odată cu valoarea, altfel anunță o stare veche.
  await expect.poll(() => slider.getAttribute('aria-valuetext')).not.toBe(text);
});

test('procentul afișat e ascuns de cititoarele de ecran', async ({ page }) => {
  // Dublează aria-valuetext. Lăsat vizibil, ascuns din arborele accesibil.
  const procent = banda(page).locator('.slider-value');
  await expect(procent).toBeVisible();
  await expect(procent).toHaveAttribute('aria-hidden', 'true');
});

test('comutatoarele de straturi au etichete legate și merg de la tastatură', async ({ page }) => {
  const candidate = page.getByRole('checkbox', { name: 'Anomalii candidate' });
  await expect(candidate).toBeVisible();
  await expect(candidate).toBeChecked();

  await candidate.focus();
  await page.keyboard.press('Space');
  await expect(candidate).not.toBeChecked();
  await page.keyboard.press('Space');
  await expect(candidate).toBeChecked();
});

test('click pe etichetă comută caseta — deci htmlFor chiar e legat', async ({ page }) => {
  const candidate = page.getByRole('checkbox', { name: 'Anomalii candidate' });
  await banda(page).getByText('Anomalii candidate').click();
  await expect(candidate).not.toBeChecked();
});

test('legenda apare doar când stratul pe care îl explică e pornit', async ({ page }) => {
  const cunoscute = page.getByRole('checkbox', { name: 'Schimbări cunoscute' });
  const legenda = banda(page).locator('.strip-legend');

  if (!(await cunoscute.isChecked())) await cunoscute.check();
  await expect(legenda).toBeVisible();
  await expect(legenda).toContainText(/întrerupt/);
  await expect(legenda).toContainText(/continuu/);

  await cunoscute.uncheck();
  await expect(legenda).toHaveCount(0);
});

test('fără adevăr de referință, comutatorul de schimbări cunoscute nu există', async ({ page }) => {
  // page.route, nu context.route: rutele de pagină au prioritate, iar între ele câștigă
  // ultima înregistrată. Cu context.route suprascrierea n-ar intra niciodată în vigoare și
  // testul ar trece pentru că verifică scenariul greșit.
  await page.route('**/flights/*/truth', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"nimic"}' }));
  await page.reload();
  await expect(banda(page)).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Schimbări cunoscute' })).toHaveCount(0);
  // Comutatorul de candidați rămâne: nu depinde de adevărul de referință.
  await expect(page.getByRole('checkbox', { name: 'Anomalii candidate' })).toBeVisible();
});

test('T-08: drag-ul sliderului nu cere nimic din rețea', async ({ page }) => {
  // Buget propriu. Testul asteapta intai ca incarcarea de tile-uri sa taca (pana la 12s pe
  // un runner incarcat), apoi face 41 de miscari de mouse, apoi mai asteapta. Cu limita
  // implicita de 30s a picat in CI prin timeout, nu prin aserțiune — adica exact felul de
  // rosu care nu spune nimic despre aplicatie.
  test.setTimeout(90_000);
  // Regresia verificată manual pe 2026-08-25 cu un script de unică folosință. Aici devine
  // permanentă. Un slider care recere tile-uri la fiecare pixel îngenunchează backendul.
  const slider = page.getByRole('slider', { name: 'Amestec' });
  await slider.waitFor();
  // Harta trebuie să fie nemișcată înainte de măsurare, altfel tile-urile cerute de animația
  // inițială de cameră ajung să fie puse pe seama drag-ului.
  await asteaptaHartaNemiscata(page);

  const cereri = [];
  page.on('request', (r) => cereri.push(r.url()));

  const box = await slider.boundingBox();
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2);
  await page.mouse.down();
  for (let i = 0; i <= 40; i++) {
    await page.mouse.move(box.x + (box.width * i) / 40, box.y + box.height / 2);
  }
  await page.mouse.up();
  await page.waitForTimeout(2000);

  const tiles = cereri.filter((u) => u.includes('/tiles/'));
  expect(tiles, `drag-ul a cerut ${tiles.length} tile-uri`).toHaveLength(0);
  expect(cereri, `drag-ul a făcut ${cereri.length} cereri`).toHaveLength(0);
});

test('comenzile de hartă nu s-au dublat în panoul lateral după mutare', async ({ page }) => {
  // Mutarea a scos sliderul din Timeline (prop-ul opacityControl). Dacă reapare acolo,
  // ar exista două slidere cu același nume și una ar fi mereu desincronizată.
  await expect(page.getByRole('slider', { name: 'Amestec' })).toHaveCount(1);
  await expect(page.getByRole('checkbox', { name: 'Anomalii candidate' })).toHaveCount(1);
});

test('banda nu acoperă niciun control al hărții', async ({ page }) => {
  // Regresia reparată pe 2026-08-30. Controalele erau jos-stânga și jos-dreapta fiindcă
  // "niciun panou nu acoperă zona aia" — adevărat până când banda a fost mutată pe hartă.
  // Acopereau două treimi din grupul de zoom și INTEGRAL atribuirea, care e o cerință de
  // licențiere a datelor.
  //
  // Testul e pe geometrie, nu pe poziția aleasă: dacă cineva mută banda sau controalele
  // altundeva și se suprapun din nou, pică, indiferent de colțul folosit.
  const bandaBox = await banda(page).boundingBox();
  const controale = page.locator('.maplibregl-ctrl');
  const n = await controale.count();
  expect(n, 'harta ar trebui să aibă controale').toBeGreaterThan(0);

  for (let i = 0; i < n; i++) {
    const c = controale.nth(i);
    if (!(await c.isVisible())) continue;
    const box = await c.boundingBox();
    const seSuprapun = box.x < bandaBox.x + bandaBox.width
      && box.x + box.width > bandaBox.x
      && box.y < bandaBox.y + bandaBox.height
      && box.y + box.height > bandaBox.y;
    const cls = await c.getAttribute('class');
    expect(seSuprapun, `controlul "${cls}" se suprapune cu banda`).toBe(false);
  }
});

test('butoanele de zoom chiar primesc click-ul, nu ceva de deasupra', async ({ page }) => {
  // Geometria singură nu ajunge: un element transparent deasupra ar trece testul de
  // suprapunere și tot ar fura click-ul. Se întreabă browserul cine e în vârf.
  for (const nume of ['Mărește harta', 'Micșorează harta']) {
    const buton = page.getByRole('button', { name: nume });
    await expect(buton).toBeVisible();
    const box = await buton.boundingBox();
    const deasupra = await page.evaluate(
      ([x, y]) => {
        const el = document.elementFromPoint(x, y);
        return el ? !!el.closest('.maplibregl-ctrl') : false;
      },
      [box.x + box.width / 2, box.y + box.height / 2],
    );
    expect(deasupra, `"${nume}" e acoperit de altceva`).toBe(true);
  }
});

test('atribuirea hărții rămâne vizibilă', async ({ page }) => {
  // Cerință de licențiere a datelor. Era ascunsă complet sub bandă.
  const atribuire = page.locator('.maplibregl-ctrl-attrib');
  await expect(atribuire).toBeVisible();
  const box = await atribuire.boundingBox();
  const deasupra = await page.evaluate(
    ([x, y]) => !!document.elementFromPoint(x, y)?.closest('.maplibregl-ctrl-attrib'),
    [box.x + box.width / 2, box.y + box.height / 2],
  );
  expect(deasupra, 'atribuirea e acoperită de alt element').toBe(true);
});
