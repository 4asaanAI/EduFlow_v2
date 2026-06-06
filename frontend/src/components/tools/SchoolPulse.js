import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { executeTool } from '../../lib/api';
import { Activity, Users, IndianRupee, AlertTriangle, RefreshCw, CheckCircle } from 'lucide-react';

function StatCard({ value, label, color = 'var(--color-accent-blue)', sublabel }) {
  return (
    <div style={{
      background: 'var(--c-bg)',
      border: '1px solid var(--c-border)',
      borderRadius: 10,
      padding: '16px 18px',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color, fontFamily: 'Inter, sans-serif', lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--c-faint)', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>{label}</div>
      {sublabel && <div style={{ fontSize: 11, color: 'var(--c-muted)', marginTop: 2 }}>{sublabel}</div>}
    </div>
  );
}

function AlertItem({ type, text }) {
  const map = {
    warning: { icon: AlertTriangle, color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.25)' },
    critical: { icon: AlertTriangle, color: '#ef4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.25)' },
    success: { icon: CheckCircle, color: '#10b981', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.25)' },
    info: { icon: Activity, color: '#4f8ff7', bg: 'rgba(79,143,247,0.08)', border: 'rgba(79,143,247,0.25)' },
  };
  const s = map[type] || map.info;
  const Icon = s.icon;
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, background: s.bg, border: `1px solid ${s.border}`, borderRadius: 8, padding: '10px 14px' }}>
      <Icon size={14} color={s.color} style={{ marginTop: 1, flexShrink: 0 }} />
      <span style={{ fontSize: 12, color: 'var(--c-text)', lineHeight: 1.5 }}>{text}</span>
    </div>
  );
}

