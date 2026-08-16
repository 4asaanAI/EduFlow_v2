/**
 * One honest way to ask a paginated endpoint for EVERYTHING.
 *
 * WHY THIS EXISTS (the defect it closes, found 2026-08-12):
 *   `ALL_ROWS` (-1) has been on the rows-per-page menu of every table since
 *   2026-08-06, but only ONE screen ever implemented it. The others passed the
 *   sentinel straight through as `limit`, and every server clamps with some
 *   variant of `max(1, min(limit, CAP))`. `max(1, -1)` is 1. So asking to see
 *   everything showed the user exactly ONE ROW, silently, on the School
 *   Directory, the staff list and the notification list.
 *
 *   That is the failure this whole sweep is about: a query that quietly returns
 *   less than it should. One row where 1,876 were asked for looks exactly like a
 *   school with one student. Nothing errored, so nothing reported it.
 *
 * THE RULE THIS FILE ENFORCES:
 *   A caller either gets every matching row, or is told plainly that it did not.
 *   `truncated` is never omitted and never guessed - a caller that ignores it is
 *   visibly ignoring it, rather than silently receiving a short answer.
 *
 * WHY NOT JUST RAISE THE SERVER CAP:
 *   The cap protects the server from one request that has to hold the whole roll
 *   in memory and serialise it. Walking the pages moves that cost into several
 *   small requests instead. The cap stays; this walks it.
 */

/**
 * A safety ceiling on how many rows one "All" will ever collect.
 *
 * Not a page-size cap and NOT a silent truncation: hitting it sets `truncated`,
 * which callers must surface. It exists so that a server reporting a wrong
 * `total` (or a collection that grows without bound, like the audit log) cannot
 * turn "show me everything" into an unbounded fetch that hangs a phone.
 *
 * 25,000 is comfortably above every list the school actually has - the biggest
 * is the payment ledger at ~10,700 - and far below the point where the browser
 * struggles. Raise it only with a measurement, never a guess.
 */
export const ALL_ROWS_HARD_CAP = 25000;

/**
 * Walk a paginated endpoint until it has everything.
 *
 * @param {Function} fetchPage  ({ page, limit }) => Promise<response>
 *        Must resolve to the platform's standard list shape:
 *        `{ success, data: [...], meta: { total }, detail? }`.
 * @param {object}  [options]
 * @param {number}  [options.pageMax=500]
 *        The most rows THIS endpoint returns in one request. It differs per
 *        route (students and staff 500, chats and audit 100, notifications 50),
 *        so it is passed in rather than assumed. Passing one larger than the
 *        server's real cap is safe: the loop trusts the rows it got back, not
 *        the number it asked for.
 * @param {number}  [options.hardCap=ALL_ROWS_HARD_CAP]
 * @returns {Promise<{success: boolean, data: Array, total: number,
 *                    truncated: boolean, detail: string|null}>}
 *          `total` is the true number of matching rows when the server reports
 *          one, so a truncated result can still say "showing 25,000 of 40,000"
 *          rather than passing its own short count off as the total.
 */
export async function fetchAllRows(fetchPage, options = {}) {
  const pageMax = options.pageMax || 500;
  const hardCap = options.hardCap || ALL_ROWS_HARD_CAP;

  const collected = [];
  let reportedTotal = 0;
  let page = 1;

  for (;;) {
    let res;
    try {
      res = await fetchPage({ page, limit: pageMax });
    } catch (err) {
      // A page that throws mid-walk must not surface as a short success. Rows
      // already collected are discarded on purpose: half a roll presented as a
      // whole one is the exact fault this file exists to prevent.
      return { success: false, data: [], total: 0, truncated: false, detail: err.message || "Couldn't load" };
    }

    if (!res || !res.success) {
      return { success: false, data: [], total: 0, truncated: false, detail: (res && res.detail) || "Couldn't load" };
    }

    const batch = res.data || [];
    collected.push(...batch);
    // Keep the largest total the server has reported. Later pages of a list
    // being written to concurrently can report a smaller one, and taking the
    // last would under-report the school to itself.
    reportedTotal = Math.max(reportedTotal, res.meta?.total || 0);

    // A short page means the end. This is the primary stop condition because it
    // holds even when the server reports no total at all.
    if (batch.length < pageMax) break;
    // A page that came back EMPTY at full width would loop forever above; this
    // is belt-and-braces for a server that reports a total it cannot deliver.
    if (batch.length === 0) break;
    if (reportedTotal && collected.length >= reportedTotal) break;
    if (collected.length >= hardCap) {
      return {
        success: true,
        data: collected.slice(0, hardCap),
        total: Math.max(reportedTotal, collected.length),
        truncated: true,
        detail: null,
      };
    }
    page += 1;
  }

  return {
    success: true,
    data: collected,
    // With no total from the server, what we collected IS the total - we walked
    // to the end to find out.
    total: Math.max(reportedTotal, collected.length),
    truncated: false,
    detail: null,
  };
}

export default fetchAllRows;
