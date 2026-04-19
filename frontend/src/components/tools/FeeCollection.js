import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { executeTool } from '../../lib/api';
import { IndianRupee, AlertTriangle, RefreshCw, TrendingUp } from 'lucide-react';

export default function FeeCollection() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await executeTool('get_fee_summary', {}, currentUser);
      if (res.success) setData(res.data);
    } catch {}
    setLoading(false);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--c-faint)' }}>
        <RefreshCw size={20} style={{ animation: 'spin 0.8s linear infinite' }} />
        <span style={{ marginLeft: 10 }}>Loading Fee Data...</span>
      </div>
    );
  }

  const stats = data?.stats || {};
  const defaulters = data?.defaulters || [];

  return (
    <div data-testid="fee-collection-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ fontFamily: 'Inter, sans-serif', fontSize: 22, fontWeight: 600, color: 'var(--c-text)' }}>Fee collection</h1>
        <button onClick={loadData} data-testid="refresh-fee-btn" style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '7px 14px', color: 'var(--c-muted)', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
          <RefreshCw size={12} />Refresh
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24, maxWidth: 900 }}>
        {[
          { value: stats.total_overdue || '₹0', label: 'TOTAL OVERDUE', color: '#f87171' },
          { value: stats.students_with_dues || 0, label: 'STUDENTS WITH DUES', color: '#fbbf24' },
          { value: stats.overdue_60_days || 0, label: 'OVERDUE 60+ DAYS', color: '#f87171' },
          { value: stats.collection_rate || '0%', label: 'COLLECTION RATE', color: '#34d399' },
        ].map((s, i) => (
          <div key={i} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: s.color, fontFamily: 'Inter, sans-serif' }}>{s.value}</div>
            <div style={{ fontSize: 9, color: 'var(--c-faint)', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Defaulters table */}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 12, overflow: 'hidden', maxWidth: 900 }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--c-border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={14} color="#f87171" />
          <span style={{ fontFamily: 'Inter, sans-serif', fontWeight: 600, fontSize: 13, color: 'var(--c-text)' }}>
            Fee Defaulters — Top {defaulters.length}
          </span>
        </div>
        {defaulters.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>
            No fee defaulters found ✓
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Student', 'Class', 'Overdue', 'Days'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {defaulters.map((d, i) => (
                <tr key={d.student_id || i} style={{ borderBottom: i < defaulters.length - 1 ? '1px solid #242424' : 'none' }}>
                  <td style={{ padding: '10px 16px', fontSize: 13, color: 'var(--c-text)', fontWeight: 500 }}>{d.student_name}</td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: 'var(--c-muted)' }}>{d.class}</td>
                  <td style={{ padding: '10px 16px', fontSize: 13, color: '#f87171', fontWeight: 600 }}>{d.amount_overdue_fmt}</td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: d.days_overdue > 60 ? '#f87171' : '#fbbf24' }}>
                    {d.days_overdue} days
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
