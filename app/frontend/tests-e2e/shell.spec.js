import { test, expect } from '@playwright/test';
import { openApp, goToTab } from './fixtures.js';

/**
 * Bara de activități, refactorizarea în stil VS Code.
 *
 * Un tablist rupt compilează perfect, deci build-ul verde nu spune nimic despre el.
 * Fiecare afirmație scrisă în comentariile din `App.jsx` și `index.css` are aici un test
 * care o poate contrazice.
 */

const FILE = ['Ingestie', 'Comparație', 'Anomalii'];

test.beforeEach(async ({ page }) => {
  await openApp(page);
});

test('trei file, exact una selectată', async ({ page }) => {
  const tabs = page.getByRole('tab');
  await expect(tabs).toHaveCount(3);
  for (const [i, nume] of FILE.entries()) {
    await expect(tabs.nth(i)).toHaveAccessibleName(new RegExp(nume));
  }
  await expect(page.getByRole('tab', { selected: true })).toHaveCount(1);
});

test('raftul e UN singur tab stop: doar fila activă are tabindex 0', async ({ page }) => {
  // Afirmația din cod: "cele trei file sunt UN singur tab stop". Verificată prin numărare,
  // nu prin citirea comentariului.
  const focusabile = page.locator('.activity-bar [role="tab"][tabindex="0"]');
  await expect(focusabile).toHaveCount(1);
  await expect(focusabile).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('.activity-bar [role="tab"][tabindex="-1"]')).toHaveCount(2);
});

test('săgețile activează panoul și lasă focusul pe filă', async ({ page }) => {
  await page.getByRole('tab', { name: 'Comparație' }).focus();

  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('tab', { name: 'Anomalii' })).toBeFocused();
  await expect(page.getByRole('tab', { name: 'Anomalii' })).toHaveAttribute('aria-selected', 'true');

  // Activare automată: panoul s-a schimbat fără Enter.
  await expect(page.getByRole('tabpanel')).toHaveAccessibleName(/Anomalii/);

  await page.keyboard.press('ArrowUp');
  await expect(page.getByRole('tab', { name: 'Comparație' })).toBeFocused();
  await expect(page.getByRole('tabpanel')).toHaveAccessibleName(/Comparație/);
});

test('săgețile se învârt în cerc la ambele capete', async ({ page }) => {
  // Se pornește prin activare, nu prin .focus() pe o filă inactivă: handlerul se orientează
  // după fila ACTIVĂ, iar click-ul și săgețile țin mereu focusul și selecția împreună.
  // Un focus programatic pe o filă cu tabindex="-1" le desparte — o stare la care
  // interacțiunea reală nu ajunge, fiindcă tastatura nu poate ateriza acolo.
  await goToTab(page, 'Ingestie');
  await page.keyboard.press('ArrowUp');
  await expect(page.getByRole('tab', { name: 'Anomalii' })).toBeFocused();
  await expect(page.getByRole('tabpanel')).toHaveAccessibleName(/Anomalii/);
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('tab', { name: 'Ingestie' })).toBeFocused();
});

test('Home și End sar la capete', async ({ page }) => {
  await page.getByRole('tab', { name: 'Comparație' }).focus();
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', { name: 'Anomalii' })).toBeFocused();
  await page.keyboard.press('Home');
  await expect(page.getByRole('tab', { name: 'Ingestie' })).toBeFocused();
});

test('săgețile stânga/dreapta merg la fel ca sus/jos', async ({ page }) => {
  // Bara e verticală, dar rămâne orizontală sub 900px. Ambele perechi trebuie să meargă.
  await goToTab(page, 'Ingestie');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Comparație' })).toBeFocused();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('tab', { name: 'Ingestie' })).toBeFocused();
});

test('aria-controls arată spre panoul care există, pentru toate cele trei file', async ({ page }) => {
  // Capcana pe care comentariul din cod spune că o evită: cu montare condiționată,
  // filele inactive ar arăta spre id-uri inexistente.
  for (const nume of FILE) {
    await goToTab(page, nume);
    for (const t of await page.getByRole('tab').all()) {
      const id = await t.getAttribute('aria-controls');
      expect(id, 'fiecare filă trebuie să aibă aria-controls').toBeTruthy();
      await expect(page.locator(`#${id}`)).toHaveCount(1);
      await expect(page.locator(`#${id}`)).toHaveAttribute('role', 'tabpanel');
    }
  }
});

test('panoul își schimbă numele odată cu fila activă', async ({ page }) => {
  for (const nume of FILE) {
    await goToTab(page, nume);
    await expect(page.getByRole('tabpanel')).toHaveAccessibleName(new RegExp(nume));
    await expect(page.getByRole('tabpanel')).toHaveCount(1);
  }
});

test('indicatorul de filă activă e bara de accent, nu doar fundalul', async ({ page }) => {
  // Afirmația din CSS: fundalul dă 1.18:1, adică invizibil, deci indicatorul e bara.
  // Dacă cineva șterge ::before și lasă doar fundalul, testul ăsta pică.
  const latime = (sel) => page.locator(sel).first().evaluate(
    (el) => getComputedStyle(el, '::before').width);

  await goToTab(page, 'Comparație');
  expect(await latime('.activity-item.is-active')).toBe('3px');
  const inactiv = await latime('.activity-item:not(.is-active)');
  expect(inactiv, 'filele inactive nu au bară de accent').not.toBe('3px');
});

test('filele au etichete vizibile, nu tooltips', async ({ page }) => {
  // Decizia scrisă în CSS: etichete vizibile în loc de tooltips. Un tooltip ar însemna
  // eticheta ascunsă vizual.
  for (const nume of FILE) {
    await expect(page.locator('.activity-label', { hasText: nume })).toBeVisible();
  }
});

test('fila Anomalii rămâne montată și când nu există rezultate', async ({ page }) => {
  // Comentariul din cod: "o filă care apare și dispare ar strica ordinea filelor și
  // numărătoarea din navigarea cu săgeți".
  await page.route('**/flights/*/result', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"nimic"}' }));
  await page.reload();
  await expect(page.getByRole('tab')).toHaveCount(3);
  await goToTab(page, 'Anomalii');
  await expect(page.getByRole('tabpanel')).toBeVisible();
});

test('click-ul lasă focusul pe filă, deci săgețile continuă de acolo', async ({ page }) => {
  // Drumul real: mouse pe o filă, apoi tastatură. Dacă un click n-ar focusa fila,
  // săgețile de după el n-ar mai ajunge la handler deloc.
  for (const nume of FILE) {
    await goToTab(page, nume);
    await expect(page.getByRole('tab', { name: nume })).toBeFocused();
  }
});
