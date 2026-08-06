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

/**
 * How many rows a page may show.
 *
 * The first six are the sizes UX-DR10 specifies, owner-chosen 2026-07-22. The rest
 * were added on 2026-08-06 at the owner's request (item 13): "the max number of the
 * table should be the max number present and not limited to 30". That decision was
 * taken when the biggest list in the product was short; with 1,802 students, 30 a
 * page is 61 pages to walk through.
 *
 * ALL_ROWS is a sentinel, not a count. A screen that supports it asks the server for
 * everything — in batches, because a single request is capped at 500 rows — and then
 * shows the lot on one page. It is deliberately last, and deliberately not the
 * default: on the student list it means holding 1,802 rows in one screen.
 */
export const ALL_ROWS = -1;
export const PAGE_SIZES = [5, 10, 15, 20, 25, 30, 50, 100, 250, 500, ALL_ROWS];

/** What to print for a size in a menu. */
export function pageSizeLabel(size) {
  return size === ALL_ROWS ? 'All' : String(size);
}

/**
 * Sizes for a table whose rows can be SELECTED and acted on in bulk.
 *
 * The All Chats page lets a person tick a whole page and delete it, and the server
 * refuses a bulk delete of more than CONVERSATION_BULK_DELETE_MAX (100) at once. A
 * page of 250, 500 or All would therefore let someone build a selection the server
 * would reject — so those tables are offered the smaller menu instead. This is the
 * safeguard the existing test in Epic6NothingGetsLost.test.js was written to demand.
 */
export const BULK_SAFE_PAGE_SIZES = PAGE_SIZES.filter((n) => n !== ALL_ROWS && n <= 100);

/** UX-DR10: 15, not 20. */
export const DEFAULT_PAGE_SIZE = 15;

const keyFor = (tableId) => `eduflow.table.${tableId}.pageSize`;

/**
 * Reads a stored size, returning the default for anything unusable.
 *
 * `allowed` narrows what counts as usable, so a table offering the bulk-safe menu
 * does not silently honour a 500 left in storage by a table that offers all of them.
 */
export function readStoredPageSize(tableId, allowed = PAGE_SIZES) {
  try {
    const raw = window.localStorage.getItem(keyFor(tableId));
    if (raw === null) return DEFAULT_PAGE_SIZE;
    const n = Number(raw);
    // Number('') is 0 and Number('abc') is NaN — both are rejected here, as is
    // any size no longer on the menu.
    if (!Number.isInteger(n) || !allowed.includes(n)) return DEFAULT_PAGE_SIZE;
    return n;
  } catch {
    // Private browsing and blocked-storage modes throw on access.
    return DEFAULT_PAGE_SIZE;
  }
}

/**
 * @param {string} tableId stable identifier for this table, e.g. 'students'
 * @param {number[]} [allowed] the sizes THIS table offers; defaults to all of them
 * @returns {[number, (n: number) => void]}
 */
export function useTablePageSize(tableId, allowed = PAGE_SIZES) {
  const [pageSize, setPageSizeState] = useState(() => readStoredPageSize(tableId, allowed));

  const setPageSize = useCallback((next) => {
    const n = Number(next);
    const safe = Number.isInteger(n) && allowed.includes(n) ? n : DEFAULT_PAGE_SIZE;
    setPageSizeState(safe);
    try {
      window.localStorage.setItem(keyFor(tableId), String(safe));
    } catch {
      // Not being able to remember the choice is not a reason to refuse it.
    }
    // `allowed` is a module-level constant array at every call site, so it is stable.
  }, [tableId, allowed]);

  return [pageSize, setPageSize];
}

export default useTablePageSize;
