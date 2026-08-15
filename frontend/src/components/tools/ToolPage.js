/**
 * Shared ToolPage layout wrapper - PREMIUM REDESIGN
 */
import React from 'react';
import { RefreshCw, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import ExportButton from '../ui/ExportButton';
import SearchableSelect from '../ui/SearchableSelect';

export function ToolPage({ title, subtitle, actions, children, onRefresh, loading }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--color-page)' : 'var(--color-page)';
  const text = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';
  const muted = isDark ? 'var(--color-text-muted)' : 'var(--color-text-muted)';
  const secondary = isDark ? 'var(--color-text-secondary)' : 'var(--color-text-secondary)';
  const btnBg = isDark ? 'var(--color-surface-raised)' : 'var(--color-surface)';
  const btnBorder = isDark ? 'var(--color-border-strong)' : 'var(--color-border)';

  return (
    <div style={{ padding: '20px 16px', overflowY: 'auto', height: '100%', background: bg }}>
      <div className="tool-header-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: text, marginBottom: 4, letterSpacing: '-0.02em' }}>{title}</h1>
          {subtitle && <p style={{ fontSize: 13, color: muted }}>{subtitle}</p>}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {actions}
          {onRefresh && (
            // 40px minimum. Phone and tablet are the primary devices here, and a
            // 36px control is one a thumb mis-hits. Set here rather than on each
            // screen because every tool page shares this one button.
            <button onClick={onRefresh} style={{
              background: btnBg, border: `1px solid ${btnBorder}`, borderRadius: 10,
              padding: '8px 14px', minHeight: 40, color: secondary, fontSize: 13, fontWeight: 500,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              transition: 'all var(--transition-fast)',
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = isDark ? 'var(--color-border-strong)' : 'var(--color-border-strong)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = btnBorder}>
              <RefreshCw size={13} style={loading ? { animation: 'spin 0.8s linear infinite' } : {}} />
              Refresh
            </button>
          )}
        </div>
      </div>
      {children}
    </div>
  );
}

/**
 * A single figure.
 *
 * `state` exists because of owner item 7 (UI Sweep, Epic 4). A figure that failed to
 * load used to render as `0`, and a `0` that is genuinely nought rendered the same
 * way - so the screen could not tell the owner which of the two he was looking at.
 * The three states are deliberately distinguished by TEXT and by a dashed border,
 * not by colour alone (WCAG colour-not-only) and not by a tooltip, because he reads
 * this on a phone in a meeting and will never hover anything.
 *
 *   ok            - a real figure. Pass `note` for the honest footnote where the
 *                   figure is true but surprising, e.g. "1 transaction on file".
 *   unavailable   - the request failed. Never render 0 for this.
 *   not-recorded  - the field was never captured for these records (date of birth,
 *                   gender, house and admission date are empty for all 1,802
 *                   students). Not missing - never collected.
 */
export function StatCard({ value, label, color = 'var(--color-accent-blue)', sublabel, small, state = 'ok', note, 'data-testid': testId }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--color-surface)' : 'var(--color-surface)';
  const border = isDark ? 'var(--color-border)' : 'var(--color-border)';
  const muted = isDark ? 'var(--color-text-muted)' : 'var(--color-text-muted)';

  const isReal = state === 'ok';
  const displayValue = state === 'unavailable'
    ? 'Unavailable'
    : state === 'not-recorded' ? 'Not recorded' : value;
  const footnote = isReal ? note : (
    state === 'unavailable' ? "Couldn't load - this is not a zero" : 'Never filled in for these records'
  );

  return (
    <div
      data-testid={testId}
      data-stat-state={state}
      style={{
        background: bg,
        border: isReal ? `1px solid ${border}` : `1px dashed ${border}`,
        borderRadius: 14,
        padding: small ? '12px 14px' : '16px 20px',
        transition: 'all var(--transition-fast)',
      }}>
      <div style={{
        fontSize: isReal ? (small ? 20 : 24) : (small ? 13 : 15),
        fontWeight: 700,
        color: isReal ? color : muted,
        letterSpacing: '-0.02em',
      }}>{displayValue}</div>
      <div style={{ fontSize: 11, color: muted, marginTop: 4, fontWeight: 600, letterSpacing: '0.02em' }}>{label}</div>
      {sublabel && <div style={{ fontSize: 11, color: muted, marginTop: 3 }}>{sublabel}</div>}
      {footnote && <div style={{ fontSize: 11, color: muted, marginTop: 3, fontWeight: 400 }}>{footnote}</div>}
    </div>
  );
}

export function LoadingCard({ message = 'Loading data...' }) {
  return (
    <div role="status" aria-live="polite" style={{ padding: 24 }}>
      <div className="skeleton" style={{ height: 12, width: '42%', marginBottom: 12 }} />
      <div className="skeleton" style={{ height: 12, width: '68%', marginBottom: 12 }} />
      <div className="skeleton" style={{ height: 12, width: '54%', marginBottom: 10 }} />
      <span style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>{message}</span>
    </div>
  );
}

export function ErrorCard({ message = 'Unable to load data.', onRetry }) {
  return (
    <div role="alert" style={{
      background: 'color-mix(in srgb, var(--color-danger) 7%, transparent)',
      border: '1px solid color-mix(in srgb, var(--color-danger) 30%, transparent)',
      borderRadius: 10,
      color: 'var(--color-danger)',
      padding: 14,
      marginBottom: 16,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
      fontSize: 13,
    }}>
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} style={{
          border: '1px solid currentColor',
          borderRadius: 8,
          background: 'transparent',
          color: 'inherit',
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 700,
          padding: '7px 10px',
        }}>
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Pull comparable text out of a cell.
 *
 * Cells in this table are whatever the calling screen passed: a string, a number,
 * or a React element such as `<span style={...}>₹12,400</span>`. Sorting has to see
 * through the element to the text a person actually reads, or half the columns on
 * the platform would sort by "[object Object]".
 *
 * DOWNLOADS USE THIS TOO (Release 3, item 4), which is why it gained the prop
 * fallback below. A cell holding `<Badge text="Draft" />` keeps its only readable
 * word in a PROP rather than in its children, so reading children alone returned an
 * empty string - which sorted every Badge column as blank, and would have put an
 * empty column into every downloaded file. A blank column in a spreadsheet reads as
 * missing data rather than as something that could not be converted.
 */
export function sortableCellText(cell) {
  if (cell === null || cell === undefined) return '';
  if (typeof cell === 'string' || typeof cell === 'number') return String(cell);
  if (typeof cell === 'boolean') return cell ? 'Yes' : 'No';
  if (Array.isArray(cell)) return cell.map(sortableCellText).join(' ').replace(/\s+/g, ' ');
  if (typeof cell === 'object' && cell.props) {
    const fromChildren = sortableCellText(cell.props.children).trim();
    if (fromChildren) return fromChildren;
    // The props a component in this codebase uses to carry its one word of text.
    for (const key of ['text', 'label', 'title', 'value', 'name']) {
      const held = cell.props[key];
      if (typeof held === 'string' || typeof held === 'number') return String(held);
    }
  }
  return '';
}

/** Numbers when both sides are numbers, text otherwise. */
function compareCells(a, b) {
  const ta = sortableCellText(a).trim();
  const tb = sortableCellText(b).trim();
  // Strip the decoration Indian school data carries - ₹, %, thousands separators,
  // and a trailing " days" - so "₹1,20,000" sorts above "₹9,000" rather than below
  // it, which is what a plain string comparison would do.
  const numeric = (s) => {
    const cleaned = s.replace(/[₹,%\s]/g, '').replace(/days?$/i, '');
    if (cleaned === '' || !/^-?\d*\.?\d+$/.test(cleaned)) return null;
    return parseFloat(cleaned);
  };
  const na = numeric(ta);
  const nb = numeric(tb);
  if (na !== null && nb !== null) return na - nb;
  // Blanks and "not recorded" sort last in ascending order rather than floating to
  // the top, where they would push the rows someone is looking for off the screen.
  const aEmpty = ta === '' || /^not recorded$/i.test(ta);
  const bEmpty = tb === '' || /^not recorded$/i.test(tb);
  if (aEmpty !== bEmpty) return aEmpty ? 1 : -1;
  return ta.localeCompare(tb, 'en', { numeric: true, sensitivity: 'base' });
}

/**
 * Column sorting for a table that CANNOT move onto `DataTable` (D-24).
 *
 * `DataTable` takes rows as arrays of cells. A handful of screens cannot express
 * themselves that way - a certificate row can expand into a full-width "reason for
 * rejection" row underneath it, an exam sheet holds a live marks input per row, a
 * timetable's cells span periods. Those keep their own <table>, and take their sorting
 * from here so it behaves, reads and announces itself EXACTLY like every other table on
 * the platform rather than being invented a second time per screen.
 *
 * It sorts a list of OBJECTS (what those screens already hold) rather than cell arrays,
 * so the screen's own <td> rendering is untouched.
 *
 * @param {Array} items       the full result set, in the order the server gave it
 * @param {Array} accessors   one entry per column, in column order: a function
 *                            `(item) => comparable value`, or `null` for a column that
 *                            must not offer sorting (an actions column, a checkbox).
 * @returns {{items: Array, index: number|null, direction: string, toggle: Function}}
 */
export function useColumnSort(items, accessors) {
  const [state, setState] = React.useState({ index: null, direction: 'ascending' });

  // Memoised for the same reason `DataTable.safeRows` is: without it the `: []` branch
  // is a new array every render, and the sort below would re-run forever.
  const safe = React.useMemo(() => (Array.isArray(items) ? items : []), [items]);

  const sorted = React.useMemo(() => {
    const accessor = state.index === null ? null : accessors[state.index];
    if (!accessor) return safe;
    const factor = state.direction === 'descending' ? -1 : 1;
    // Copy before sorting - mutating the caller's array would reorder their state.
    return [...safe].sort((a, b) => factor * compareCells(accessor(a), accessor(b)));
  }, [safe, accessors, state]);

  const toggle = React.useCallback((i) => setState((prev) => (
    prev.index === i
      ? { index: i, direction: prev.direction === 'ascending' ? 'descending' : 'ascending' }
      : { index: i, direction: 'ascending' }
  )), []);

  return { items: sorted, index: state.index, direction: state.direction, toggle };
}

/**
 * The `<thead>` row for a table using `useColumnSort`.
 *
 * Kept as one component so the accessibility contract is written once: `aria-sort` lives
 * on the `<th>` (that is what a screen reader announces for the column) and the control
 * is a real `<button>` (so the column is sortable from the keyboard). Getting either of
 * those wrong is invisible until someone who needs them tries to use the screen.
 *
 * `thStyle` is passed in because these screens each have their own header styling and
 * this change is about sorting, not about restyling them underneath their owners. It may
 * be a plain object, or `(index) => style` where columns differ (a sticky first column,
 * centred numeric columns).
 */
export function SortableHeaderRow({ headers, sort, accessors, thStyle, trStyle, tableId = 'tool-table' }) {
  const styleFor = (i) => (typeof thStyle === 'function' ? thStyle(i) : thStyle);
  return (
    <tr style={trStyle}>
      {headers.map((label, i) => {
        const canSort = Boolean(accessors[i]);
        const thStyleI = styleFor(i);
        const isSorted = canSort && sort.index === i;
        const ariaSort = isSorted ? sort.direction : 'none';
        const inner = {
          display: 'inline-flex', alignItems: 'center', gap: 5, width: '100%',
          background: 'none', border: 'none', padding: 0, font: 'inherit',
          color: isSorted ? 'var(--color-accent-blue)' : 'inherit',
          cursor: canSort ? 'pointer' : 'default',
          textAlign: thStyleI?.textAlign || 'left',
          justifyContent: thStyleI?.textAlign === 'center' ? 'center' : undefined,
        };
        if (!canSort) {
          return <th key={i} scope="col" style={thStyleI}>{label}</th>;
        }
        const Glyph = isSorted
          ? (sort.direction === 'ascending' ? ChevronUp : ChevronDown)
          : ChevronsUpDown;
        return (
          <th key={i} scope="col" aria-sort={ariaSort} style={thStyleI}>
            <button
              type="button"
              data-testid={`${tableId}-sort-${i}`}
              onClick={() => sort.toggle(i)}
              style={inner}
            >
              {label}
              <Glyph size={11} aria-hidden="true" style={{ opacity: isSorted ? 1 : 0.4, flexShrink: 0 }} />
            </button>
          </th>
        );
      })}
    </tr>
  );
}

/**
 * The tool-screen table.
 *
 * Column sorting was added here in UI Sweep Epic 4 rather than screen by screen:
 * 33 tool screens render through this one component, so FR82 ("any list that may
 * exceed 20 rows supports at minimum one column-level sort") is satisfied for all
 * of them at once. Asked for directly by the owner, 2026-07-22.
 *
 * The sort is CLIENT-SIDE and that is correct HERE, unlike in `ui/DataTable`: these
 * screens hand over their complete result set, so ordering the array IS ordering the
 * whole set. `ui/DataTable` is server-paginated, where a client sort would reorder
 * only the visible page and lie about the rest.
 *
 * Pass `sortable={false}` for a table whose row order is itself the information -
 * a ranked list, or a timetable.
 *
 * EVERY ONE OF THESE TABLES CAN BE DOWNLOADED (Release 3, item 4), and the button is
 * here rather than on each screen for the same reason the sort is: about seventy
 * tables render through this one component. `exportable={false}` turns it off for a
 * table that is a control panel rather than a record.
 *
 * These screens hand over their COMPLETE result set, so the file holds everything the
 * table holds. Where a screen deliberately shows a summary - "Top 10 defaulters", the
 * ten most recent expenses - the file holds that same summary, and the table's own
 * title travels with it into the filename so the file says which it is. A screen that
 * wants the full list downloadable instead should pass `exportRows`.
 */
export function DataTable({ title, headers, rows, emptyMsg = 'No data found', actions, loading = false, sortable = true, tableId = 'tool-table', exportable = true, exportRows = null, filterable = true }) {
  const { isDark } = useTheme();
  const [sortState, setSortState] = React.useState({ index: null, direction: 'ascending' });
  const [search, setSearch] = React.useState('');
  const [picked, setPicked] = React.useState({});
  const bg = isDark ? 'var(--color-surface)' : 'var(--color-surface)';
  const border = isDark ? 'var(--color-border)' : 'var(--color-border)';
  const rowBorder = isDark ? 'var(--color-surface-raised)' : 'var(--color-border)';
  const thBg = isDark ? 'var(--color-page)' : 'var(--color-surface-raised)';
  const tc = isDark ? 'var(--color-text-secondary)' : 'var(--color-text-secondary)';
  const hc = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';

  // Memoised because `sortedRows` below depends on it: without this, the `: []`
  // branch would produce a brand-new array every render and re-sort on every render.
  const safeRows = React.useMemo(() => (Array.isArray(rows) ? rows : []), [rows]);

  // ── Filtering (Release 3, item C) ──────────────────────────────────────────
  //
  // Here rather than on each screen, for the third time and the same reason: about
  // seventy tables render through this one component. Sorting arrived this way in
  // July and the download in item 5 of this release; a filter written seventy times
  // by hand would be seventy chances to filter the screen and not the file.
  //
  // TWO KINDS, because a person filters in two ways. They type a name or a number,
  // or they pick a value out of a column: a status, a class, a category. The typed
  // search reads every cell; the pickers appear on their own, for any column whose
  // values repeat enough to be worth choosing between.
  //
  // THE THRESHOLD IS LOW ON PURPOSE. Abhimanyu asked for filters wherever the data
  // is OR COULD BECOME too much to go through by hand, so this is not reserved for
  // the tables that are long today - eight rows is enough for the controls to earn
  // their place, and a list of eight is a list of eighty next term.
  const FILTER_FROM = 8;

  // A column is worth a picker when its values repeat: a handful of distinct values
  // across many rows is a status or a category. Many distinct values is a name or an
  // amount, where a dropdown of 300 options is worse than typing.
  const columnFilters = React.useMemo(() => {
    if (!filterable || safeRows.length < FILTER_FROM) return [];
    return (headers || []).map((h, i) => {
      const values = new Set();
      for (const row of safeRows) {
        const text = sortableCellText((row || [])[i]);
        if (text !== '') values.add(text);
        if (values.size > 12) return null;
      }
      if (values.size < 2 || values.size > safeRows.length * 0.6) return null;
      return { index: i, label: typeof h === 'string' ? h : `Column ${i + 1}`, values: [...values].sort() };
    }).filter(Boolean);
  }, [filterable, headers, safeRows]);

  const filteredRows = React.useMemo(() => {
    const needle = search.trim().toLowerCase();
    const active = Object.entries(picked).filter(([, v]) => v !== '');
    if (!needle && active.length === 0) return safeRows;
    return safeRows.filter((row) => {
      for (const [index, want] of active) {
        if (sortableCellText((row || [])[Number(index)]) !== want) return false;
      }
      if (!needle) return true;
      return (row || []).some((cell) => sortableCellText(cell).toLowerCase().includes(needle));
    });
  }, [safeRows, search, picked]);

  const sortedRows = React.useMemo(() => {
    if (!sortable || sortState.index === null) return filteredRows;
    const factor = sortState.direction === 'descending' ? -1 : 1;
    // Copy before sorting: mutating the caller's array would reorder their state.
    return [...filteredRows].sort((ra, rb) => factor * compareCells(ra[sortState.index], rb[sortState.index]));
  }, [filteredRows, sortable, sortState]);

  const isFiltered = sortedRows.length !== safeRows.length;
  const showFilters = filterable && safeRows.length >= FILTER_FROM;

  // What a download holds. The rows are already the complete set this table was
  // given, so this is not a page: it is the table. `exportRows` lets a screen hand
  // over plain values where its cells are drawn rather than written.
  const showExport = exportable && safeRows.length > 0 && (headers || []).length > 0;
  const exportColumns = React.useMemo(
    () => (headers || []).map((h, i) => ({ key: String(i), label: typeof h === 'string' ? h : `Column ${i + 1}` })),
    [headers],
  );

  // WHAT A DOWNLOAD HOLDS WHEN A FILTER IS ON, and it is the whole point of doing the
  // filtering here. A file that quietly holds the whole list when the screen was
  // filtered is the same fault as a short file, in the other direction: somebody
  // narrows to one class, downloads, and files a document about the whole school
  // under that class's name.
  //
  // `exportRows` is a screen's plain-value copy of the same rows, so it is followed
  // by POSITION while a filter is on. If a screen ever hands over a differently sized
  // list, the positions do not line up and the safe answer is the rows on screen,
  // which are the ones the person is actually looking at.
  const parallelExport = exportRows && exportRows.length === safeRows.length ? exportRows : null;
  const downloadRows = React.useCallback(
    async () => {
      let source;
      if (!isFiltered) {
        source = exportRows || sortedRows;
      } else if (parallelExport) {
        source = sortedRows.map((row) => parallelExport[safeRows.indexOf(row)] || row);
      } else {
        source = sortedRows;
      }
      return source.map(
        (row) => Object.fromEntries((row || []).map((cell, i) => [String(i), sortableCellText(cell)])),
      );
    },
    [exportRows, sortedRows, isFiltered, parallelExport, safeRows],
  );

  const toggleSort = (i) => setSortState((prev) => (
    prev.index === i
      ? { index: i, direction: prev.direction === 'ascending' ? 'descending' : 'ascending' }
      : { index: i, direction: 'ascending' }
  ));

  return (
    <div className="responsive-table-card" style={{ background: bg, border: `1px solid ${border}`, borderRadius: 14, overflow: 'hidden', marginBottom: 16 }}>
      {(title || actions || showExport) && (
        <div className="tool-header-row" style={{ padding: '12px 18px', borderBottom: `1px solid ${border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          {title && <span style={{ fontWeight: 600, fontSize: 14, color: hc, letterSpacing: '-0.01em' }}>{title}</span>}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {actions && <div>{actions}</div>}
            {showExport && (
              <ExportButton
                title={title || 'Export'}
                testId={`${tableId}-export`}
                getRows={downloadRows}
                columns={exportColumns}
              />
            )}
          </div>
        </div>
      )}
      {showFilters && (
        <div
          className="tool-filter-row"
          data-testid={`${tableId}-filters`}
          style={{
            padding: '10px 18px', borderBottom: `1px solid ${border}`,
            display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
          }}
        >
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid={`${tableId}-search`}
            aria-label={`Search ${title || 'this table'}`}
            placeholder="Search this table"
            style={{
              // 16px so a phone does not zoom the page in when the field is tapped.
              // That magnification is exactly what the owner reported on 6 August.
              flex: '1 1 180px', maxWidth: 260, fontSize: 16, padding: '8px 12px',
              minHeight: 40, borderRadius: 8, border: `1px solid ${border}`,
              background: bg, color: hc, outline: 'none',
            }}
          />
          {/* Type-to-search, 2026-08-15. These filters are built from whatever is in the
              column, so on a school of this size one of them can hold hundreds of
              entries. `SearchableSelect` leaves a short filter exactly as it was and
              adds the search box only where the list has grown past being scrollable. */}
          {columnFilters.map((f) => (
            <SearchableSelect
              key={f.index}
              value={picked[f.index] || ''}
              onChange={(e) => setPicked((p) => ({ ...p, [f.index]: e.target.value }))}
              data-testid={`${tableId}-filter-${f.index}`}
              aria-label={`Filter by ${f.label}`}
              searchPlaceholder={`Type to find a ${f.label.toLowerCase()}`}
              style={{
                fontSize: 16, padding: '8px 10px', minHeight: 40, borderRadius: 8,
                border: `1px solid ${border}`, background: bg, color: hc, outline: 'none',
              }}
            >
              <option value="">All {f.label.toLowerCase()}</option>
              {f.values.map((v) => <option key={v} value={v}>{v}</option>)}
            </SearchableSelect>
          ))}
          {/* THE COUNT IS ALWAYS VISIBLE. This whole release is about a query that
              quietly returns less than it should, and a filter is the one control
              whose entire job is to return less. Saying "24 of 1,876" is what stops
              a narrowed screen from being read, or downloaded, as the whole list. */}
          <span
            aria-live="polite"
            data-testid={`${tableId}-filter-count`}
            style={{ fontSize: 12, color: 'var(--color-text-muted)', marginLeft: 'auto' }}
          >
            {isFiltered
              ? `Showing ${sortedRows.length.toLocaleString('en-IN')} of ${safeRows.length.toLocaleString('en-IN')}`
              : `${safeRows.length.toLocaleString('en-IN')} rows`}
          </span>
          {isFiltered && (
            <button
              type="button"
              onClick={() => { setSearch(''); setPicked({}); }}
              data-testid={`${tableId}-filter-clear`}
              style={{
                background: 'none', border: 'none', padding: '8px 4px', minHeight: 40,
                cursor: 'pointer', color: 'var(--color-accent-blue)', font: 'inherit', fontSize: 12,
              }}
            >
              Clear
            </button>
          )}
        </div>
      )}
      {loading && safeRows.length === 0 ? (
        <LoadingCard />
      ) : sortedRows.length === 0 && safeRows.length > 0 ? (
        // A filtered-to-nothing table must not say "No data found". That reads as an
        // empty school rather than a narrow filter, which is this release's fault in
        // miniature.
        <div data-testid={`${tableId}-no-match`} style={{ padding: 36, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
          Nothing here matches that filter. {safeRows.length.toLocaleString('en-IN')} rows are hidden.
        </div>
      ) : safeRows.length === 0 ? (
        <div style={{ padding: 36, textAlign: 'center', color: isDark ? 'var(--color-text-muted)' : 'var(--color-text-muted)', fontSize: 13 }}>{emptyMsg}</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {headers.map((h, i) => {
                  const isSorted = sortable && sortState.index === i;
                  const headerStyle = {
                    padding: 0, textAlign: 'left', background: thBg,
                    borderBottom: `1px solid ${border}`, whiteSpace: 'nowrap',
                  };
                  const labelStyle = {
                    display: 'inline-flex', alignItems: 'center', gap: 5, width: '100%',
                    padding: '10px 16px', fontSize: 11, fontWeight: 600,
                    color: isSorted ? 'var(--color-accent-blue)' : 'var(--color-text-faint)',
                    textTransform: 'uppercase', letterSpacing: '0.04em', textAlign: 'left',
                  };
                  if (!sortable) {
                    return <th key={i} style={headerStyle}><span style={labelStyle}>{h}</span></th>;
                  }
                  const SortGlyph = isSorted
                    ? (sortState.direction === 'ascending' ? ChevronUp : ChevronDown)
                    : ChevronsUpDown;
                  return (
                    // aria-sort belongs on the <th>: that is what a screen reader
                    // announces for the column (WCAG sortable-table).
                    <th key={i} scope="col" aria-sort={isSorted ? sortState.direction : 'none'} style={headerStyle}>
                      {/* A real <button>, so the column is sortable by keyboard. */}
                      <button
                        type="button"
                        data-testid={`${tableId}-sort-${i}`}
                        onClick={() => toggleSort(i)}
                        style={{ ...labelStyle, background: 'none', border: 'none', cursor: 'pointer', font: 'inherit', fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}
                      >
                        {h}
                        <SortGlyph size={12} aria-hidden="true" style={{ opacity: isSorted ? 1 : 0.4, flexShrink: 0 }} />
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row, i) => (
                <tr key={i} style={{ borderBottom: i < sortedRows.length - 1 ? `1px solid ${rowBorder}` : 'none', transition: 'background 0.1s ease' }}
                  onMouseEnter={e => e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  {row.map((cell, j) => (
                    <td key={j} style={{ padding: '10px 16px', fontSize: 13, color: tc }}>
                      {typeof cell === 'object' ? cell : String(cell ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function Badge({ text, label, color = 'blue' }) {
  const displayText = text ?? label;
  const named = {
    green: { bg: 'rgba(52,211,153,0.1)', text: 'var(--color-success)', border: 'rgba(52,211,153,0.2)' },
    red: { bg: 'rgba(248,113,113,0.1)', text: 'var(--color-danger)', border: 'rgba(248,113,113,0.2)' },
    yellow: { bg: 'rgba(251,191,36,0.1)', text: 'var(--color-warning)', border: 'rgba(251,191,36,0.2)' },
    blue: { bg: 'rgba(79,143,247,0.1)', text: 'var(--color-accent-blue)', border: 'rgba(79,143,247,0.2)' },
    purple: { bg: 'rgba(167,139,250,0.1)', text: 'var(--color-purple)', border: 'rgba(167,139,250,0.2)' },
    gray: { bg: 'rgba(100,100,100,0.1)', text: 'var(--color-text-faint)', border: 'rgba(100,100,100,0.2)' },
  };
  const c = named[color] || {
    bg: `color-mix(in srgb, ${color} 15%, transparent)`,
    text: color,
    border: `color-mix(in srgb, ${color} 30%, transparent)`,
  };
  return <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 6, background: c.bg, color: c.text, border: `1px solid ${c.border}`, whiteSpace: 'nowrap' }}>{displayText}</span>;
}

export function ComingSoon({ toolName }) {
  const { isDark } = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60%', gap: 16, color: 'var(--color-text-faint)' }}>
      <div style={{
        width: 60, height: 60, borderRadius: 16,
        background: isDark ? 'var(--color-surface)' : 'var(--color-surface-raised)',
        border: `1px solid ${isDark ? 'var(--color-border)' : 'var(--color-border)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24,
      }}>
        <span style={{ opacity: 0.5 }}>{'\u2699'}</span>
      </div>
      <h3 style={{ color: isDark ? 'var(--color-text-secondary)' : 'var(--color-text-secondary)', fontSize: 17, fontWeight: 600, letterSpacing: '-0.01em' }}>{toolName}</h3>
      <p style={{ fontSize: 13, color: isDark ? 'var(--color-text-muted)' : 'var(--color-text-muted)', textAlign: 'center', maxWidth: 300 }}>Coming soon. Backend integration in progress.</p>
    </div>
  );
}

export function FormField({ label, type = 'text', value, onChange, placeholder, options, required }) {
  const fieldId = React.useId();
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--color-surface-raised)' : 'var(--color-surface-raised)';
  const border = isDark ? 'var(--color-border-strong)' : 'var(--color-border)';
  const text = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';
  const muted = isDark ? 'var(--color-text-muted)' : 'var(--color-text-muted)';
  const style = {
    width: '100%', background: bg, border: `1px solid ${border}`, borderRadius: 10,
    padding: '9px 14px', color: text, fontSize: 13, outline: 'none',
    transition: 'border-color 0.2s ease',
  };
  return (
    <div style={{ marginBottom: 14 }}>
      <label htmlFor={fieldId} style={{ display: 'block', fontSize: 12, color: muted, marginBottom: 6, fontWeight: 600 }}>{label}{required && ' *'}</label>
      {type === 'select' ? (
        // Type-to-search, 2026-08-15. This one field is used across roughly 25 tool
        // forms, and what fills it varies from four fixed words to every child in the
        // school. The control decides from the length of the list rather than the
        // author having to, so a short one is untouched.
        <SearchableSelect id={fieldId} aria-label={label} value={value} onChange={e => onChange(e.target.value)} style={{ ...style, cursor: 'pointer' }}>
          <option value="">Select...</option>
          {(options || []).map(o => <option key={o.value || o} value={o.value || o}>{o.label || o}</option>)}
        </SearchableSelect>
      ) : type === 'textarea' ? (
        <textarea id={fieldId} aria-label={label} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={3} style={{ ...style, resize: 'vertical' }} />
      ) : (
        <input id={fieldId} aria-label={label} type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={style}
          onFocus={e => e.target.style.borderColor = 'var(--color-accent-blue)'}
          onBlur={e => e.target.style.borderColor = border} />
      )}
    </div>
  );
}

// `data-testid` is forwarded because UX-DR4 requires it on every interactive element
// and this button is used across ~25 tool screens; swallowing it made those screens
// untestable by anything but text matching.
export function ActionBtn({ label, onClick, variant = 'primary', icon, disabled, type = 'button', style: extraStyle, 'data-testid': testId, 'aria-busy': ariaBusy }) {
  const { isDark } = useTheme();
  const styles = {
    primary: { background: '#4f8ff7', color: '#ffffff', border: 'none' },
    success: { background: 'rgba(52,211,153,0.1)', color: 'var(--color-success)', border: '1px solid rgba(52,211,153,0.2)' },
    danger: { background: 'rgba(248,113,113,0.1)', color: 'var(--color-danger)', border: '1px solid rgba(248,113,113,0.2)' },
    secondary: { background: isDark ? 'var(--color-surface-raised)' : 'var(--color-surface)', color: isDark ? 'var(--color-text-secondary)' : 'var(--color-text-secondary)', border: `1px solid ${isDark ? 'var(--color-border-strong)' : 'var(--color-border)'}` },
  };
  const s = styles[variant] || styles.primary;
  return (
    <button type={type} onClick={onClick} disabled={disabled} data-testid={testId} aria-busy={ariaBusy} style={{
      // `minHeight: 40` comes BEFORE the spread of `extraStyle` deliberately, so a
      // screen that has its own reason to be taller still wins. What it stops is a
      // control coming out SHORTER than a thumb can reliably hit, which the phone
      // sweep found on Add Student, Add Staff and Load defaulters (Release 3, item E).
      ...s, minHeight: 40, ...extraStyle, borderRadius: 10, padding: '8px 16px', fontSize: 13, fontWeight: 600,
      cursor: disabled ? 'not-allowed' : 'pointer', display: 'inline-flex',
      alignItems: 'center', gap: 6, opacity: disabled ? 0.5 : 1,
      transition: 'all var(--transition-fast)', letterSpacing: '-0.01em',
    }}>
      {icon}{label}
    </button>
  );
}

export function useToolData(fetcher, deps = [], options = {}) {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const load = React.useCallback(async () => {
    setLoading(true);
    try { const result = await fetcher(); setData(result); setError(null); }
    catch (e) { setError(e.message); }
    setLoading(false);
    // Intentional: `deps` is the CALLER's invalidation list, by design - this is a
    // generic data hook, so `fetcher` is recreated every render and must NOT be a
    // dependency (it would refetch forever). ESLint can't verify a variable deps
    // array, hence the disable. Scoped to this ONE line; the wider exhaustive-deps
    // sweep (D-16, ~30 warnings across a dozen files) stays its own deferred pass.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  React.useEffect(() => { load(); }, [load]);
  const ErrorView = options.renderError === null ? null : (options.renderError || ErrorCard);
  return { data, loading, error, reload: load, ErrorView };
}

// Recharts Chart Components (theme-aware)
export function LineChartWidget({ data, xKey, lines, title, height = 220 }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--color-surface)' : 'var(--color-surface)';
  const border = isDark ? 'var(--color-border)' : 'var(--color-border)';
  const text = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';
  const muted = isDark ? 'var(--color-text-muted)' : 'var(--color-text-muted)';
  const gridColor = isDark ? 'var(--color-border)' : 'var(--color-surface-muted)';

  try {
    const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } = require('recharts');
    return (
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 16 }}>
        {title && <div style={{ fontWeight: 600, fontSize: 14, color: text, marginBottom: 14, letterSpacing: '-0.01em' }}>{title}</div>}
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: muted }} />
            <YAxis tick={{ fontSize: 11, fill: muted }} />
            <Tooltip contentStyle={{ background: isDark ? 'var(--color-surface-raised)' : 'var(--color-surface)', border: `1px solid ${border}`, borderRadius: 10, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {lines.map(l => <Line key={l.key} type="monotone" dataKey={l.key} stroke={l.color || 'var(--color-accent-blue)'} strokeWidth={2} dot={{ r: 3 }} name={l.name || l.key} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}

export function BarChartWidget({ data, xKey, bars, title, height = 220 }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--color-surface)' : 'var(--color-surface)';
  const border = isDark ? 'var(--color-border)' : 'var(--color-border)';
  const text = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';
  const muted = isDark ? 'var(--color-text-muted)' : 'var(--color-text-muted)';
  const gridColor = isDark ? 'var(--color-border)' : 'var(--color-surface-muted)';

  try {
    const { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } = require('recharts');
    return (
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 16 }}>
        {title && <div style={{ fontWeight: 600, fontSize: 14, color: text, marginBottom: 14, letterSpacing: '-0.01em' }}>{title}</div>}
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: muted }} />
            <YAxis tick={{ fontSize: 11, fill: muted }} />
            <Tooltip contentStyle={{ background: isDark ? 'var(--color-surface-raised)' : 'var(--color-surface)', border: `1px solid ${border}`, borderRadius: 10, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {bars.map(b => <Bar key={b.key} dataKey={b.key} fill={b.color || 'var(--color-accent-blue)'} name={b.name || b.key} radius={[5, 5, 0, 0]} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}

export function PieChartWidget({ data, title, height = 220 }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--color-surface)' : 'var(--color-surface)';
  const border = isDark ? 'var(--color-border)' : 'var(--color-border)';
  const text = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';

  try {
    const { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } = require('recharts');
    const COLORS = ['var(--color-success)', 'var(--color-accent-blue)', 'var(--color-danger)', 'var(--color-warning)', 'var(--color-purple)'];
    return (
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 16 }}>
        {title && <div style={{ fontWeight: 600, fontSize: 14, color: text, marginBottom: 14, letterSpacing: '-0.01em' }}>{title}</div>}
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: isDark ? 'var(--color-surface-raised)' : 'var(--color-surface)', border: `1px solid ${border}`, borderRadius: 10, fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}
