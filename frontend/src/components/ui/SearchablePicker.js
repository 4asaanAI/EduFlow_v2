/**
 * Pick one person out of a long list, by typing part of their name.
 *
 * Owner note, 2026-08-07: "there should be a search option for the name among the
 * list... and no search option among the list and try to find other places as well
 * like these over the platform".
 *
 * The school has 1,802 students. A plain dropdown of 1,802 names is unusable even
 * when it is complete, and several of these lists were not complete either: they
 * asked the server for students without a limit and got its default of twenty back.
 * Both halves have to be fixed together, because a searchable box over a truncated
 * list is worse than the scroll it replaced - it looks like the name is not there.
 *
 * Deliberately a text box plus a native select rather than a custom combobox: the
 * native control already handles keyboard, screen readers and touch correctly on
 * every device the school uses, and a hand-rolled listbox is where that quietly
 * breaks.
 */

import React, { useMemo, useState } from 'react';

const MAX_SHOWN = 200;

const wrapStyle = { display: 'flex', flexDirection: 'column', gap: 6 };

const fieldStyle = {
  width: '100%',
  background: 'var(--c-bg)',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  padding: '9px 12px',
  color: 'var(--c-text)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
};

/**
 * `options` is `[{ value, label, hint }]`. `hint` is extra text that is searched and
 * shown beside the name - a class, an admission number, a department - so two
 * children with the same name can be told apart.
 */
export default function SearchablePicker({
  label,
  value,
  onChange,
  options = [],
  placeholder = 'Type a name to narrow the list',
  required = false,
  'data-testid': testId,
}) {
  const [query, setQuery] = useState('');
  const selectId = `picker-${(label || 'value').replace(/\s+/g, '-').toLowerCase()}`;

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((o) =>
      `${o.label || ''} ${o.hint || ''}`.toLowerCase().includes(needle));
  }, [options, query]);

  // The chosen person stays selectable even when the search has narrowed them out,
  // or typing after choosing would silently clear the selection.
  const shown = useMemo(() => {
    const capped = matches.slice(0, MAX_SHOWN);
    if (value && !capped.some((o) => o.value === value)) {
      const chosen = options.find((o) => o.value === value);
      if (chosen) return [chosen, ...capped];
    }
    return capped;
  }, [matches, options, value]);

  const hiddenCount = Math.max(0, matches.length - MAX_SHOWN);

  return (
    <div style={wrapStyle}>
      {label && (
        <label htmlFor={selectId} style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>
          {label}{required ? ' *' : ''}
        </label>
      )}
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        aria-label={label ? `Search ${label}` : 'Search the list'}
        data-testid={testId ? `${testId}-search` : undefined}
        style={fieldStyle}
      />
      <select
        id={selectId}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        style={fieldStyle}
        size={1}
      >
        <option value="">Select…</option>
        {shown.map((o) => (
          <option key={o.value} value={o.value}>
            {o.hint ? `${o.label} - ${o.hint}` : o.label}
          </option>
        ))}
      </select>
      <span style={{ fontSize: 11, color: 'var(--c-faint)' }}>
        {options.length === 0
          ? 'Nothing to choose from yet.'
          : hiddenCount > 0
            ? `Showing ${MAX_SHOWN} of ${matches.length} matches. Type more to narrow it down.`
            : `${matches.length} of ${options.length} shown.`}
      </span>
    </div>
  );
}
