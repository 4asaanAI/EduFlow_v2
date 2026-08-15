/**
 * A drop-down that you can narrow by typing, WHEN there is enough in it to be worth it.
 *
 * Owner's instruction, 2026-08-07: "there should be a search option for the name among
 * the list... and try to find other places as well like these over the platform." The
 * first half was done that day, in `SearchablePicker`, and wired into exactly one
 * screen. Abhimanyu asked for the rest of it on 2026-08-15, across every list on the
 * platform that is filled from school data.
 *
 * **Why this exists beside `SearchablePicker` rather than replacing it.** That one is a
 * labelled field a form is built around, and it always shows its search box. This one is
 * a drop-in for the ~50 bare `<select>` elements already scattered through the tool
 * screens: it takes the same props a select takes, so a screen adopts it by changing the
 * tag, and it keeps whatever label, styling and test id that screen already had.
 *
 * **THREE THINGS HERE ARE DELIBERATE.**
 *
 * 1. **A short list stays exactly as it was.** Below `SEARCH_FROM` options this renders a
 *    plain select with no search box at all. A box asking you to type over six choices is
 *    slower than six choices, and every screen that adopts this must be free to do so
 *    without anybody checking first whether its list is long. The list decides, not the
 *    author.
 *
 * 2. **The count of what is shown is always visible once searching starts.** Standing
 *    rule from the tables release: a partial answer must be impossible to mistake for a
 *    complete one. Three matches out of ninety must never read like a school with three
 *    people in it.
 *
 * 3. **The chosen option is never filtered out.** Typing after choosing somebody would
 *    otherwise silently clear the selection, which is the worst kind of fault: the form
 *    looks filled in and is not.
 *
 * A search box over a TRUNCATED list is worse than the scroll it replaces, because a
 * missing name looks like a person who is not there. This control cannot know whether
 * its caller fetched everything, so that stays the caller's responsibility, exactly as
 * it is noted in `SearchablePicker`.
 */

import React, { useMemo, useState } from 'react';

// Below this, a search box costs more than it saves. Ten is roughly the point at which a
// list stops fitting on a phone screen in one go.
export const SEARCH_FROM = 10;

// Long lists are capped for the browser's sake, never silently: past this the control
// says how many are hidden and asks for more typing.
const MAX_SHOWN = 200;

const hintStyle = { fontSize: 11, color: 'var(--color-text-faint, var(--c-faint))', marginTop: 4 };

/**
 * Takes everything a `<select>` takes. `children` are the `<option>` elements the screen
 * already writes, so adopting this is a one-word change and no screen has to restate its
 * list as data.
 */
export default function SearchableSelect({
  children,
  style,
  searchPlaceholder = 'Type to narrow this list',
  'aria-label': ariaLabel,
  'data-testid': testId,
  ...rest
}) {
  const [query, setQuery] = useState('');

  const options = useMemo(() => React.Children.toArray(children), [children]);
  // A blank first entry ("Select...", "Every class") is a prompt, not a choice, so it is
  // never filtered away and never counted. Filtering it out would leave somebody unable
  // to clear their selection once they had typed.
  const isPrompt = (child) => !child?.props?.value;
  const realOptions = options.filter((child) => !isPrompt(child));

  const needle = query.trim().toLowerCase();

  const text = (child) => {
    const { children: label, label: labelProp, value } = child.props || {};
    // `label` as a prop rather than as children is used by several screens and would
    // otherwise be invisible to the search.
    const flat = labelProp !== undefined ? labelProp : label;
    return `${Array.isArray(flat) ? flat.flat(Infinity).join('') : (flat ?? '')} ${value ?? ''}`
      .toLowerCase();
  };

  const matches = needle
    ? realOptions.filter((child) => text(child).includes(needle))
    : realOptions;

  const shown = useMemo(() => {
    const capped = matches.slice(0, MAX_SHOWN);
    const chosen = realOptions.find((child) => String(child.props.value) === String(rest.value));
    if (chosen && !capped.includes(chosen)) return [chosen, ...capped];
    return capped;
  }, [matches, realOptions, rest.value]);

  const select = (
    <select {...rest} aria-label={ariaLabel} data-testid={testId} style={style}>
      {options.filter(isPrompt)}
      {shown}
    </select>
  );

  if (realOptions.length < SEARCH_FROM) return select;

  const hidden = Math.max(0, matches.length - MAX_SHOWN);

  return (
    <div data-testid={testId ? `${testId}-searchable` : undefined}>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={searchPlaceholder}
        aria-label={ariaLabel ? `Search ${ariaLabel}` : 'Search this list'}
        data-testid={testId ? `${testId}-search` : undefined}
        style={{ ...style, marginBottom: 6 }}
      />
      {select}
      <div style={hintStyle} data-testid={testId ? `${testId}-count` : undefined}>
        {matches.length === 0
          ? 'Nothing matches what you typed.'
          : hidden > 0
            ? `Showing ${MAX_SHOWN} of ${matches.length} matches. Type more to narrow it down.`
            : needle
              ? `${matches.length} of ${realOptions.length} shown.`
              : `${realOptions.length} to choose from.`}
      </div>
    </div>
  );
}
