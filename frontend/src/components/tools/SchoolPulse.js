import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { executeTool } from '../../lib/api';
import { Activity, Users, IndianRupee, AlertTriangle, RefreshCw, CheckCircle } from 'lucide-react';

function StatCard({ value, label, color = '#3B82F6', sublabel }) {
  return (
    <div style={{
      background: '#161622', border: '1px solid #222230', borderRadius: 10, padding: '16px 18px',
    }}>
      <div style={{ fontSize: 24, fontWeight: 700, color, fontFamily: 'Outfit, sans-serif' }}>{value}</div>
      <div style={{ fontSize: 10, color: '#64748B', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>{label}</div>
      {sublabel && <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{sublabel}</div>}
    </div>
  );
}

function AlertItem({ type, text }) {
  const map = {
    warning: { icon: AlertTriangle, color: '#F59E0B', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)' },
    critical: { icon: AlertTriangle, color: '#EF4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.2)' },
    success: { icon: CheckCircle, color: '#10B981', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.2)' },
    info: { icon: Activity, color: '#3B82F6', bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.2)' },
  };
  const s = map[type] || map.info;
  const Icon = s.icon;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: s.bg, border: `1px solid ${s.border}`, borderRadius: 8, padding: '10px 14px' }}>
      <Icon size={14} color={s.color} />
      <span style={{ fontSize: 12, color: '#E2E8F0' }}>{text}</span>
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748B' }}>
        <RefreshCw size={20} style={{ animation: 'spin 0.8s linear infinite' }} />
        <span style={{ marginLeft: 10 }}>Loading School Pulse...</span>
      </div>
    );
  }

  const summary = data?.summary || {};

  return (
    <div data-testid="school-pulse-tool" style={{ padding: '24px', overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 22, fontWeight: 600, color: '#fff' }}>School pulse</h1>
        <button
          data-testid="refresh-pulse-btn"
          onClick={loadData}
          style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '7px 14px', color: '#94A3B8', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 1000 }}>

        {/* Quick Actions */}
        <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, color: '#E2E8F0', marginBottom: 16 }}>Quick Actions</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {[
              { icon: Users, label: "Mark Today's Attendance", color: '#3B82F6' },
              { icon: IndianRupee, label: 'Send Fee Reminders', color: '#10B981' },
              { icon: AlertTriangle, label: 'View Active Alerts', color: '#EF4444' },
              { icon: Activity, label: 'Generate Daily Report', color: '#8B5CF6' },
            ].map((action, i) => {
              const Icon = action.icon;
              return (
                <button key={i} data-testid={`quick-action-${i}`} style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                  background: 'transparent', border: '1px solid #222230', borderRadius: 10,
                  padding: '16px 8px', cursor: 'pointer', color: '#94A3B8', fontSize: 11, fontWeight: 500,
                  transition: 'all 0.15s',
                }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.borderColor = action.color + '50'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = '#222230'; }}
                >
                  <Icon size={20} color={action.color} />
                  <span style={{ textAlign: 'center', lineHeight: 1.3 }}>{action.label}</span>
                </button>
              );
            })}
          </div>

          {/* Attendance threshold slider */}
          <div style={{ marginTop: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>SET ATTENDANCE ALERT THRESHOLD</span>
              <span style={{ fontSize: 12, color: '#3B82F6', fontWeight: 600 }}>{threshold}%</span>
            </div>
            <input
              type="range" min={50} max={100} value={threshold}
              onChange={e => setThreshold(Number(e.target.value))}
              data-testid="threshold-slider"
              style={{ width: '100%', accentColor: '#3B82F6' }}
            />
          </div>
          <button data-testid="save-settings-btn" style={{ width: '100%', marginTop: 14, background: '#3B82F6', border: 'none', borderRadius: 8, padding: '10px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            Save Settings
          </button>
        </div>

        {/* Today's Snapshot */}
        <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, color: '#E2E8F0', marginBottom: 16 }}>Today's Snapshot</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
            <StatCard value={summary.attendance_rate || 'N/A'} label="ATTENDANCE" color="#10B981" />
            <StatCard value={summary.total_students || 0} label="ENROLLED" color="#E2E8F0" />
            <StatCard value={data?.fee_stats?.paid || '₹0'} label="FEES PAID" color="#3B82F6" />
            <StatCard value={data?.fee_stats?.overdue || '₹0'} label="OVERDUE" color="#EF4444" />
          </div>

          {/* Alerts */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(data?.staff_absent_today?.length || 0) > 0 && (
              <AlertItem type="warning" text={`${data.staff_absent_today.length} teachers absent today`} />
            )}
            {(data?.chronic_absent_students?.length || 0) > 0 && (
              <AlertItem type="warning" text={`${data.chronic_absent_students.length} students absent 3+ days`} />
            )}
            {summary.fee_collected && (
              <AlertItem type="success" text={`Fee collection: ${data?.fee_stats?.paid} collected`} />
            )}
            {(data?.pending_leave_requests?.length || 0) > 0 && (
              <AlertItem type="info" text={`${data.pending_leave_requests.length} leave requests pending`} />
            )}
          </div>
        </div>
      </div>

      {/* Staff absent list */}
      {data?.staff_absent_today?.length > 0 && (
        <div style={{ marginTop: 20, background: '#161622', border: '1px solid #222230', borderRadius: 12, padding: 20, maxWidth: 1000 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, color: '#E2E8F0', marginBottom: 12 }}>Staff Absent Today</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.staff_absent_today.map((name, i) => (
              <span key={i} style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, padding: '4px 10px', fontSize: 12, color: '#FCA5A5' }}>
                {name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
