/**
 * Shared ToolPage layout wrapper — PREMIUM REDESIGN
 */
import React from 'react';
import { RefreshCw, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

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
            <button onClick={onRefresh} style={{
              background: btnBg, border: `1px solid ${btnBorder}`, borderRadius: 10,
              padding: '8px 14px', color: secondary, fontSize: 13, fontWeight: 500,
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
 * way — so the screen could not tell the owner which of the two he was looking at.
 * The three states are deliberately distinguished by TEXT and by a dashed border,
 * not by colour alone (WCAG colour-not-only) and not by a tooltip, because he reads
 * this on a phone in a meeting and will never hover anything.
 *
 *   ok            — a real figure. Pass `note` for the honest footnote where the
 *                   figure is true but surprising, e.g. "1 transaction on file".
 *   unavailable   — the request failed. Never render 0 for this.
 *   not-recorded  — the field was never captured for these records (date of birth,
 *                   gender, house and admission date are empty for all 1,802
 *                   students). Not missing — never collected.
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
    state === 'unavailable' ? "Couldn't load — this is not a zero" : 'Never filled in for these records'
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
 */
export function sortableCellText(cell) {
  if (cell === null || cell === undefined) return '';
  if (typeof cell === 'string' || typeof cell === 'number') return String(cell);
  if (Array.isArray(cell)) return cell.map(sortableCellText).join(' ');
  if (typeof cell === 'object' && cell.props) return sortableCellText(cell.props.children);
  return '';
}

/** Numbers when both sides are numbers, text otherwise. */
function compareCells(a, b) {
  const ta = sortableCellText(a).trim();
  const tb = sortableCellText(b).trim();
  // Strip the decoration Indian school data carries — ₹, %, thousands separators,
  // and a trailing " days" — so "₹1,20,000" sorts above "₹9,000" rather than below
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
 * Pass `sortable={false}` for a table whose row order is itself the information —
 * a ranked list, or a timetable.
 */
export function DataTable({ title, headers, rows, emptyMsg = 'No data found', actions, loading = false, sortable = true, tableId = 'tool-table' }) {
  const { isDark } = useTheme();
  const [sortState, setSortState] = React.useState({ index: null, direction: 'ascending' });
  const bg = isDark ? 'var(--color-surface)' : 'var(--color-surface)';
  const border = isDark ? 'var(--color-border)' : 'var(--color-border)';
  const rowBorder = isDark ? 'var(--color-surface-raised)' : 'var(--color-border)';
  const thBg = isDark ? 'var(--color-page)' : 'var(--color-surface-raised)';
  const tc = isDark ? 'var(--color-text-secondary)' : 'var(--color-text-secondary)';
  const hc = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';

  const safeRows = Array.isArray(rows) ? rows : [];
  const sortedRows = React.useMemo(() => {
    if (!sortable || sortState.index === null) return safeRows;
    const factor = sortState.direction === 'descending' ? -1 : 1;
    // Copy before sorting: mutating the caller's array would reorder their state.
    return [...safeRows].sort((ra, rb) => factor * compareCells(ra[sortState.index], rb[sortState.index]));
  }, [safeRows, sortable, sortState]);

  const toggleSort = (i) => setSortState((prev) => (
    prev.index === i
      ? { index: i, direction: prev.direction === 'ascending' ? 'descending' : 'ascending' }
      : { index: i, direction: 'ascending' }
  ));

  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 14, overflow: 'hidden', marginBottom: 16 }}>
      {(title || actions) && (
        <div style={{ padding: '12px 18px', borderBottom: `1px solid ${border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {title && <span style={{ fontWeight: 600, fontSize: 14, color: hc, letterSpacing: '-0.01em' }}>{title}</span>}
          {actions && <div>{actions}</div>}
        </div>
      )}
      {loading && safeRows.length === 0 ? (
        <LoadingCard />
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
      <label style={{ display: 'block', fontSize: 12, color: muted, marginBottom: 6, fontWeight: 600 }}>{label}{required && ' *'}</label>
      {type === 'select' ? (
        <select value={value} onChange={e => onChange(e.target.value)} style={{ ...style, cursor: 'pointer' }}>
          <option value="">Select...</option>
          {(options || []).map(o => <option key={o.value || o} value={o.value || o}>{o.label || o}</option>)}
        </select>
      ) : type === 'textarea' ? (
        <textarea value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={3} style={{ ...style, resize: 'vertical' }} />
      ) : (
        <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={style}
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
      ...s, ...extraStyle, borderRadius: 10, padding: '8px 16px', fontSize: 13, fontWeight: 600,
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
