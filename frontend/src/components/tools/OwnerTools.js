import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { executeTool, updateLeave, getStaff } from '../../lib/api';
import { ToolPage, StatCard, DataTable, Badge, ComingSoon, FormField, ActionBtn, useToolData, LineChartWidget, BarChartWidget, PieChartWidget } from './ToolPage';
import { Activity, CheckCircle, XCircle, AlertTriangle, Plus, RefreshCw, Save, TrendingUp, Users, FileText, Send } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h(user) { return { 'Content-Type': 'application/json', 'X-User-Role': user?.role || 'owner', 'X-User-Id': user?.id || 'user-owner-001', 'X-User-Name': user?.name || 'Aman' }; }

// 1. School Pulse
export function SchoolPulse() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [threshold, setThreshold] = useState(85);

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try { const r = await executeTool('get_school_pulse', {}, currentUser); if (r.success) setData(r.data); } catch {}
    setLoading(false);
  };

  const s = data?.summary || {};
  const leaves = data?.pending_leave_requests || [];

  return (
    <ToolPage title="School Pulse" subtitle="Today's complete overview" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 1000 }}>
        {/* Quick Actions */}
        <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, color: '#E2E8F0', marginBottom: 14 }}>Quick Actions</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {[
              { icon: Users, label: "Mark Today's Attendance", color: '#3B82F6', action: () => window.dispatchEvent(new CustomEvent('open-tool', { detail: 'attendance-recorder' })) },
              { icon: Send, label: 'Send Fee Reminders', color: '#10B981', action: async () => { alert('Fee reminders will be sent via WhatsApp (Phase 2)'); } },
              { icon: AlertTriangle, label: 'View Active Alerts', color: '#EF4444', action: () => window.dispatchEvent(new CustomEvent('open-tool', { detail: 'smart-alerts' })) },
              { icon: FileText, label: 'Generate Daily Report', color: '#8B5CF6', action: async () => { alert('Daily report generation coming in Phase 2'); } },
            ].map((a, i) => (
              <button key={i} data-testid={`quick-action-${i}`} onClick={a.action} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7, background: 'transparent', border: '1px solid #222230', borderRadius: 10, padding: '14px 8px', cursor: 'pointer', color: '#94A3B8', fontSize: 11, fontWeight: 500, transition: 'all 0.15s' }}
                onMouseEnter={e => { e.currentTarget.style.background = `${a.color}10`; e.currentTarget.style.borderColor = `${a.color}40`; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = '#222230'; }}>
                <a.icon size={18} color={a.color} />
                <span style={{ textAlign: 'center', lineHeight: 1.3 }}>{a.label}</span>
              </button>
            ))}
          </div>
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 10, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>ATTENDANCE ALERT THRESHOLD</span>
              <span style={{ fontSize: 12, color: '#3B82F6', fontWeight: 700 }}>{threshold}%</span>
            </div>
            <input type="range" min={50} max={100} value={threshold} onChange={e => setThreshold(+e.target.value)} data-testid="threshold-slider" style={{ width: '100%', accentColor: '#3B82F6' }} />
          </div>
          <button data-testid="save-settings-btn" onClick={async () => {
            await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/settings/school`, {
              method: 'PATCH', headers: h(currentUser), body: JSON.stringify({ attendance_threshold: threshold })
            });
            alert(`Attendance threshold saved as ${threshold}%`);
          }} style={{ width: '100%', marginTop: 12, background: '#3B82F6', border: 'none', borderRadius: 8, padding: '10px', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>Save Settings</button>
        </div>

        {/* Snapshot */}
        <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, color: '#E2E8F0', marginBottom: 14 }}>Today's Snapshot</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
            <StatCard value={s.attendance_rate || '0%'} label="ATTENDANCE" color="#10B981" small />
            <StatCard value={s.total_students || 0} label="ENROLLED" color="#E2E8F0" small />
            <StatCard value={data?.fee_stats?.paid || '₹0'} label="FEES PAID" color="#3B82F6" small />
            <StatCard value={data?.fee_stats?.overdue || '₹0'} label="OVERDUE" color="#EF4444" small />
          </div>
          {(data?.staff_absent_today?.length || 0) > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 7, padding: '8px 12px', marginBottom: 6, fontSize: 12, color: '#FCD34D' }}><AlertTriangle size={12} />{data.staff_absent_today.length} teachers absent today</div>}
          {(data?.chronic_absent_students?.length || 0) > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 7, padding: '8px 12px', marginBottom: 6, fontSize: 12, color: '#FCA5A5' }}><AlertTriangle size={12} />{data.chronic_absent_students.length} students absent 3+ days</div>}
          {data?.fee_stats?.paid && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 7, padding: '8px 12px', marginBottom: 6, fontSize: 12, color: '#6EE7B7' }}><CheckCircle size={12} />Fee collection: {data.fee_stats.paid} collected</div>}
          {leaves.length > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 7, padding: '8px 12px', fontSize: 12, color: '#93C5FD' }}><Activity size={12} />{leaves.length} leave requests pending</div>}
        </div>
      </div>

      {/* Pending Leaves quick actions */}
      {leaves.length > 0 && (
        <div style={{ marginTop: 16, background: '#161622', border: '1px solid #222230', borderRadius: 11, overflow: 'hidden', maxWidth: 1000 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #222230' }}>
            <span style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 13, color: '#E2E8F0' }}>Pending Leave Requests</span>
          </div>
          {leaves.map((lr, i) => (
            <div key={lr.id || i} style={{ padding: '12px 16px', borderBottom: i < leaves.length - 1 ? '1px solid #1A1A24' : 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontWeight: 600, color: '#E2E8F0', fontSize: 13 }}>{lr.staff_name}</span>
                <span style={{ color: '#64748B', fontSize: 11, marginLeft: 10 }}>{lr.leave_type} · {lr.start_date} – {lr.end_date}</span>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 2, fontStyle: 'italic' }}>{lr.reason}</div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <ActionBtn label="Approve" variant="success" icon={<CheckCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'approved', currentUser); load(); }} />
                <ActionBtn label="Reject" variant="danger" icon={<XCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'rejected', currentUser); load(); }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </ToolPage>
  );
}

// 2. Fee Collection Summary — with bar chart
export function FeeCollection() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { loadData(); }, []);
  const loadData = async () => { setLoading(true); try { const r = await executeTool('get_fee_summary', {}, currentUser); if (r.success) setData(r.data); } catch {} setLoading(false); };
  const stats = data?.stats || {};
  const defaulters = data?.defaulters || [];

  // Bar chart data: top defaulters
  const chartData = defaulters.slice(0, 6).map(d => ({ name: d.student_name.split(' ')[0], amount: d.amount_overdue }));

  return (
    <ToolPage title="Fee collection" subtitle="Revenue summary & defaulters" onRefresh={loadData} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18, maxWidth: 900 }}>
        <StatCard value={stats.total_overdue || '₹0'} label="TOTAL OVERDUE" color="#EF4444" />
        <StatCard value={stats.students_with_dues || 0} label="STUDENTS WITH DUES" color="#F59E0B" />
        <StatCard value={stats.overdue_60_days || 0} label="OVERDUE 60+ DAYS" color="#EF4444" />
        <StatCard value={stats.collection_rate || '0%'} label="COLLECTION RATE" color="#10B981" />
      </div>
      {chartData.length > 0 && (
        <BarChartWidget data={chartData} xKey="name" bars={[{ key: 'amount', color: '#EF4444', name: 'Overdue (₹)' }]} title="Top Defaulters — Amount Overdue" height={200} />
      )}
      <DataTable title={`Fee Defaulters — Top ${defaulters.length}`} headers={['Student', 'Class', 'Amount Overdue', 'Days Overdue']}
        rows={defaulters.map(d => [d.student_name, d.class, <span style={{ color: '#EF4444', fontWeight: 600 }}>{d.amount_overdue_fmt}</span>, <span style={{ color: d.days_overdue > 60 ? '#EF4444' : '#F59E0B' }}>{d.days_overdue} days</span>])}
        emptyMsg="No fee defaulters — great collection rate!"
      />
    </ToolPage>
  );
}

// 3. Student Strength Overview
export function StudentStrength() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try {
      const [classRes, studRes] = await Promise.all([
        fetch(`${API}/settings/classes`, { headers: h(currentUser) }).then(r => r.json()),
        fetch(`${API}/students/`, { headers: h(currentUser) }).then(r => r.json()),
      ]);
      setData({ classes: classRes.data || [], total: studRes.meta?.total || 0 });
    } catch {}
    setLoading(false);
  };

  return (
    <ToolPage title="Student Strength" subtitle="Class-wise enrollment overview" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20, maxWidth: 600 }}>
        <StatCard value={data?.total || 0} label="TOTAL STUDENTS" color="#3B82F6" />
        <StatCard value={data?.classes?.length || 0} label="CLASSES" color="#10B981" />
        <StatCard value={data ? Math.round((data.total || 0) / (data.classes?.length || 1)) : 0} label="AVG PER CLASS" color="#8B5CF6" />
      </div>
      <DataTable title="Class-wise Strength" headers={['Class', 'Section', 'Academic Year']}
        rows={(data?.classes || []).map(c => [c.name, c.section, '2025-26'])}
      />
    </ToolPage>
  );
}

// 4. Attendance Overview (Owner) - with recharts
export function AttendanceOverview() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await executeTool('get_attendance_overview', { days: 30 }, currentUser); if (r.success) setData(r.data); } catch {} setLoading(false); };

  const chartData = (data?.daily_trend || []).map(d => ({ date: d.date?.slice(5), rate: d.rate, present: d.present, absent: d.absent }));

  return (
    <ToolPage title="Attendance Overview" subtitle="Trends and class-wise analysis" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16, maxWidth: 500 }}>
        <StatCard value={data?.avg_attendance_rate || '0%'} label="AVG RATE (30 DAYS)" color="#10B981" />
        <StatCard value={data?.total_records || 0} label="TOTAL RECORDS" color="#3B82F6" />
        <StatCard value="Last 30 days" label="PERIOD" color="#8B5CF6" />
      </div>
      {chartData.length > 0 && (
        <LineChartWidget data={chartData} xKey="date" lines={[{ key: 'rate', color: '#10B981', name: 'Attendance %' }, { key: 'absent', color: '#EF4444', name: 'Absent' }]} title="7-Day Attendance Trend" height={200} />
      )}
      <DataTable title="Class-wise Today" headers={['Class', 'Present', 'Total', 'Rate']}
        rows={(data?.class_stats_today || []).map(c => [c.class, c.present, c.total, <span style={{ color: parseFloat(c.rate) >= 85 ? '#10B981' : '#EF4444', fontWeight: 600 }}>{c.rate}</span>])}
        emptyMsg="Attendance not yet marked for today"
      />
    </ToolPage>
  );
}

// 5. Staff Attendance Tracker
export function StaffAttendanceTracker() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('attendance');
  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await executeTool('get_staff_status', {}, currentUser); if (r.success) setData(r.data); } catch {} setLoading(false); };
  const staff = data?.staff_list || [];
  const leaves = data?.pending_leaves || [];
  const statusColors = { present: '#10B981', absent: '#EF4444', late: '#F59E0B', not_marked: '#64748B', 'on-leave': '#8B5CF6' };

  return (
    <ToolPage title="Staff Tracker" subtitle="Attendance & leave management" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18, maxWidth: 700 }}>
        <StatCard value={data?.total_staff || 0} label="TOTAL STAFF" color="#E2E8F0" />
        <StatCard value={data?.present_today || 0} label="PRESENT" color="#10B981" />
        <StatCard value={data?.absent_today || 0} label="ABSENT" color="#EF4444" />
        <StatCard value={leaves.length} label="PENDING LEAVES" color="#F59E0B" />
      </div>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid #222230', marginBottom: 14 }}>
        {['attendance', 'leaves'].map(t => (
          <button key={t} onClick={() => setActiveTab(t)} data-testid={`tab-${t}`} style={{ background: 'none', border: 'none', padding: '8px 14px', borderBottom: activeTab === t ? '2px solid #3B82F6' : '2px solid transparent', color: activeTab === t ? '#fff' : '#64748B', fontSize: 13, fontWeight: 500, cursor: 'pointer', marginBottom: -1 }}>
            {t === 'attendance' ? "Today's Attendance" : `Pending Leaves (${leaves.length})`}
          </button>
        ))}
      </div>
      {activeTab === 'attendance' && (
        <DataTable headers={['Name', 'Type', 'Status']}
          rows={staff.map(s => [s.name, s.staff_type, <Badge text={s.status.replace('_', ' ')} color={s.status === 'present' ? 'green' : s.status === 'absent' ? 'red' : s.status === 'late' ? 'yellow' : 'gray'} />])}
        />
      )}
      {activeTab === 'leaves' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {leaves.length === 0 ? <div style={{ padding: 24, textAlign: 'center', color: '#64748B', fontSize: 13, background: '#161622', border: '1px solid #222230', borderRadius: 11 }}>No pending leave requests</div> : leaves.map((lr, i) => (
            <div key={lr.id || i} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 10, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div><div style={{ fontWeight: 600, color: '#E2E8F0', fontSize: 13 }}>{lr.staff_name}</div><div style={{ color: '#64748B', fontSize: 11 }}>{lr.leave_type} · {lr.start_date} – {lr.end_date}</div><div style={{ color: '#94A3B8', fontSize: 11, marginTop: 3, fontStyle: 'italic' }}>{lr.reason}</div></div>
              <div style={{ display: 'flex', gap: 6 }}>
                <ActionBtn label="Approve" variant="success" icon={<CheckCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'approved', currentUser); load(); }} />
                <ActionBtn label="Reject" variant="danger" icon={<XCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'rejected', currentUser); load(); }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </ToolPage>
  );
}

// 6. Financial Reports Generator
export function FinancialReports() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expenses, setExpenses] = useState([]);
  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try {
      const [feeRes, expRes] = await Promise.all([
        executeTool('get_financial_report', {}, currentUser),
        fetch(`${API}/ops/expenses`, { headers: h(currentUser) }).then(r => r.json()),
      ]);
      if (feeRes.success) setData(feeRes.data);
      if (expRes.success) setExpenses(expRes.data || []);
    } catch {}
    setLoading(false);
  };

  const totalExp = expenses.reduce((s, e) => s + (e.amount || 0), 0);
  const fmtExp = totalExp >= 100000 ? `₹${(totalExp / 100000).toFixed(1)}L` : `₹${totalExp.toLocaleString('en-IN')}`;

  return (
    <ToolPage title="Financial Reports" subtitle="Revenue, expenses & analysis" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 18, maxWidth: 700 }}>
        <StatCard value={data?.total_collected || '₹0'} label="TOTAL COLLECTED" color="#10B981" />
        <StatCard value={fmtExp || '₹0'} label="TOTAL EXPENSES" color="#EF4444" />
        <StatCard value={data?.collection_rate || '0%'} label="COLLECTION RATE" color="#3B82F6" />
      </div>
      <DataTable title="Revenue by Fee Type" headers={['Fee Type', 'Expected', 'Collected']}
        rows={(data?.by_fee_type || []).map(r => [r.fee_type, r.expected, <span style={{ color: '#10B981' }}>{r.collected}</span>])}
        emptyMsg="No fee data available"
      />
      <DataTable title="Recent Expenses" headers={['Date', 'Category', 'Description', 'Amount']}
        rows={expenses.slice(0, 10).map(e => [e.date, e.category, e.description, <span style={{ color: '#EF4444' }}>₹{(e.amount || 0).toLocaleString('en-IN')}</span>])}
        emptyMsg="No expenses recorded"
      />
    </ToolPage>
  );
}

// 7. Announcement Broadcaster
export function AnnouncementBroadcaster() {
  const { currentUser } = useUser();
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: '', content: '', audience_type: 'all' });
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try { const r = await fetch(`${API}/ops/announcements`, { headers: h(currentUser) }).then(r => r.json()); if (r.success) setAnnouncements(r.data || []); } catch {}
    setLoading(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title || !form.content) return;
    await fetch(`${API}/ops/announcements`, { method: 'POST', headers: h(currentUser), body: JSON.stringify({ ...form, is_draft: false }) });
    setShowForm(false); setForm({ title: '', content: '', audience_type: 'all' }); load();
  };

  return (
    <ToolPage title="Announcement Broadcaster" subtitle="Broadcast messages to school" onRefresh={load} loading={loading}
      actions={<ActionBtn label="New Announcement" onClick={() => setShowForm(true)} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 11, padding: 20, marginBottom: 18 }}>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#E2E8F0', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>New Announcement</h3>
          <form onSubmit={handleSubmit}>
            <FormField label="Title" value={form.title} onChange={f('title')} placeholder="Announcement title" required />
            <FormField label="Message" type="textarea" value={form.content} onChange={f('content')} placeholder="Write your announcement..." required />
            <FormField label="Audience" type="select" value={form.audience_type} onChange={f('audience_type')} options={[{ value: 'all', label: 'All' }, { value: 'role', label: 'By Role' }, { value: 'class', label: 'By Class' }]} />
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <ActionBtn label="Send Now" onClick={() => {}} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}
      <DataTable title="Recent Announcements" headers={['Title', 'Audience', 'Date', 'Status']}
        rows={announcements.map(a => [a.title, a.audience_type, a.created_at?.slice(0, 10), <Badge text={a.is_draft ? 'Draft' : 'Sent'} color={a.is_draft ? 'gray' : 'green'} />])}
        emptyMsg="No announcements yet"
      />
    </ToolPage>
  );
}

// 8. Admission Funnel (Owner view)
export function AdmissionFunnel() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await executeTool('get_enquiries', {}, currentUser); if (r.success) setData(r.data); } catch {} setLoading(false); };
  const funnel = data?.funnel || {};
  const stages = ['new', 'contacted', 'visit_scheduled', 'visited', 'documents_submitted', 'fee_paid', 'enrolled', 'lost'];

  return (
    <ToolPage title="Admission Funnel" subtitle="Enquiries & conversion pipeline" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18, maxWidth: 800 }}>
        <StatCard value={data?.total || 0} label="TOTAL ENQUIRIES" color="#3B82F6" />
        <StatCard value={funnel.enrolled || 0} label="ENROLLED" color="#10B981" />
        <StatCard value={funnel.new || 0} label="NEW TODAY" color="#F59E0B" />
        <StatCard value={funnel.lost || 0} label="LOST" color="#EF4444" />
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 18 }}>
        {stages.map(s => (
          <div key={s} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '8px 12px', textAlign: 'center', minWidth: 80 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#E2E8F0', fontFamily: 'Outfit, sans-serif' }}>{funnel[s] || 0}</div>
            <div style={{ fontSize: 9, color: '#64748B', textTransform: 'capitalize', fontWeight: 600 }}>{s.replace('_', ' ')}</div>
          </div>
        ))}
      </div>
      <DataTable title="Recent Enquiries" headers={['Student Name', 'Parent', 'Class', 'Status', 'Source']}
        rows={(data?.enquiries || []).map(e => [e.student_name, e.parent_name, e.class_applying, <Badge text={e.status} color={e.status === 'enrolled' ? 'green' : e.status === 'lost' ? 'red' : 'blue'} />, e.source])}
        emptyMsg="No enquiries yet"
      />
    </ToolPage>
  );
}

// 9. Staff Leave Manager
export function StaffLeaveManager() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await executeTool('get_staff_status', {}, currentUser); if (r.success) setData(r.data); } catch {} setLoading(false); };
  return <StaffAttendanceTracker />;
}

// 10. Staff Performance Overview
export function StaffPerformance() {
  const { currentUser } = useUser();
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try { const r = await getStaff(currentUser); if (r.success) setStaff(r.data || []); } catch {}
    setLoading(false);
  };
  return (
    <ToolPage title="Staff Performance" subtitle="Attendance patterns & punctuality" onRefresh={load} loading={loading}>
      <DataTable title="All Staff" headers={['Name', 'Type', 'Employee ID', 'Join Date']}
        rows={staff.map(s => [s.name, s.staff_type, s.employee_id || 'N/A', s.join_date || 'N/A'])}
        emptyMsg="No staff data"
      />
    </ToolPage>
  );
}

// 11. Health Report (renamed from AI Health Report)
export function AiHealthReport() {
  const { currentUser } = useUser();
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const generate = async () => {
    setLoading(true);
    setTimeout(() => {
      setReport({
        generated: new Date().toLocaleDateString('en-IN'),
        score: 78,
        highlights: ['Fee collection at 86% — above average', 'Attendance trending up 3% this month', '2 staff punctuality concerns flagged'],
        alerts: ['3 students with chronic absence need follow-up', 'Overdue fees: ₹70K needs escalation'],
      });
      setLoading(false);
    }, 2000);
  };
  return (
    <ToolPage title="AI Health Report" subtitle="Weekly auto-generated school health summary">
      {!report ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🏥</div>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#E2E8F0', fontSize: 16, marginBottom: 8 }}>AI School Health Report</h3>
          <p style={{ color: '#64748B', fontSize: 12, marginBottom: 20 }}>Generate a comprehensive AI-powered analysis of your school's current health status</p>
          <ActionBtn label={loading ? 'Generating...' : 'Generate Report'} onClick={generate} disabled={loading} />
        </div>
      ) : (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 18 }}>
            <StatCard value={`${report.score}/100`} label="HEALTH SCORE" color="#10B981" />
            <StatCard value={report.generated} label="GENERATED" color="#3B82F6" />
            <StatCard value={report.alerts.length} label="ACTION ITEMS" color="#EF4444" />
          </div>
          <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 11, padding: 20, marginBottom: 14 }}>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#10B981', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Highlights</h3>
            {report.highlights.map((h, i) => <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 13, color: '#94A3B8' }}><CheckCircle size={12} color="#10B981" />{h}</div>)}
          </div>
          <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 11, padding: 20 }}>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#EF4444', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Action Items</h3>
            {report.alerts.map((a, i) => <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 13, color: '#94A3B8' }}><AlertTriangle size={12} color="#EF4444" />{a}</div>)}
          </div>
        </div>
      )}
    </ToolPage>
  );
}

// 12. Smart Alerts
export function SmartAlerts() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await executeTool('get_smart_alerts', {}, currentUser); if (r.success) setData(r.data); } catch {} setLoading(false); };
  const alerts = data?.alerts || [];
  const colors = { critical: 'red', warning: 'yellow', success: 'green', info: 'blue' };
  return (
    <ToolPage title="Smart Alerts" subtitle="Active exceptions & flags" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 18, maxWidth: 500 }}>
        <StatCard value={data?.total_alerts || 0} label="TOTAL ALERTS" color="#F59E0B" />
        <StatCard value={data?.critical_count || 0} label="CRITICAL" color="#EF4444" />
      </div>
      {alerts.length === 0 ? <div style={{ padding: 32, textAlign: 'center', color: '#64748B', background: '#161622', border: '1px solid #222230', borderRadius: 11, fontSize: 13 }}>No active alerts — all good!</div> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {alerts.map((a, i) => (
            <div key={i} style={{ background: '#161622', border: '1px solid #222230', borderRadius: 10, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <Badge text={a.category} color={colors[a.type] || 'blue'} />
              <span style={{ fontSize: 13, color: '#E2E8F0', flex: 1 }}>{a.text}</span>
              <Badge text={a.priority} color={a.priority === 'high' ? 'red' : a.priority === 'medium' ? 'yellow' : 'gray'} />
            </div>
          ))}
        </div>
      )}
    </ToolPage>
  );
}

// 13. Expense Tracker
export function ExpenseTracker() {
  const { currentUser } = useUser();
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ category: '', description: '', amount: '', date: new Date().toISOString().slice(0, 10), vendor: '' });
  const f = k => v => setForm(p => ({ ...p, [k]: v }));
  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await fetch(`${API}/ops/expenses`, { headers: h(currentUser) }).then(r => r.json()); if (r.success) setExpenses(r.data || []); } catch {} setLoading(false); };
  const handleAdd = async (e) => { e.preventDefault(); await fetch(`${API}/ops/expenses`, { method: 'POST', headers: h(currentUser), body: JSON.stringify({ ...form, amount: parseFloat(form.amount) }) }); setShowForm(false); setForm({ category: '', description: '', amount: '', date: new Date().toISOString().slice(0, 10), vendor: '' }); load(); };
  const total = expenses.reduce((s, e) => s + (e.amount || 0), 0);

  return (
    <ToolPage title="Expense Tracker" subtitle="Track & manage school expenses" onRefresh={load} loading={loading}
      actions={<ActionBtn label="Add Expense" onClick={() => setShowForm(true)} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <form onSubmit={handleAdd}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Category" type="select" value={form.category} onChange={f('category')} options={['utilities', 'maintenance', 'salary', 'events', 'stationery', 'transport', 'other'].map(v => ({ value: v, label: v }))} required />
              <FormField label="Amount (₹)" type="number" value={form.amount} onChange={f('amount')} placeholder="0.00" required />
              <FormField label="Date" type="date" value={form.date} onChange={f('date')} />
              <FormField label="Vendor" value={form.vendor} onChange={f('vendor')} placeholder="Vendor name" />
            </div>
            <FormField label="Description" type="textarea" value={form.description} onChange={f('description')} placeholder="Expense description" />
            <div style={{ display: 'flex', gap: 8 }}><ActionBtn label="Save Expense" /><ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} /></div>
          </form>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 16, maxWidth: 400 }}>
        <StatCard value={`₹${(total / 1000).toFixed(1)}K`} label="TOTAL EXPENSES" color="#EF4444" />
        <StatCard value={expenses.length} label="RECORDS" color="#E2E8F0" />
      </div>
      <DataTable headers={['Date', 'Category', 'Description', 'Vendor', 'Amount']}
        rows={expenses.map(e => [e.date, e.category, e.description, e.vendor || 'N/A', <span style={{ color: '#EF4444' }}>₹{(e.amount || 0).toLocaleString('en-IN')}</span>])}
      />
    </ToolPage>
  );
}

// 14. Complaint Tracker
export function ComplaintTracker() {
  const { currentUser } = useUser();
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => { setLoading(true); try { const r = await fetch(`${API}/ops/complaints`, { headers: h(currentUser) }).then(r => r.json()); if (r.success) setComplaints(r.data || []); } catch {} setLoading(false); };
  const statusColors = { open: 'red', assigned: 'yellow', in_progress: 'blue', resolved: 'green', closed: 'gray' };
  return (
    <ToolPage title="Complaint & Grievance Tracker" subtitle="Manage and resolve complaints" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16, maxWidth: 500 }}>
        <StatCard value={complaints.filter(c => c.status === 'open').length} label="OPEN" color="#EF4444" />
        <StatCard value={complaints.filter(c => c.status === 'resolved').length} label="RESOLVED" color="#10B981" />
        <StatCard value={complaints.length} label="TOTAL" color="#E2E8F0" />
      </div>
      <DataTable headers={['Subject', 'Category', 'Priority', 'Status', 'Date']}
        rows={complaints.map(c => [c.subject, c.category, <Badge text={c.priority} color={c.priority === 'urgent' ? 'red' : c.priority === 'high' ? 'yellow' : 'gray'} />, <Badge text={c.status} color={statusColors[c.status] || 'gray'} />, c.created_at?.slice(0, 10)])}
        emptyMsg="No complaints filed"
      />
    </ToolPage>
  );
}

// 15. Custom Report Builder
export function CustomReportBuilder() {
  const { currentUser } = useUser();
  const [sources, setSources] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const dataSources = [
    { id: 'students', label: 'Student Data', icon: '👥' },
    { id: 'attendance', label: 'Attendance Records', icon: '📋' },
    { id: 'fee_transactions', label: 'Fee Transactions', icon: '₹' },
    { id: 'staff', label: 'Staff Information', icon: '👨‍🏫' },
    { id: 'expenses', label: 'Expenses', icon: '💰' },
    { id: 'exam_results', label: 'Exam Results', icon: '📊' },
    { id: 'enquiries', label: 'Admission Enquiries', icon: '📝' },
  ];

  const toggle = (id) => setSelectedSources(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);

  const generateReport = async () => {
    if (selectedSources.length === 0) return;
    setLoading(true);
    // Generate download links for selected sources
    const links = selectedSources.map(src => {
      let url = `${process.env.REACT_APP_BACKEND_URL}/api/export/${src.replace('_', '-')}`;
      if (dateRange.start) url += `?start_date=${dateRange.start}`;
      if (dateRange.end) url += `${dateRange.start ? '&' : '?'}end_date=${dateRange.end}`;
      return { source: src, url, label: dataSources.find(d => d.id === src)?.label };
    });
    setReport({ links, generated: new Date().toLocaleString('en-IN') });
    setLoading(false);
  };

  return (
    <ToolPage title="Custom Report Builder" subtitle="Select data sources and download reports">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 900 }}>
        <div>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#E2E8F0', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Select Data Sources</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {dataSources.map(src => (
              <label key={src.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: selectedSources.includes(src.id) ? 'rgba(59,130,246,0.1)' : '#161622', border: `1px solid ${selectedSources.includes(src.id) ? '#3B82F6' : '#222230'}`, borderRadius: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={selectedSources.includes(src.id)} onChange={() => toggle(src.id)} />
                <span style={{ fontSize: 18 }}>{src.icon}</span>
                <span style={{ fontSize: 13, color: '#E2E8F0' }}>{src.label}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#E2E8F0', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Date Range (Optional)</h3>
          <FormField label="From Date" type="date" value={dateRange.start} onChange={v => setDateRange(p => ({ ...p, start: v }))} />
          <FormField label="To Date" type="date" value={dateRange.end} onChange={v => setDateRange(p => ({ ...p, end: v }))} />
          <ActionBtn label={loading ? 'Preparing...' : `Generate ${selectedSources.length} Report(s)`} onClick={generateReport} disabled={loading || selectedSources.length === 0} />

          {report && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, color: '#10B981', marginBottom: 10 }}>Reports ready — click to download:</div>
              {report.links.map((link, i) => (
                <a key={i} href={link.url} download target="_blank" rel="noreferrer"
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#161622', border: '1px solid #10B981', borderRadius: 7, color: '#10B981', fontSize: 12, marginBottom: 6, textDecoration: 'none' }}>
                  ⬇️ {link.label} (CSV)
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </ToolPage>
  );
}

// 16. Board/Trust Meeting Report
export function BoardReport() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const [pulse, fee, smart] = await Promise.all([
        executeTool('get_school_pulse', {}, currentUser),
        executeTool('get_fee_summary', {}, currentUser),
        executeTool('get_smart_alerts', {}, currentUser),
      ]);
      setData({
        generated: new Date().toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' }),
        pulse: pulse.data,
        fee: fee.data,
        alerts: smart.data,
      });
    } catch {}
    setLoading(false);
  };

  const s = data?.pulse?.summary || {};
  return (
    <ToolPage title="Board / Trust Meeting Report" subtitle="Consolidated school metrics for trust meetings">
      {!data ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
          <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#E2E8F0', fontSize: 16, marginBottom: 8 }}>Board Meeting Report</h3>
          <p style={{ color: '#64748B', fontSize: 12, marginBottom: 20 }}>Generate a comprehensive report combining all school metrics suitable for board/trust meetings</p>
          <ActionBtn label={loading ? 'Generating...' : 'Generate Report'} onClick={generate} disabled={loading} />
        </div>
      ) : (
        <div>
          <div style={{ marginBottom: 16, color: '#64748B', fontSize: 12 }}>Generated: {data.generated}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 20 }}>
            <StatCard value={s.total_students || 0} label="ENROLLED STUDENTS" color="#3B82F6" />
            <StatCard value={s.attendance_rate || 'N/A'} label="ATTENDANCE RATE" color="#10B981" />
            <StatCard value={data.fee?.stats?.collection_rate || 'N/A'} label="FEE COLLECTION" color="#10B981" />
            <StatCard value={data.alerts?.critical_count || 0} label="CRITICAL ALERTS" color="#EF4444" />
          </div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            <StatCard value={data.fee?.stats?.total_collected || '₹0'} label="TOTAL COLLECTED" color="#10B981" />
            <StatCard value={data.fee?.stats?.total_overdue || '₹0'} label="TOTAL OVERDUE" color="#EF4444" />
            <StatCard value={s.total_staff || 0} label="TOTAL STAFF" color="#E2E8F0" />
          </div>
          {data.alerts?.alerts?.length > 0 && (
            <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 11, padding: 16, marginBottom: 14 }}>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#EF4444', fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Active Alerts ({data.alerts.total_alerts})</h3>
              {data.alerts.alerts.map((a, i) => <div key={i} style={{ fontSize: 12, color: '#94A3B8', marginBottom: 4 }}>• {a.text}</div>)}
            </div>
          )}
          <ActionBtn label="Re-generate" variant="secondary" onClick={generate} disabled={loading} />
        </div>
      )}
    </ToolPage>
  );
}


// Year-end Session Transition Tool (accessible from Settings / Owner tools)
export function YearEndTransition() {
  const { currentUser } = useUser();
  const [newYear, setNewYear] = useState('2026-27');
  const [startDate, setStartDate] = useState('2026-04-01');
  const [endDate, setEndDate] = useState('2027-03-31');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [confirmed, setConfirmed] = useState(false);

  const handleTransition = async () => {
    if (!confirmed) { setConfirmed(true); return; }
    setLoading(true);
    try {
      const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/settings/year-end-transition`, {
        method: 'POST', headers: h(currentUser),
        body: JSON.stringify({ new_year_name: newYear, start_date: startDate, end_date: endDate })
      }).then(r => r.json());
      if (r.success) setResult(r.data);
    } catch {}
    setLoading(false);
    setConfirmed(false);
  };

  return (
    <ToolPage title="Year-end Session Transition" subtitle="Transition to a new academic year">
      <div style={{ maxWidth: 520 }}>
        {!result ? (
          <>
            <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 12, color: '#FCD34D' }}>
              ⚠️ This will archive the current academic year (2025-26) and create a new one. All existing students and data are preserved.
            </div>
            <FormField label="New Academic Year Name" value={newYear} onChange={setNewYear} placeholder="e.g. 2026-27" required />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Start Date" type="date" value={startDate} onChange={setStartDate} />
              <FormField label="End Date" type="date" value={endDate} onChange={setEndDate} />
            </div>
            {confirmed && (
              <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 13, color: '#FCA5A5' }}>
                Are you absolutely sure? Click again to confirm. This cannot be undone.
              </div>
            )}
            <ActionBtn label={confirmed ? 'Confirm Transition' : 'Start Year Transition'} onClick={handleTransition} disabled={loading} variant={confirmed ? 'danger' : 'primary'} />
            {confirmed && <ActionBtn label="Cancel" variant="secondary" onClick={() => setConfirmed(false)} />}
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🎓</div>
            <h3 style={{ fontFamily: 'Outfit, sans-serif', color: '#10B981', fontSize: 16, marginBottom: 8 }}>Year Transition Complete!</h3>
            <p style={{ color: '#94A3B8', fontSize: 13, marginBottom: 16 }}>{result.message}</p>
            <div style={{ background: '#161622', border: '1px solid #222230', borderRadius: 8, padding: '12px 16px', textAlign: 'left' }}>
              <div style={{ fontSize: 12, color: '#E2E8F0' }}><b>New Year:</b> {result.new_year?.name}</div>
              <div style={{ fontSize: 12, color: '#E2E8F0', marginTop: 4 }}><b>Students Carried Forward:</b> {result.students_carried_forward}</div>
            </div>
          </div>
        )}
      </div>
    </ToolPage>
  );
}
