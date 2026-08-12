/**
 * The platform's shared sortable, paginated table - FR82, UX-DR5, UX-DR10.
 *
 * Built once so FR82 ("any list over 20 rows supports pagination and at
 * minimum one column-level sort") is satisfied once rather than re-implemented
 * per screen, and so Epic 7's School Directory has something to consume.
 *
 * THE THING MOST LIKELY TO BE GOT WRONG:
 *   Sorting is SERVER-SIDE. `onSortChange` asks the API to re-order the whole
 *   result set and hand back page 1. Sorting the 20 rows already on screen
 *   would look identical on a 20-row table and be a lie on a 1,802-row one.
 *   This component therefore never sorts `rows` itself - it renders them in
 *   the order it was given. If you find yourself adding `rows.sort(...)` here,
 *   the bug is upstream.
 *
 * Accessibility:
 *   - each sortable heading is a real <button> inside its <th>, so it is
 *     reachable and operable by keyboard;
 *   - the <th> carries aria-sort=ascending|descending|none, which is how a
 *     screen-reader user learns the current order (WCAG `sortable-table`);
 *   - the caption is visually hidden but announced.
 *
 * Mobile:
 *   the table stays ONE element and its wrapper scrolls. It is never switched
 *   to display:block with display:table children - that splits a table into
 *   two independently-sized tables and de-aligns every heading from its
 *   column, which is exactly the regression logged as D-01.
 */

import React from 'react';
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { Button, EmptyState } from './primitives';
import ExportButton from './ExportButton';
import { ALL_ROWS, PAGE_SIZES, pageSizeLabel } from '../../hooks/useTablePrefs';

const srOnly = {
  position: 'absolute', width: 1, height: 1, padding: 0, margin: -1,
  overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0,
};

/**
 * Renders a cell value, distinguishing "never captured" from "empty".
 *
 * The school's data makes this a real distinction rather than a nicety: dob,
 * gender, house and admission_date are blank for all 1,802 students because
 * they were never collected. Showing a bare dash invites someone to read it as
 * a data fault. See §12 of the source-of-truth document.
 */
export function cellValue(value) {
  if (value === null || value === undefined || value === '') {
    return <span style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>not recorded</span>;
  }
  return value;
}

function SortIcon({ state }) {
  const Icon = state === 'ascending' ? ChevronUp : state === 'descending' ? ChevronDown : ChevronsUpDown;
  return (
    <Icon
      size={13}
      aria-hidden="true"
      style={{ opacity: state === 'none' ? 0.4 : 1, flexShrink: 0 }}
    />
  );
}

/**
 * @param {object}   props
 * @param {Array}    props.columns  [{ key, label, sortKey?, align?, render? }]
 *                                  A column is sortable only if it has a
 *                                  sortKey the SERVER accepts. A heading that
 *                                  offers to sort and then does nothing is
 *                                  worse than one that does not offer.
 * @param {Array}    props.rows     the current page, in the order the server gave them
 * @param {string}   props.sort           active server sort key
 * @param {Function} props.onSortChange   (sortKey) => void - must refetch from page 1
 * @param {number}   props.page
 * @param {number}   props.total          total matching rows across all pages
 * @param {number}   props.pageSize
 * @param {Function} props.onPageChange
 * @param {Function} props.onPageSizeChange
 * @param {boolean}  props.loading
 * @param {string}   props.error          message if the fetch failed
 * @param {object}   props.exportTable    optional download control for this table.
 *                   `{ title, getRows }` to package the rows the screen holds, or
 *                   `{ title, serverExport: { path, params } }` to use one of the
 *                   server's own exports. `getRows` must return EVERY row matching
 *                   the filters in force - see ExportButton for why the page on
 *                   screen is never the right answer.
 */
