/**
 * One honest way to turn a table on screen into a file the office can open.
 *
 * WHAT THIS IS FOR (Release 3, item 4). Seven data sets have a real export route on
 * the server. The platform has about 35 tables. Writing 28 more export routes would
 * mean 28 more places for a row ceiling and a permission check to drift apart, and
 * digging exactly that pair of faults back out of the original seven is most of what
 * this release has been.
 *
 * So there are two paths and they share one rule.
 *
 *   `downloadServerExport` - for a data set the server already knows how to read.
 *      The server does the reading, applies the permission table, and refuses rather
 *      than shortening.
 *
 *   `downloadTableRows` - for everything else. The SCREEN has already fetched every
 *      row it is showing, through its own list endpoint, which is already gated and
 *      already walked page by page by `fetchAllRows`. Those rows are posted to the
 *      server to be packaged. Nothing is read here that the person could not already
 *      read, because they are the ones who read it.
 *
 * THE RULE BOTH SHARE: **the file is complete or there is no file.** Never a short
 * one. A truncated screen is an annoyance; a truncated download leaves the building,
 * gets mailed to the trust and filed as a record, and nothing on it says it is
 * partial. Every failure below therefore throws with something a person can read,
 * and no caller is ever handed a half file to save.
 *
 * WHAT IS DELIBERATELY NOT HERE: no confirm step and no approval window. Abhimanyu
 * settled that on 2026-08-12. Reading what you may already read is not the thing that
 * needs guarding; WHO is, and that happened before any of this ran.
 */

import { API, apiFetch } from './api';
import { fetchAllRows } from './fetchAllRows';

/**
 * Every row a screen's filters match, or an error. Never a short list.
 *
 * This is the one line a screen writes to get a download control. It exists so that
 * the three ways a walk can come back incomplete - a failed page, the safety ceiling,
 * a server that says no - are handled once and identically rather than eight times
 * with a different amount of care each. `fetchAllRows` already refuses to return a
 * partial list; this turns each refusal into a sentence a person can act on.
 *
 * @param {Function} fetchPage  ({ page, limit }) => Promise<list response>, WITH the
 *                              screen's current filters already applied
 * @param {object}   [opts]
 * @param {number}   [opts.pageMax]  the most rows that endpoint returns at once
 * @param {string}   [opts.what]     what the rows are, for the wording ("students")
 */
export async function collectAllRows(fetchPage, { pageMax, what = 'rows' } = {}) {
  const all = await fetchAllRows(fetchPage, pageMax ? { pageMax } : {});
  if (!all.success) {
    throw new Error(all.detail || `Could not load every one of the ${what}. Nothing was saved.`);
  }
  if (all.truncated) {
    throw new Error(
      `There are more ${what} here than one download can hold `
      + `(${(all.total || 0).toLocaleString('en-IN')} rows). Narrow it with a filter or a `
      + 'date range and download in parts. Nothing was saved.',
    );
  }
  return all.data;
}

/** Formats a person can pick. Excel first: the office works in Excel. */
export const EXPORT_FORMATS = [
  { value: 'xlsx', label: 'Excel' },
  { value: 'csv', label: 'CSV' },
];

/**
 * Hand a downloaded file to the browser.
 *
 * The object URL is revoked afterwards. Without that, every export in a session
 * stays in memory until the tab is closed, and these files hold the whole roll.
 */
function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Turn a failed download into something worth showing a person.
 *
 * The body of a failed export is JSON even though the request asked for a file, and
 * the server's own wording is far better than anything generic: it says whether a
 * file was produced, and what to do next. Losing it and printing "export failed"
 * would waste the one useful sentence in the exchange.
 */
async function messageFor(res) {
  try {
    const body = await res.json();
    if (body && body.detail) return body.detail;
  } catch {
    /* not JSON: fall through to the status-based wording below */
  }
  if (res.status === 403) return 'You do not have permission to download this.';
  if (res.status === 401) return 'Your session has ended. Sign in again to download this.';
  return `The download failed (error ${res.status}). Nothing was saved.`;
}