export default function SchoolPulse() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [threshold, setThreshold] = useState(85);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await executeTool('get_school_pulse', {}, currentUser);
      if (res.success) setData(res.data);
    } catch {}
    setLoading(false);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--c-faint)', gap: 10 }}>
        <RefreshCw size={20} style={{ animation: 'spin 0.8s linear infinite' }} />
        <span style={{ fontSize: 13 }}>Loading School Pulse...</span>
      </div>
    );
  }

  const summary = data?.summary || {};

  return (
    <>
      <style>{`
        @media (max-width: 640px) {
          .pulse-header { flex-direction: column !important; align-items: flex-start !important; gap: 10px !important; }
          .pulse-grid { grid-template-columns: 1fr !important; }
          .pulse-stats { grid-template-columns: repeat(2, 1fr) !important; }
          .pulse-inner-stats { grid-template-columns: repeat(2, 1fr) !important; }
          .pulse-actions { grid-template-columns: repeat(2, 1fr) !important; }
          .pulse-absent { flex-wrap: wrap !important; }
        }
        @media (max-width: 400px) {
          .pulse-stats { grid-template-columns: 1fr !important; }
        }
      `}</style>
      <div data-testid="school-pulse-tool" style={{ padding: '20px 16px', overflowY: 'auto', height: '100%', background: 'var(--c-app)', boxSizing: 'border-box' }}>
        {/* Header */}
        <div className="pulse-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, gap: 12 }}>
          <div>
            <h1 style={{ fontFamily: 'Inter, sans-serif', fontSize: 22, fontWeight: 700, color: 'var(--c-text)', margin: 0 }}>School Pulse</h1>
            <p style={{ color: 'var(--c-faint)', fontSize: 12, margin: '4px 0 0' }}>Live overview of your school's health</p>
          </div>
          <button
            data-testid="refresh-pulse-btn"
            onClick={loadData}
            style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '7px 14px', color: 'var(--c-muted)', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, boxShadow: 'var(--shadow-sm)' }}
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>

        {/* Top stats */}
        <div className="pulse-stats" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
          <StatCard value={summary.total_students || 0} label="Enrolled Students" color="var(--color-accent-blue)" />
          <StatCard value={summary.attendance_rate || 'N/A'} label="Today's Attendance" color="var(--color-success)" />
          <StatCard value={data?.fee_stats?.paid || '₹0'} label="Fees Collected" color="var(--color-accent-blue)" sublabel={data?.fee_stats?.collection_rate ? `${data.fee_stats.collection_rate} collected` : undefined} />
          <StatCard value={data?.fee_stats?.overdue || '₹0'} label="Overdue Fees" color="var(--color-danger)" />
        </div>

        <div className="pulse-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 1000 }}>

          {/* Quick Actions */}
          <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 12, padding: 20, boxShadow: 'var(--shadow-sm)' }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, color: 'var(--c-text)', marginBottom: 16, marginTop: 0 }}>Quick Actions</h3>
            <div className="pulse-actions" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                { icon: Users, label: "Mark Today's Attendance", color: '#4f8ff7' },
                { icon: IndianRupee, label: 'Send Fee Reminders', color: '#10b981' },
                { icon: AlertTriangle, label: 'View Active Alerts', color: '#ef4444' },
                { icon: Activity, label: 'Generate Daily Report', color: '#a78bfa' },
              ].map((action, i) => {
                const Icon = action.icon;
                return (
                  <button key={i} data-testid={`quick-action-${i}`} style={{
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                    background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 10,
                    padding: '14px 8px', cursor: 'pointer', color: 'var(--c-muted)', fontSize: 11, fontWeight: 500,
                    transition: 'all 0.15s', textAlign: 'center', lineHeight: 1.3,
                  }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.borderColor = action.color + '60'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'var(--c-deep)'; e.currentTarget.style.borderColor = 'var(--c-border)'; }}
                  >
                    <Icon size={20} color={action.color} />
                    <span>{action.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Attendance threshold slider */}
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--c-border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Alert Threshold</span>
                <span style={{ fontSize: 12, color: '#4f8ff7', fontWeight: 700 }}>{threshold}%</span>
              </div>
              <input
                type="range" min={50} max={100} value={threshold}
                onChange={e => setThreshold(Number(e.target.value))}
                data-testid="threshold-slider"
                style={{ width: '100%', accentColor: '#4f8ff7', cursor: 'pointer' }}
              />
              <button data-testid="save-settings-btn" style={{ width: '100%', marginTop: 12, background: '#4f8ff7', border: 'none', borderRadius: 8, padding: '10px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'opacity 0.15s' }}
                onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
                onMouseLeave={e => e.currentTarget.style.opacity = '1'}
              >
                Save Settings
              </button>
            </div>
          </div>

          {/* Today's Snapshot */}
          <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 12, padding: 20, boxShadow: 'var(--shadow-sm)' }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, color: 'var(--c-text)', marginBottom: 16, marginTop: 0 }}>Today's Snapshot</h3>
            <div className="pulse-inner-stats" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
              <StatCard value={summary.total_staff || 0} label="Total Staff" color="var(--c-text)" />
              <StatCard value={(data?.staff_absent_today?.length || 0)} label="Staff Absent" color="var(--color-danger)" />
              <StatCard value={(data?.pending_leave_requests?.length || 0)} label="Leave Requests" color="#fbbf24" />
              <StatCard value={(data?.chronic_absent_students?.length || 0)} label="Chronic Absences" color="var(--color-danger)" />
            </div>

            {/* Alerts */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(data?.staff_absent_today?.length || 0) > 0 && (
                <AlertItem type="warning" text={`${data.staff_absent_today.length} staff member${data.staff_absent_today.length !== 1 ? 's' : ''} absent today`} />
              )}
              {(data?.chronic_absent_students?.length || 0) > 0 && (
                <AlertItem type="warning" text={`${data.chronic_absent_students.length} students absent 3+ consecutive days`} />
              )}
              {summary.fee_collected && (
                <AlertItem type="success" text={`Fee collection: ${data?.fee_stats?.paid} collected this period`} />
              )}
              {(data?.pending_leave_requests?.length || 0) > 0 && (
                <AlertItem type="info" text={`${data.pending_leave_requests.length} leave request${data.pending_leave_requests.length !== 1 ? 's' : ''} awaiting approval`} />
              )}
              {!(data?.staff_absent_today?.length) && !(data?.chronic_absent_students?.length) && !(data?.pending_leave_requests?.length) && (
                <AlertItem type="success" text="All good — no active alerts today!" />
              )}
            </div>
          </div>
        </div>

        {/* Staff absent list */}
        {data?.staff_absent_today?.length > 0 && (
          <div style={{ marginTop: 16, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 12, padding: 20, maxWidth: 1000, boxShadow: 'var(--shadow-sm)' }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, color: 'var(--c-text)', marginBottom: 12, marginTop: 0 }}>Staff Absent Today</h3>
            <div className="pulse-absent" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {data.staff_absent_today.map((name, i) => (
                <span key={i} style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, padding: '4px 12px', fontSize: 12, color: '#ef4444', fontWeight: 500 }}>
                  {name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