export default function DataTable({
  columns,
  rows = [],
  caption,
  rowKey = (r, i) => r.id ?? i,
  onRowClick,
  sort,
  sortDirection = 'ascending',
  onSortChange,
  page = 1,
  total = 0,
  pageSize,
  pageSizes,
  onPageChange,
  onPageSizeChange,
  loading = false,
  error = null,
  emptyTitle,
  emptyMessage,
  tableId = 'table',
  exportTable = null,
}) {
  // ALL_ROWS (-1) means "one page holding everything", so the page count is 1 and
  // Prev/Next are both disabled. Without this the arithmetic divides by -1 and the
  // page count comes out negative.
  const totalPages = pageSize === ALL_ROWS
    ? 1
    : Math.max(1, Math.ceil(total / (pageSize || 1)));
  const selectId = `${tableId}-page-size`;

  // ── Rows drawn as you scroll (Release 3, item D) ───────────────────────────
  //
  // "All" means ALL THE DATA, drawn as you scroll (Abhimanyu, 2026-08-12). Every row
  // is fetched and held; what changes is that the browser is not asked to lay out
  // 1,876 table rows in one go, which is what makes the student list and the School
  // Directory stutter on a phone.
  //
  // WHY GROW-ON-SCROLL RATHER THAN A VIRTUAL WINDOW. A windowed list draws a fixed
  // slice and moves it, which needs every row to be the same known height. These rows
  // are not: a child's cell carries a name and an admission number under it, and a
  // wrapped name on a phone is taller again. Guessing the height wrong makes the
  // scrollbar lie about how much is left, and this release is about not lying about
  // how much there is. Growing the list keeps the browser's own scrollbar honest.
  //
  // IT NEVER HIDES ANYTHING. Ctrl+F is the thing people actually use to find a name,
  // so an undrawn row would be a row that is not there as far as the person is
  // concerned. That is why the count below says how many are drawn AND how many
  // there are, and why there is a button as well as the scroll: an IntersectionObserver
  // that never fires would otherwise strand the rest of the list silently.
  const DRAW_STEP = 100;
  const [drawn, setDrawn] = React.useState(DRAW_STEP);
  const sentinelRef = React.useRef(null);

  // Back to the top of the list whenever the rows themselves change - a new page, a
  // new filter, a new sort. Keeping the old figure would draw 900 rows of a list the
  // person has just narrowed to twelve.
  React.useEffect(() => { setDrawn(DRAW_STEP); }, [rows]);

  const visibleRows = rows.length > drawn ? rows.slice(0, drawn) : rows;
  const moreToDraw = rows.length - visibleRows.length;

  React.useEffect(() => {
    const node = sentinelRef.current;
    // No IntersectionObserver (older Safari, and jsdom in the tests) means the button
    // below is the only way on. It is always rendered, so nothing is unreachable.
    if (!node || moreToDraw <= 0 || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) setDrawn((n) => n + DRAW_STEP);
    }, { rootMargin: '400px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [moreToDraw]);

  // A failed load must never be dressed up as an empty result - owner item 7.
  if (error) {
    return <EmptyState kind="error" message={error} data-testid={`${tableId}-error`} />;
  }
  if (!loading && rows.length === 0) {
    return <EmptyState kind="empty" title={emptyTitle} message={emptyMessage} data-testid={`${tableId}-empty`} />;
  }

  return (
    <div data-testid={`${tableId}-datatable`}>
      {/* The WRAPPER scrolls. The table itself is never re-laid-out. */}
      <div
        style={{
          overflowX: 'auto',
          WebkitOverflowScrolling: 'touch',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-xl)',
          background: 'var(--color-surface)',
        }}
      >
        <table style={{ width: '100%', minWidth: '100%', borderCollapse: 'collapse' }}>
          {caption ? <caption style={srOnly}>{caption}</caption> : null}
          <thead>
            <tr>
              {columns.map((col) => {
                const isSorted = col.sortKey && col.sortKey === sort;
                const ariaSort = isSorted ? sortDirection : 'none';
                return (
                  <th
                    key={col.key}
                    scope="col"
                    // aria-sort is set on the <th>, not the button - this is
                    // what a screen reader reads out for the column.
                    aria-sort={col.sortKey ? ariaSort : undefined}
                    style={{
                      textAlign: col.align || 'left',
                      padding: 0,
                      background: 'var(--color-surface-raised)',
                      borderBottom: '1px solid var(--color-border)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {col.sortKey ? (
                      <button
                        type="button"
                        data-testid={`${tableId}-sort-${col.key}`}
                        onClick={() => onSortChange && onSortChange(col.sortKey)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: col.align === 'right' ? 'flex-end' : 'flex-start',
                          gap: 5,
                          width: '100%',
                          padding: '11px 14px',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          font: 'inherit',
                          fontFamily: 'var(--font-display)',
                          fontSize: 'var(--text-xs)',
                          fontWeight: 700,
                          letterSpacing: '0.04em',
                          textTransform: 'uppercase',
                          textAlign: col.align || 'left',
                          color: isSorted ? 'var(--color-accent-blue)' : 'var(--color-text-secondary)',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        {col.label}
                        <SortIcon state={ariaSort} />
                      </button>
                    ) : (
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '11px 14px',
                          fontFamily: 'var(--font-display)',
                          fontSize: 'var(--text-xs)',
                          fontWeight: 700,
                          letterSpacing: '0.04em',
                          textTransform: 'uppercase',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        {col.label}
                      </span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, i) => (
              <tr
                key={rowKey(row, i)}
                className="tool-table-row"
                // A clickable row is a convenience, never the only way in: any
                // screen using this must also expose the action on a real
                // focusable control inside the row, or keyboard users lose it.
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                style={{
                  borderBottom: '1px solid var(--color-border-subtle, var(--color-border))',
                  cursor: onRowClick ? 'pointer' : undefined,
                }}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    style={{
                      padding: '11px 14px',
                      textAlign: col.align || 'left',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--color-text-primary)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {col.render ? col.render(row) : cellValue(row[col.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* HOW MANY ARE DRAWN, AND HOW MANY THERE ARE. Without this line a list that has
          only painted its first hundred rows is indistinguishable from a list of a
          hundred rows, which is this release's defining fault wearing a new hat. The
          button is here as well as the scroll because a scroll that does not fire
          would otherwise strand the rest of the list with nothing to say so. */}
      {moreToDraw > 0 && (
        <div
          ref={sentinelRef}
          data-testid={`${tableId}-draw-more`}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 10, flexWrap: 'wrap', padding: '10px 4px',
          }}
        >
          <span
            aria-live="polite"
            data-testid={`${tableId}-drawn-count`}
            style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}
          >
            {`Showing ${visibleRows.length.toLocaleString('en-IN')} of `
             + `${rows.length.toLocaleString('en-IN')} loaded rows. Scroll for more.`}
          </span>
          <Button
            size="sm"
            variant="secondary"
            data-testid={`${tableId}-draw-more-button`}
            onClick={() => setDrawn((n) => n + DRAW_STEP)}
          >
            Show more
          </Button>
        </div>
      )}

      {/* Pagination + rows-per-page (UX-DR10): the size selector sits beside
          the pagination control and shows its active value. */}
      <div
        className="tool-header-row"
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 12, flexWrap: 'wrap', marginTop: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* A real visible label, not placeholder-only (WCAG input-labels). */}
          <label
            htmlFor={selectId}
            style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-display)', fontWeight: 600 }}
          >
            Rows
          </label>
          <select
            id={selectId}
            data-testid={`${tableId}-page-size`}
            value={pageSize}
            onChange={(e) => onPageSizeChange && onPageSizeChange(Number(e.target.value))}
            style={{
              background: 'var(--color-surface-raised)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-text-primary)',
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-sm)',
              padding: '7px 10px',
              minHeight: 40,
            }}
          >
            {/* `pageSizes` lets a table offer a narrower menu than the full set.
                The All Chats page does, because its rows can be selected and deleted
                in bulk and the server caps that at 100. See BULK_SAFE_PAGE_SIZES. */}
            {(pageSizes || PAGE_SIZES).map((n) => (
              <option key={n} value={n}>{pageSizeLabel(n)}</option>
            ))}
          </select>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
            of {total.toLocaleString('en-IN')}
          </span>
        </div>

        {/* The download control, when the screen supplies one. It lives beside the
            row count on purpose: the count is what tells a person how much the file
            should hold, which is the only way to notice a short one. */}
        {exportTable ? (
          <ExportButton
            title={exportTable.title || caption || tableId}
            columns={exportTable.columns || columns}
            getRows={exportTable.getRows}
            serverExport={exportTable.serverExport}
            // The count this table is already showing, so a download that comes back
            // short of it is refused rather than saved. See ExportButton.
            total={total}
            testId={`${tableId}-export`}
          />
        ) : null}

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button
            size="sm"
            variant="secondary"
            icon={ChevronLeft}
            data-testid={`${tableId}-prev`}
            disabled={page <= 1}
            onClick={() => onPageChange && onPageChange(Math.max(1, page - 1))}
          >
            Prev
          </Button>
          {/* aria-live so a screen reader hears the page change. */}
          <span
            aria-live="polite"
            data-testid={`${tableId}-page-indicator`}
            style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-display)', fontWeight: 600 }}
          >
            Page {page} of {totalPages}
          </span>
          <Button
            size="sm"
            variant="secondary"
            data-testid={`${tableId}-next`}
            disabled={page >= totalPages}
            onClick={() => onPageChange && onPageChange(page + 1)}
          >
            Next <ChevronRight size={13} aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}
