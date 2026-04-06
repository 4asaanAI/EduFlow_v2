/**
 * Shared ToolPage layout wrapper — THEME-AWARE
 */
import React from 'react';
import { RefreshCw } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

export function ToolPage({ title, subtitle, actions, children, onRefresh, loading }) {
  const { isDark } = useTheme();
  const bg = isDark ? '#0A0A0F' : '#F8F9FC';
  const text = isDark ? '#fff' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const btnBg = isDark ? '#161622' : '#fff';
  const btnBorder = isDark ? '#222230' : '#E2E8F0';

  return (
    <div style={{ padding: '20px 24px', overflowY: 'auto', height: '100%', background: bg }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 20, fontWeight: 600, color: text, marginBottom: 2 }}>{title}</h1>
          {subtitle && <p style={{ fontSize: 12, color: muted }}>{subtitle}</p>}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {actions}
          {onRefresh && (
            <button onClick={onRefresh} style={{ background: btnBg, border: `1px solid ${btnBorder}`, borderRadius: 7, padding: '6px 12px', color: muted, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
              <RefreshCw size={11} style={loading ? { animation: 'spin 0.8s linear infinite' } : {}} />
              Refresh
            </button>
          )}
        </div>
      </div>
      {children}
    </div>
  );
}

export function StatCard({ value, label, color = '#3B82F6', sublabel, small }) {
  const { isDark } = useTheme();
  const bg = isDark ? '#161622' : '#FFFFFF';
  const border = isDark ? '#222230' : '#E2E8F0';
  const muted = isDark ? '#64748B' : '#94A3B8';
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: small ? '10px 12px' : '14px 16px' }}>
      <div style={{ fontSize: small ? 18 : 22, fontWeight: 700, color, fontFamily: 'Outfit, sans-serif' }}>{value}</div>
      <div style={{ fontSize: 9, color: muted, marginTop: 3, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 700 }}>{label}</div>
      {sublabel && <div style={{ fontSize: 10, color: muted, marginTop: 2 }}>{sublabel}</div>}
    </div>
  );
}

