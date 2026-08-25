/**
 * Timeline geometry and Romanian date formatting. Pure functions, no React, no DOM —
 * the tick layout is the part with real logic in it, so it lives where it can be tested
 * without a browser.
 */

export const MIN_TICK_PX = 24; // WCAG 2.5.8 Target Size (Minimum)

/**
 * Lay ticks out proportionally to elapsed time, then push them apart to a 24px floor.
 *
 * Purely proportional is the honest picture right up until two flights three days apart
 * become one unhittable target — a control you cannot reach communicates nothing at all.
 * The true interval is always stated in text next to the axis, so the geometry is the
 * sketch and the words are authoritative.
 */
export function layoutTicks(dates, width) {
  const n = dates.length;
  if (n === 0) return [];
  if (n === 1) return [width / 2];

  const t = dates.map((d) => new Date(`${d}T00:00:00Z`).getTime());
  const span = t[n - 1] - t[0];
  const xs = t.map((v) => (span > 0 ? ((v - t[0]) / span) * width : (v ? 0 : 0)));

  if (span === 0) {
    // Every capture on the same date: nothing proportional to express.
    return dates.map((_, i) => i * MIN_TICK_PX);
  }

  for (let i = 1; i < n; i += 1) {
    if (xs[i] - xs[i - 1] < MIN_TICK_PX) xs[i] = xs[i - 1] + MIN_TICK_PX;
  }
  if (xs[n - 1] > width) {
    xs[n - 1] = width;
    for (let i = n - 2; i >= 0; i -= 1) {
      if (xs[i + 1] - xs[i] < MIN_TICK_PX) xs[i] = xs[i + 1] - MIN_TICK_PX;
    }
  }
  return xs;
}

/** True when the axis cannot hold every tick at the minimum target size. */
export function needsVerticalLayout(count, width) {
  return count * MIN_TICK_PX > width;
}

const de = (n) => {
  const r = Math.abs(n) % 100;
  return r === 0 || r >= 20 ? 'de ' : '';
};
const zileText = (n) => (n === 1 ? 'o zi' : `${n} ${de(n)}zile`);
const luniText = (n) => (n === 1 ? 'o lună' : `${n} ${de(n)}luni`);
export const intervalText = (z) => (z < 60 ? zileText(z) : `aproximativ ${luniText(Math.round(z / 30))}`);

const _fmt = new Intl.DateTimeFormat('ro-RO', {
  day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
});
const _fmtShort = new Intl.DateTimeFormat('ro-RO', {
  day: 'numeric', month: 'long', timeZone: 'UTC',
});
export const dataLunga = (iso) => (iso ? _fmt.format(new Date(`${iso}T00:00:00Z`)) : '');
export const dataScurta = (iso) => (iso ? _fmtShort.format(new Date(`${iso}T00:00:00Z`)) : '');
export const zileIntre = (a, b) =>
  Math.round(Math.abs(new Date(`${b}T00:00:00Z`) - new Date(`${a}T00:00:00Z`)) / 86400000);

