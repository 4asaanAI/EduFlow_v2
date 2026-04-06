import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { executeTool } from '../../lib/api';
import { updateLeave } from '../../lib/api';
import { Users, RefreshCw, CheckCircle, XCircle } from 'lucide-react';

const STATUS_COLOR = {
  present: '#10B981',
  absent: '#EF4444',
  late: '#F59E0B',
  on_leave: '#8B5CF6',
  not_marked: '#64748B',
};

export default function StaffTracker() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('attendance');

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await executeTool('get_staff_status', {}, currentUser);
      if (res.success) setData(res.data);
    } catch {}
    setLoading(false);
  };

  const handleLeave = async (leaveId, status) => {
    try {
      await updateLeave(leaveId, status, currentUser);
      loadData();
    } catch {}
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748B' }}>
        <RefreshCw size={20} style={{ animation: 'spin 0.8s linear infinite' }} />
        <span style={{ marginLeft: 10 }}>Loading Staff Data...</span>
      </div>
    );
  }

  const staffList = data?.staff_list || [];
  const pendingLeaves = data?.pending_leaves || [];

  return (
    <div data-testid="staff-tracker-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 22, fontWeight: 600, color: '#fff' }}>Staff tracker</h1>
        <button onClick={loadData} data-testid="refresh-staff-btn" style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '7px 14px', color: '#94A3B8', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
          <RefreshCw size={12} />Refresh
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24, maxWidth: 800 }}>
        {[
          { value: data?.total_staff || 0, label: 'TOTAL STAFF', color: '#E2E8F0' },
          { value: data?.present_today || 0, label: 'PRESENT TODAY', color: '#10B981' },
          { value: data?.absent_today || 0, label: 'ABSENT', color: '#EF4444' },
          { value: pendingLeaves.length, label: 'PENDING LEAVES', color: '#F59E0B' },
        ].map((s, i) => (
          <div key={i} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: s.color, fontFamily: 'Outfit, sans-serif' }}>{s.value}</div>
            <div style={{ fontSize: 9, color: '#64748B', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid #222230', paddingBottom: 0 }}>
        {['attendance', 'leaves'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} data-testid={`tab-${tab}`} style={{
            background: 'none', border: 'none', padding: '8px 16px',
            borderBottom: activeTab === tab ? '2px solid #3B82F6' : '2px solid transparent',
            color: activeTab === tab ? '#fff' : '#64748B',
            fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s', marginBottom: -1,
          }}>
            {tab === 'attendance' ? 'Today\'s Attendance' : `Pending Leaves (${pendingLeaves.length})`}
          </button>
        ))}
      </div>

      {activeTab === 'attendance' && (
        <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 12, overflow: 'hidden', maxWidth: 800 }}>
          {staffList.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: '#64748B', fontSize: 13 }}>No staff records found</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Name', 'Type', 'Status'].map(h => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', background: '#0F0F1A', borderBottom: '1px solid #222230' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {staffList.map((s, i) => (
                  <tr key={s.id || i} style={{ borderBottom: i < staffList.length - 1 ? '1px solid #1A1A24' : 'none' }}>
                    <td style={{ padding: '10px 16px', fontSize: 13, color: '#E2E8F0', fontWeight: 500 }}>{s.name}</td>
                    <td style={{ padding: '10px 16px', fontSize: 12, color: '#94A3B8' }}>{s.staff_type}</td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 5,
                        color: STATUS_COLOR[s.status] || '#64748B',
                        background: `${STATUS_COLOR[s.status] || '#64748B'}15`,
                        textTransform: 'capitalize',
                      }}>{s.status.replace('_', ' ')}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'leaves' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 800 }}>
          {pendingLeaves.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: '#64748B', fontSize: 13, background: '#161622', border: '1px solid #222230', borderRadius: 12 }}>
              No pending leave requests ✓
            </div>
          ) : (
            pendingLeaves.map((lr, i) => (
              <div key={lr.id || i} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 10, padding: '14px 18px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                  <div>
                    <div style={{ fontWeight: 600, color: '#E2E8F0', fontSize: 14 }}>{lr.staff_name}</div>
                    <div style={{ color: '#64748B', fontSize: 12, marginTop: 2 }}>
                      {lr.leave_type} · {lr.start_date} to {lr.end_date}
                    </div>
                    <div style={{ color: '#94A3B8', fontSize: 12, marginTop: 4, fontStyle: 'italic' }}>{lr.reason}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                    <button data-testid={`approve-leave-${lr.id}`} onClick={() => handleLeave(lr.id, 'approved')} style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 7, padding: '6px 12px', color: '#10B981', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>
                      <CheckCircle size={12} />Approve
                    </button>
                    <button data-testid={`reject-leave-${lr.id}`} onClick={() => handleLeave(lr.id, 'rejected')} style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 7, padding: '6px 12px', color: '#EF4444', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>
                      <XCircle size={12} />Reject
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
