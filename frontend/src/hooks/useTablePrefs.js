/**
 * Remembers how many rows a user wants to see, per table (UX-DR10).
 *
 * Keyed PER TABLE on purpose. A single app-wide preference would mean that
 * sizing the 1,802-row student list also resizes the audit log and the
 * notification list, which is not what anyone means when they set it.
 *
 * Reading localStorage is parsing untrusted input: the value may be absent, a
 * string, a number this build no longer offers (an older build shipped 50), or
 * something a person typed into devtools. A throw here would white-screen the
 * whole list, so every read falls back to the default instead.
 */

import { useCallback, useState } from 'react';

/** The sizes UX-DR10 specifies, owner-chosen 2026-07-22. */
export const PAGE_SIZES = [5, 10, 15, 20, 25, 30];

/** UX-DR10: 15, not 20. */
export const DEFAULT_PAGE_SIZE = 15;

const keyFor = (tableId) => `eduflow.table.${tableId}.pageSize`;

/** Reads a stored size, returning the default for anything unusable. */
export function readStoredPageSize(tableId) {
  try {
    const raw = window.localStorage.getItem(keyFor(tableId));
    if (raw === null) return DEFAULT_PAGE_SIZE;
    const n = Number(raw);
    // Number('') is 0 and Number('abc') is NaN — both are rejected here, as is
    // any size no longer on the menu.
    if (!Number.isInteger(n) || !PAGE_SIZES.includes(n)) return DEFAULT_PAGE_SIZE;
    return n;
  } catch {
    // Private browsing and blocked-storage modes throw on access.
    return DEFAULT_PAGE_SIZE;
  }
}

/**
 * @param {string} tableId stable identifier for this table, e.g. 'students'
 * @returns {[number, (n: number) => void]}
 */
export function useTablePageSize(tableId) {
  const [pageSize, setPageSizeState] = useState(() => readStoredPageSize(tableId));

  const setPageSize = useCallback((next) => {
    const n = Number(next);
    const safe = Number.isInteger(n) && PAGE_SIZES.includes(n) ? n : DEFAULT_PAGE_SIZE;
    setPageSizeState(safe);
    try {
      window.localStorage.setItem(keyFor(tableId), String(safe));
    } catch {
      // Not being able to remember the choice is not a reason to refuse it.
    }
  }, [tableId]);

  return [pageSize, setPageSize];
}

export default useTablePageSize;
