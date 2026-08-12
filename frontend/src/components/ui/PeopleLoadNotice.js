/**
 * "The list of children could not be loaded" - said out loud, on the screen.
 *
 * THE FAULT THIS CLOSES (Release 3, item C). Every screen with a person-picker on it
 * loaded the roll with the same line:
 *
 *     getAllStudents().then(r => { if (r.success) setStudents(r.data || []); })
 *
 * There is no `else`. So when the load failed the picker simply stayed empty, and an
 * empty picker on a school of 1,876 children reads as "there are no children",
 * "nobody matches", or "this feature is broken" - three different wrong conclusions,
 * none of them the true one, which is "ask again in a minute".
 *
 * Before Release 3 the failure was worse and quieter still: the walk returned the
 * rows it had managed to collect, marked partial, and nothing anywhere read that
 * mark. So a picker showed 500 of 1,876 children and reported a genuinely enrolled
 * child as not on the roll. Making the walk fail properly was right, and it turned a
 * silently short picker into a silently empty one. This is the other half of that
 * fix: neither state is allowed to be silent.
 *
 * The whole release is one idea - a query that quietly returns less than it should -
 * and a picker is where it costs a real person their afternoon.
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { getAllStudents } from '../../lib/api';

/**
 * Load the whole roll into a screen's state, and say so when it does not work.
 *
 * @param {Function} setStudents  state setter for the rows
 * @param {Function} setError     state setter for the message ('' when all is well)
 * @param {object}   [params]     filters passed to the list endpoint
 */
export function loadStudentsInto(setStudents, setError, params = {}) {
  return getAllStudents(params).then((r) => {
    if (r.success) {
      setStudents(r.data || []);
      setError('');
      return r;
    }
    // The rows are cleared as well as the message being set. Leaving a stale list
    // behind a failure notice is how somebody picks a child who is no longer on it.
    setStudents([]);
    setError(
      r.detail
        || 'The list of children could not be loaded, so this list is empty rather '
        + 'than complete. Try again in a moment.',
    );
    return r;
  }).catch((err) => {
    setStudents([]);
    setError(
      (err && err.message)
        || 'The list of children could not be loaded. Try again in a moment.',
    );
    return { success: false, data: [] };
  });
}

/**
 * The notice itself. Renders nothing when there is nothing wrong.
 *
 * `role="alert"` so a screen reader hears it: an empty picker announces nothing at
 * all, which is the whole problem here in its purest form.
 */
export default function PeopleLoadNotice({ error, onRetry, testId = 'people-load-error' }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      data-testid={testId}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
        padding: '8px 12px', marginBottom: 10, borderRadius: 8,
        background: 'var(--color-accent-red-soft, #fef3f2)',
        color: 'var(--color-accent-red, #b42318)',
        fontSize: 'var(--text-sm)',
      }}
    >
      <AlertTriangle size={14} aria-hidden="true" />
      <span>{error}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          data-testid={`${testId}-retry`}
          style={{
            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            color: 'inherit', textDecoration: 'underline', font: 'inherit',
          }}
        >
          Try again
        </button>
      )}
    </div>
  );
}