const stamp = () => new Date().toISOString().slice(0, 10);

/** A filename that survives Windows, macOS and email. */
function safeName(title, format) {
  const base = String(title || 'export')
    .replace(/[^A-Za-z0-9 _-]+/g, ' ')
    .trim()
    .replace(/\s+/g, '-')
    .toLowerCase() || 'export';
  return `${base}-${stamp()}.${format === 'xlsx' ? 'xlsx' : 'csv'}`;
}

/**
 * Download one of the server's own exports.
 *
 * @param {string} path    e.g. 'students' or 'fee-transactions'
 * @param {object} params  the SCREEN'S LIVE FILTERS. Passing them is the point: a
 *                         download of "unpaid fees for April" that quietly comes
 *                         back as every fee ever taken is the same class of fault as
 *                         a short file, in the other direction.
 * @param {string} format  'xlsx' | 'csv'
 * @param {string} title   what to call the saved file
 */
export async function downloadServerExport(path, params = {}, format = 'xlsx', title = '') {
  const qs = new URLSearchParams({ format });
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  });

  const res = await apiFetch(`${API}/export/${path}?${qs.toString()}`);
  if (!res.ok) throw new Error(await messageFor(res));

  saveBlob(await res.blob(), safeName(title || path, format));
}

/**
 * Download the whole school as one Excel file, a sheet per area.
 *
 * The server reads every row itself and refuses rather than shortening any sheet, so
 * there is nothing to walk here. It also sends the per-sheet row counts back on a
 * header, which is returned so the screen can say what it saved without anybody
 * opening the file. Nine tabs is exactly the shape where one coming back short would
 * go unnoticed.
 *
 * @returns {Promise<string>} the counts, as "Children: 1876; Staff: 62; ..."
 */
export async function downloadWholeSchool() {
  const res = await apiFetch(`${API}/export/school-workbook`);
  if (!res.ok) throw new Error(await messageFor(res));

  const counts = res.headers.get('X-Export-Row-Counts') || '';
  saveBlob(await res.blob(), `the-aaryans-whole-school-${stamp()}.xlsx`);
  return counts;
}

/**
 * Package rows a screen already holds into a file.
 *
 * @param {object}   spec
 * @param {string}   spec.title    the sheet name and the basis of the filename
 * @param {string[]} spec.headers  column headings, in order
 * @param {Array[]}  spec.rows     one array of cell values per row, same order
 * @param {string}   spec.format   'xlsx' | 'csv'
 */
export async function downloadTableRows({ title, headers, rows, format = 'xlsx' }) {
  if (!headers || headers.length === 0) {
    throw new Error('This table has no columns to export.');
  }

  const res = await apiFetch(`${API}/export/table`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, headers, rows: rows || [], format }),
  });
  if (!res.ok) throw new Error(await messageFor(res));

  saveBlob(await res.blob(), safeName(title, format));
}

/**
 * Flatten what a DataTable is showing into headings and rows of plain values.
 *
 * A column's `render` is for the SCREEN - it returns React, badges, buttons, an
 * icon. Putting that through a spreadsheet gives a column of "[object Object]", so
 * a column that needs different wording in a file says so with `exportValue`, and
 * everything else falls back to the raw field. Columns marked `exportSkip` (a row's
 * action buttons, a tick box) are left out: a column of empty cells reads as missing
 * data rather than as a control that did not apply.
 */
export function tableToRows(columns, rows) {
  const cols = (columns || []).filter((c) => !c.exportSkip);
  const headers = cols.map((c) => c.exportLabel || c.label || c.key);
  const body = (rows || []).map((row) =>
    cols.map((c) => {
      const value = c.exportValue ? c.exportValue(row) : row[c.key];
      if (value === null || value === undefined) return '';
      // A blank cell is honest here in a way "not recorded" is not: the screen says
      // "not recorded" because a reader needs telling the difference between empty
      // and never-collected, but a spreadsheet is read by formulas and imports too,
      // and a word where a number belongs breaks them.
      if (typeof value === 'object') return '';
      return value;
    }),
  );
  return { headers, rows: body };
}
