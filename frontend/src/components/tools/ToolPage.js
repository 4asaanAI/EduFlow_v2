/**
 * Shared ToolPage layout wrapper — PREMIUM REDESIGN
 */
import React from 'react';
import { RefreshCw } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

export function ToolPage({ title, subtitle, actions, children, onRefresh, loading }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--tool-hex-1a1a1a)' : 'var(--tool-hex-f5f5f5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)';
  const secondary = isDark ? 'var(--tool-hex-a0a0a0)' : 'var(--tool-hex-525252)';
  const btnBg = isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fff)';
  const btnBorder = isDark ? 'var(--tool-hex-333)' : 'var(--tool-hex-e5e5e5)';

  return (
    <div style={{ padding: '24px 28px', overflowY: 'auto', height: '100%', background: bg }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
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
              onMouseEnter={e => e.currentTarget.style.borderColor = isDark ? 'var(--tool-hex-444)' : 'var(--tool-hex-ccc)'}
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

export function StatCard({ value, label, color = 'var(--tool-hex-4f8ff7)', sublabel, small }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-ffffff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const muted = isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)';
  return (
    <div style={{
      background: bg, border: `1px solid ${border}`, borderRadius: 14,
      padding: small ? '12px 14px' : '16px 20px',
      transition: 'all var(--transition-fast)',
    }}>
      <div style={{ fontSize: small ? 20 : 24, fontWeight: 700, color, letterSpacing: '-0.02em' }}>{value}</div>
      <div style={{ fontSize: 11, color: muted, marginTop: 4, fontWeight: 600, letterSpacing: '0.02em' }}>{label}</div>
      {sublabel && <div style={{ fontSize: 11, color: muted, marginTop: 3 }}>{sublabel}</div>}
    </div>
  );
}

export function DataTable({ title, headers, rows, emptyMsg = 'No data found', actions }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-ffffff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const rowBorder = isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-f5f5f5)';
  const thBg = isDark ? 'var(--tool-hex-1a1a1a)' : 'var(--tool-hex-fafafa)';
  const tc = isDark ? 'var(--tool-hex-a0a0a0)' : 'var(--tool-hex-525252)';
  const hc = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 14, overflow: 'hidden', marginBottom: 16 }}>
      {(title || actions) && (
        <div style={{ padding: '12px 18px', borderBottom: `1px solid ${border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {title && <span style={{ fontWeight: 600, fontSize: 14, color: hc, letterSpacing: '-0.01em' }}>{title}</span>}
          {actions && <div>{actions}</div>}
        </div>
      )}
      {rows.length === 0 ? (
        <div style={{ padding: 36, textAlign: 'center', color: isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)', fontSize: 13 }}>{emptyMsg}</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={i} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--tool-hex-737373)', textTransform: 'uppercase', letterSpacing: '0.04em', background: thBg, borderBottom: `1px solid ${border}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} style={{ borderBottom: i < rows.length - 1 ? `1px solid ${rowBorder}` : 'none', transition: 'background 0.1s ease' }}
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

export function Badge({ text, color = 'blue' }) {
  const colors = {
    green: { bg: 'rgba(52,211,153,0.1)', text: 'var(--tool-hex-34d399)', border: 'rgba(52,211,153,0.2)' },
    red: { bg: 'rgba(248,113,113,0.1)', text: 'var(--tool-hex-f87171)', border: 'rgba(248,113,113,0.2)' },
    yellow: { bg: 'rgba(251,191,36,0.1)', text: 'var(--tool-hex-fbbf24)', border: 'rgba(251,191,36,0.2)' },
    blue: { bg: 'rgba(79,143,247,0.1)', text: 'var(--tool-hex-4f8ff7)', border: 'rgba(79,143,247,0.2)' },
    purple: { bg: 'rgba(167,139,250,0.1)', text: 'var(--tool-hex-a78bfa)', border: 'rgba(167,139,250,0.2)' },
    gray: { bg: 'rgba(100,100,100,0.1)', text: 'var(--tool-hex-737373)', border: 'rgba(100,100,100,0.2)' },
  };
  const c = colors[color] || colors.blue;
  return <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 6, background: c.bg, color: c.text, border: `1px solid ${c.border}` }}>{text}</span>;
}

export function ComingSoon({ toolName }) {
  const { isDark } = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60%', gap: 16, color: 'var(--tool-hex-737373)' }}>
      <div style={{
        width: 60, height: 60, borderRadius: 16,
        background: isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-fafafa)',
        border: `1px solid ${isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24,
      }}>
        <span style={{ opacity: 0.5 }}>{'\u2699'}</span>
      </div>
      <h3 style={{ color: isDark ? 'var(--tool-hex-a0a0a0)' : 'var(--tool-hex-525252)', fontSize: 17, fontWeight: 600, letterSpacing: '-0.01em' }}>{toolName}</h3>
      <p style={{ fontSize: 13, color: isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)', textAlign: 'center', maxWidth: 300 }}>Coming soon. Backend integration in progress.</p>
    </div>
  );
}

export function FormField({ label, type = 'text', value, onChange, placeholder, options, required }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fafafa)';
  const border = isDark ? 'var(--tool-hex-333)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)';
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
          onFocus={e => e.target.style.borderColor = 'var(--tool-hex-4f8ff7)'}
          onBlur={e => e.target.style.borderColor = border} />
      )}
    </div>
  );
}

export function ActionBtn({ label, onClick, variant = 'primary', icon, disabled, type = 'button' }) {
  const { isDark } = useTheme();
  const styles = {
    primary: { background: isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)', color: isDark ? 'var(--tool-hex-171717)' : 'var(--tool-hex-fff)', border: 'none' },
    success: { background: 'rgba(52,211,153,0.1)', color: 'var(--tool-hex-34d399)', border: '1px solid rgba(52,211,153,0.2)' },
    danger: { background: 'rgba(248,113,113,0.1)', color: 'var(--tool-hex-f87171)', border: '1px solid rgba(248,113,113,0.2)' },
    secondary: { background: isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-f5f5f5)', color: isDark ? 'var(--tool-hex-a0a0a0)' : 'var(--tool-hex-525252)', border: `1px solid ${isDark ? 'var(--tool-hex-333)' : 'var(--tool-hex-e5e5e5)'}` },
  };
  const s = styles[variant] || styles.primary;
  return (
    <button type={type} onClick={onClick} disabled={disabled} style={{
      ...s, borderRadius: 10, padding: '8px 16px', fontSize: 13, fontWeight: 600,
      cursor: disabled ? 'not-allowed' : 'pointer', display: 'inline-flex',
      alignItems: 'center', gap: 6, opacity: disabled ? 0.5 : 1,
      transition: 'all var(--transition-fast)', letterSpacing: '-0.01em',
    }}>
      {icon}{label}
    </button>
  );
}

export function useToolData(fetcher, deps = []) {
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
  return { data, loading, error, reload: load };
}

// Recharts Chart Components (theme-aware)
export function LineChartWidget({ data, xKey, lines, title, height = 220 }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-ffffff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)';
  const gridColor = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-f0f0f0)';

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
            <Tooltip contentStyle={{ background: isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fff)', border: `1px solid ${border}`, borderRadius: 10, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {lines.map(l => <Line key={l.key} type="monotone" dataKey={l.key} stroke={l.color || 'var(--tool-hex-4f8ff7)'} strokeWidth={2} dot={{ r: 3 }} name={l.name || l.key} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}

export function BarChartWidget({ data, xKey, bars, title, height = 220 }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-ffffff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)';
  const gridColor = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-f0f0f0)';

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
            <Tooltip contentStyle={{ background: isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fff)', border: `1px solid ${border}`, borderRadius: 10, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {bars.map(b => <Bar key={b.key} dataKey={b.key} fill={b.color || 'var(--tool-hex-4f8ff7)'} name={b.name || b.key} radius={[5, 5, 0, 0]} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}

export function PieChartWidget({ data, title, height = 220 }) {
  const { isDark } = useTheme();
  const bg = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-ffffff)';
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';

  try {
    const { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } = require('recharts');
    const COLORS = ['var(--tool-hex-34d399)', 'var(--tool-hex-4f8ff7)', 'var(--tool-hex-f87171)', 'var(--tool-hex-fbbf24)', 'var(--tool-hex-a78bfa)'];
    return (
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 16 }}>
        {title && <div style={{ fontWeight: 600, fontSize: 14, color: text, marginBottom: 14, letterSpacing: '-0.01em' }}>{title}</div>}
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fff)', border: `1px solid ${border}`, borderRadius: 10, fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}
