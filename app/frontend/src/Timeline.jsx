import React, { useEffect, useMemo, useRef, useState } from 'react';

/**
 * Pick two captures out of N along a time axis.
 *
 * Two native radio groups, not a two-thumb slider. The reason is geometry before ARIA:
 * an <input type="range"> moves its thumb linearly through value space, so it can either
 * step one capture per arrow press (forcing evenly spaced ticks) or place ticks at true
 * elapsed time (forcing arrows to step by one day). It cannot do both, and irregular
 * flight intervals need both. Radios can: each tick is its own element, positioned
 * independently, and the ordering constraint is enforced by `disabled` — which the user
 * agent honours for clicks, focus and arrow-key wrapping alike, so there is no clamping
 * code to get wrong.
 */

import {
  MIN_TICK_PX,
  dataLunga,
  intervalText,
  layoutTicks,
  needsVerticalLayout,
  zileIntre,
} from './timeline-layout';

/** Accessible name for one capture. Never an ISO string: a Romanian voice reads
 *  "2026-03-12" as "două mii douăzeci și șase minus zero trei minus doisprezece". */
function captureName(capture, computed) {
  const parts = [dataLunga(capture.captured_on)];
  if (capture.label) parts.push(capture.label);
  parts.push(computed ? 'cu rezultat' : 'fără rezultat');
  if (!capture.has_tiles) parts.push('fără imagini pe hartă');
  return parts.join(', ');
}

export default function Timeline({
  captures,
  baselineId,
  targetId,
  onChange,
  computedPairs,
  children,
}) {
  const trackRef = useRef(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = trackRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    // Container width, not a viewport media query: 1.4.10 is defined at 400% zoom of a
    // 1280px viewport, which a viewport query can miss entirely.
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const dates = useMemo(() => captures.map((c) => c.captured_on), [captures]);
  const vertical = width > 0 && needsVerticalLayout(captures.length, width);
  const xs = useMemo(
    () => (vertical || width === 0 ? [] : layoutTicks(dates, Math.max(0, width - MIN_TICK_PX))),
    [dates, width, vertical]
  );

  const baseIndex = captures.findIndex((c) => c.id === baselineId);
  const targetIndex = captures.findIndex((c) => c.id === targetId);

  const isComputed = (a, b) => {
    if (!a || !b) return false;
    const key = [a, b].sort().join('|');
    return computedPairs.has(key);
  };

  const renderGroup = (which) => {
    const isBaseline = which === 'baseline';
    const selected = isBaseline ? baselineId : targetId;
    const legendId = `timeline-${which}-legend`;
    const helpId = `timeline-${which}-help`;

    return (
      <fieldset className={`timeline-group timeline-group-${which}`}>
        <legend id={legendId}>{isBaseline ? 'Zbor de referință' : 'Zbor comparat'}</legend>
        <p id={helpId} className="help-text timeline-help">
          {isBaseline
            ? 'Zborul mai vechi din pereche. Schimbările se măsoară față de el.'
            : 'Zborul mai nou din pereche.'}{' '}
          „cu rezultat” înseamnă că perechea formată cu celălalt zbor selectat are deja o
          comparație calculată.
        </p>
        <div className={`timeline-track ${vertical ? 'is-vertical' : ''}`} ref={isBaseline ? trackRef : null}>
          {captures.map((capture, i) => {
            // The user agent enforces the ordering: a disabled radio cannot be focused,
            // clicked, or reached by arrow keys, and native arrow-wrap skips it. No input
            // path can produce an out-of-order or self-comparing pair.
            const disabled = isBaseline ? i >= targetIndex : i <= baseIndex;
            const other = isBaseline ? targetId : baselineId;
            const checked = capture.id === selected;
            return (
              <div
                key={capture.id}
                className="timeline-tick-slot"
                style={vertical ? undefined : { left: `${xs[i] ?? 0}px` }}
              >
                <input
                  type="radio"
                  className="timeline-tick"
                  id={`tick-${which}-${capture.id}`}
                  name={`capture-${which}`}
                  value={capture.id}
                  checked={checked}
                  disabled={disabled}
                  aria-describedby={helpId}
                  onChange={() => onChange(which, capture.id)}
                />
                <label htmlFor={`tick-${which}-${capture.id}`}>
                  <span className="sr-only">{captureName(capture, isComputed(capture.id, other))}</span>
                  <span
                    className={`tick-mark ${isComputed(capture.id, other) ? 'is-computed' : 'is-open'}`}
                    aria-hidden="true"
                  />
                  {vertical && (
                    <span className="tick-row-text" aria-hidden="true">
                      {dataLunga(capture.captured_on)}
                      {capture.label ? ` — ${capture.label}` : ''}
                      {isComputed(capture.id, other) ? ' · cu rezultat' : ''}
                    </span>
                  )}
                </label>
              </div>
            );
          })}
        </div>
      </fieldset>
    );
  };

  const base = captures[baseIndex];
  const target = captures[targetIndex];
  const gap = base && target ? zileIntre(base.captured_on, target.captured_on) : null;

  return (
    <>
      <div className="timeline-readout">
        <span>
          <span aria-hidden="true" className="readout-caps">REFERINȚĂ </span>
          <time dateTime={base?.captured_on}>{dataLunga(base?.captured_on)}</time>
        </span>
        {gap !== null && (
          <span className="readout-gap">
            <span aria-hidden="true">Δ </span>
            {intervalText(gap)}
          </span>
        )}
        <span>
          <span aria-hidden="true" className="readout-caps">COMPARAT </span>
          <time dateTime={target?.captured_on}>{dataLunga(target?.captured_on)}</time>
        </span>
      </div>

      {renderGroup('baseline')}
      {renderGroup('target')}

      {children}
    </>
  );
}