export function DataTable({ title, headers, rows, emptyMsg = 'No data found', actions }) {
  const { isDark } = useTheme();
  const bg = isDark ? '#161622' : '#FFFFFF';
  const border = isDark ? '#222230' : '#E2E8F0';
  const rowBorder = isDark ? '#1A1A24' : '#F1F5F9';
  const thBg = isDark ? '#0F0F1A' : '#F8F9FC';
  const tc = isDark ? '#94A3B8' : '#475569';
  const hc = isDark ? '#E2E8F0' : '#0F172A';
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 11, overflow: 'hidden', marginBottom: 16 }}>
      {(title || actions) && (
        <div style={{ padding: '10px 16px', borderBottom: `1px solid ${border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {title && <span style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 13, color: hc }}>{title}</span>}
          {actions && <div>{actions}</div>}
        </div>
      )}
      {rows.length === 0 ? (
        <div style={{ padding: 28, textAlign: 'center', color: isDark ? '#64748B' : '#94A3B8', fontSize: 12 }}>{emptyMsg}</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={i} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 9.5, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', background: thBg, borderBottom: `1px solid ${border}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} style={{ borderBottom: i < rows.length - 1 ? `1px solid ${rowBorder}` : 'none' }}>
                  {row.map((cell, j) => (
                    <td key={j} style={{ padding: '9px 14px', fontSize: 12, color: tc }}>
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
    green: { bg: 'rgba(16,185,129,0.1)', text: '#10B981', border: 'rgba(16,185,129,0.25)' },
    red: { bg: 'rgba(239,68,68,0.1)', text: '#EF4444', border: 'rgba(239,68,68,0.25)' },
    yellow: { bg: 'rgba(245,158,11,0.1)', text: '#F59E0B', border: 'rgba(245,158,11,0.25)' },
    blue: { bg: 'rgba(59,130,246,0.1)', text: '#60A5FA', border: 'rgba(59,130,246,0.25)' },
    purple: { bg: 'rgba(139,92,246,0.1)', text: '#A78BFA', border: 'rgba(139,92,246,0.25)' },
    gray: { bg: 'rgba(100,116,139,0.1)', text: '#64748B', border: 'rgba(100,116,139,0.25)' },
  };
  const c = colors[color] || colors.blue;
  return <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 5, background: c.bg, color: c.text, border: `1px solid ${c.border}` }}>{text}</span>;
}

export function ComingSoon({ toolName }) {
  const { isDark } = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60%', gap: 12, color: '#64748B' }}>
      <div style={{ width: 56, height: 56, borderRadius: 12, background: isDark ? '#161622' : '#F1F5F9', border: `1px solid ${isDark ? '#222230' : '#E2E8F0'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>🔧</div>
      <h3 style={{ fontFamily: 'Outfit, sans-serif', color: isDark ? '#94A3B8' : '#475569', fontSize: 16, fontWeight: 600 }}>{toolName}</h3>
      <p style={{ fontSize: 12, color: isDark ? '#475569' : '#94A3B8', textAlign: 'center', maxWidth: 300 }}>Coming soon. Backend integration in progress.</p>
    </div>
  );
}

export function FormField({ label, type = 'text', value, onChange, placeholder, options, required }) {
  const { isDark } = useTheme();
  const bg = isDark ? '#161622' : '#F8F9FC';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const style = { width: '100%', background: bg, border: `1px solid ${border}`, borderRadius: 7, padding: '8px 12px', color: text, fontSize: 12, outline: 'none' };
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', fontSize: 10, color: muted, marginBottom: 4, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}{required && ' *'}</label>
      {type === 'select' ? (
        <select value={value} onChange={e => onChange(e.target.value)} style={style}>
          <option value="">Select...</option>
          {(options || []).map(o => <option key={o.value || o} value={o.value || o}>{o.label || o}</option>)}
        </select>
      ) : type === 'textarea' ? (
        <textarea value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={3} style={{ ...style, resize: 'vertical' }} />
      ) : (
        <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={style} />
      )}
    </div>
  );
}

export function ActionBtn({ label, onClick, variant = 'primary', icon, disabled, type = 'button' }) {
  const styles = {
    primary: { background: '#3B82F6', color: '#fff', border: 'none' },
    success: { background: 'rgba(16,185,129,0.1)', color: '#10B981', border: '1px solid rgba(16,185,129,0.3)' },
    danger: { background: 'rgba(239,68,68,0.1)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.3)' },
    secondary: { background: 'rgba(100,116,139,0.1)', color: '#94A3B8', border: '1px solid rgba(100,116,139,0.3)' },
  };
  const s = styles[variant] || styles.primary;
  return (
    <button type={type} onClick={onClick} disabled={disabled} style={{ ...s, borderRadius: 7, padding: '7px 14px', fontSize: 12, fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5, opacity: disabled ? 0.5 : 1 }}>
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
export function LineChartWidget({ data, xKey, lines, title, height = 200 }) {
  const { isDark } = useTheme();
  const bg = isDark ? '#161622' : '#FFFFFF';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const gridColor = isDark ? '#222230' : '#F1F5F9';

  try {
    const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } = require('recharts');
    return (
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: '14px 16px', marginBottom: 16 }}>
        {title && <div style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 13, color: text, marginBottom: 12 }}>{title}</div>}
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: muted }} />
            <YAxis tick={{ fontSize: 10, fill: muted }} />
            <Tooltip contentStyle={{ background: isDark ? '#1C1C28' : '#fff', border: `1px solid ${border}`, borderRadius: 8, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {lines.map(l => <Line key={l.key} type="monotone" dataKey={l.key} stroke={l.color || '#3B82F6'} strokeWidth={2} dot={{ r: 3 }} name={l.name || l.key} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}

export function BarChartWidget({ data, xKey, bars, title, height = 200 }) {
  const { isDark } = useTheme();
  const bg = isDark ? '#161622' : '#FFFFFF';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';
  const muted = isDark ? '#64748B' : '#94A3B8';
  const gridColor = isDark ? '#222230' : '#F1F5F9';

  try {
    const { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } = require('recharts');
    return (
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: '14px 16px', marginBottom: 16 }}>
        {title && <div style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 13, color: text, marginBottom: 12 }}>{title}</div>}
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: muted }} />
            <YAxis tick={{ fontSize: 10, fill: muted }} />
            <Tooltip contentStyle={{ background: isDark ? '#1C1C28' : '#fff', border: `1px solid ${border}`, borderRadius: 8, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {bars.map(b => <Bar key={b.key} dataKey={b.key} fill={b.color || '#3B82F6'} name={b.name || b.key} radius={[4, 4, 0, 0]} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}

export function PieChartWidget({ data, title, height = 200 }) {
  const { isDark } = useTheme();
  const bg = isDark ? '#161622' : '#FFFFFF';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#E2E8F0' : '#0F172A';

  try {
    const { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } = require('recharts');
    const COLORS = ['#10B981', '#3B82F6', '#EF4444', '#F59E0B', '#8B5CF6'];
    return (
      <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: '14px 16px', marginBottom: 16 }}>
        {title && <div style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 13, color: text, marginBottom: 12 }}>{title}</div>}
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: isDark ? '#1C1C28' : '#fff', border: `1px solid ${border}`, borderRadius: 8, fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  } catch { return null; }
}
