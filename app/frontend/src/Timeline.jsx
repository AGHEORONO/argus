import React from 'react';

import { dataLunga, intervalText, zileIntre } from './timeline-layout';

/**
 * Pick two captures out of N and compare them.
 *
 * Two native `<select>`s plus an axis that is pure decoration. The axis is
 * `aria-hidden` and has no click targets, which is what makes WCAG 2.5.8 Target Size
 * inapplicable rather than merely excused — with N flights on a multi-year axis, per-tick
 * targets would be unhittable, and nudging them apart to 24px would falsify the very
 * proportionality the axis exists to show.
 *
 * A range input was never an option: its thumb moves in equal pixel steps, while ticks sit
 * at true elapsed time. Making a thumb land on a proportional tick means hand-rendering
 * track and thumb — paying the full cost of a custom widget and keeping none of the
 * native behaviour.
 */

/** Option text is the announcement — a <select> has no aria-valuetext. */
function optionText(capture, computedAgainstOther, disabled) {
  const parts = [dataLunga(capture.captured_on)];
  if (capture.label) parts.push(capture.label);
  // The ordering rule is stated once in the description; repeating it on every disabled
  // option would make arrowing through the list unbearable.
  if (!disabled) {
    parts.push(computedAgainstOther ? 'comparație calculată' : 'comparație necalculată');
  }
  return parts.join(', ');
}

export default function Timeline({
  captures,
  baselineId,
  targetId,
  onSelect,
  isComputed,
  onCompare,
  isComparing,
  pairComputed,
  opacityControl,
}) {
  if (!captures || captures.length < 2) {
    return (
      <p className="help-text">
        {captures && captures.length === 1
          ? 'Acest sit are un singur zbor înregistrat. Comparația necesită cel puțin două zboruri.'
          : 'Acest sit nu are încă zboruri înregistrate.'}
      </p>
    );
  }

  const baseIndex = captures.findIndex((c) => c.id === baselineId);
  const targetIndex = captures.findIndex((c) => c.id === targetId);
  const base = captures[baseIndex];
  const target = captures[targetIndex];
  const gap = base && target ? zileIntre(base.captured_on, target.captured_on) : null;

  const first = new Date(`${captures[0].captured_on}T00:00:00Z`).getTime();
  const last = new Date(`${captures[captures.length - 1].captured_on}T00:00:00Z`).getTime();
  const span = last - first;
  const pct = (iso) => {
    if (span <= 0) return 0;
    return ((new Date(`${iso}T00:00:00Z`).getTime() - first) / span) * 100;
  };

  const renderSelect = (which) => {
    const isBaseline = which === 'baseline';
    const selected = isBaseline ? baselineId : targetId;
    const other = isBaseline ? targetId : baselineId;
    const id = `capture-${which}`;
    return (
      <div className="capture-picker">
        <label htmlFor={id}>{isBaseline ? 'Zbor de referință' : 'Zbor comparat'}</label>
        <select
          id={id}
          className="switcher-select"
          value={selected || ''}
          aria-describedby="order-rule"
          onChange={(e) => onSelect(which, e.target.value)}
        >
          {captures.map((capture, i) => {
            // Invalid options are `disabled`, so the user agent enforces the ordering at
            // click, focus and arrow-key level alike. There is no clamping code to get wrong,
            // and self-comparison becomes unreachable.
            const disabled = isBaseline ? i >= targetIndex : i <= baseIndex;
            return (
              <option key={capture.id} value={capture.id} disabled={disabled}>
                {optionText(capture, isComputed(capture.id, other), disabled)}
              </option>
            );
          })}
        </select>
      </div>
    );
  };

  return (
    <>
      {/* Decoration only. Every fact it carries — order, intervals, computed state — is
          also in the option text and the summary line below, which is what keeps hiding it
          on narrow screens from losing information. */}
      <div className="timeline-axis" aria-hidden="true">
        <div className="axis-track" />
        {base && target && (
          <div
            className="axis-range"
            style={{
              left: `${Math.min(pct(base.captured_on), pct(target.captured_on))}%`,
              width: `${Math.abs(pct(target.captured_on) - pct(base.captured_on))}%`,
            }}
          />
        )}
        {captures.map((capture) => {
          const computed = isComputed(capture.id, capture.id === baselineId ? targetId : baselineId);
          const isEnd = capture.id === baselineId || capture.id === targetId;
          return (
            <span
              key={capture.id}
              className={`axis-tick ${computed ? 'is-computed' : 'is-open'} ${isEnd ? 'is-endpoint' : ''}`}
              style={{ left: `${pct(capture.captured_on)}%` }}
            />
          );
        })}
        <span className="axis-end axis-end-left">{dataLunga(captures[0].captured_on)}</span>
        <span className="axis-end axis-end-right">
          {dataLunga(captures[captures.length - 1].captured_on)}
        </span>
      </div>

      <div className="capture-pickers">
        {renderSelect('baseline')}
        {renderSelect('target')}
      </div>

      <p id="order-rule" className="help-text">
        Zborul de referință este întotdeauna cel anterior. Zborurile care ar inversa ordinea
        nu pot fi selectate. Poziția pe axă este proporțională cu timpul scurs.
      </p>

      {/* Summary before the button: "you chose X and Y, 49 days apart, not computed" is the
          narrative order. Plain paragraph, not a live region — the sr-only status region
          already carries the same sentence and two would double-speak. */}
      <p className="pair-summary">
        {base && target && (
          <>
            Referință: <time dateTime={base.captured_on}>{dataLunga(base.captured_on)}</time>.
            {' '}Comparat: <time dateTime={target.captured_on}>{dataLunga(target.captured_on)}</time>.
            {' '}Interval de {intervalText(gap)}.{' '}
            {pairComputed ? 'Comparația este calculată.' : 'Comparația nu a fost încă calculată.'}
          </>
        )}
      </p>

      <div className="compare-row">
        <button
          type="button"
          className="btn btn-primary"
          aria-disabled={pairComputed || isComparing}
          aria-busy={isComparing}
          aria-describedby={pairComputed ? 'compare-help' : undefined}
          onClick={() => {
            if (pairComputed || isComparing) return;
            onCompare();
          }}
        >
          Compară zborurile
        </button>
        {opacityControl}
      </div>

      {pairComputed && (
        <p id="compare-help" className="help-text">
          Comparația pentru această pereche este deja calculată.
        </p>
      )}

      {isComparing && (
        <div className="progress-group">
          <label htmlFor="compare-progress">Se calculează comparația…</label>
          <progress id="compare-progress" className="native-progress" />
        </div>
      )}
    </>
  );
}
