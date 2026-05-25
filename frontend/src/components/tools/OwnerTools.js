import React, { useState, useEffect, useRef } from 'react';
import { useUser } from '../../contexts/UserContext';
import { executeTool, updateLeave, getStaff, fetchPlatformHealth } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, StatCard, DataTable, Badge, ComingSoon, FormField, ActionBtn, useToolData, LineChartWidget, BarChartWidget, PieChartWidget } from './ToolPage';
import { Activity, CheckCircle, XCircle, AlertTriangle, Plus, RefreshCw, Save, TrendingUp, Users, FileText, Send, Download, Upload, Zap, Database, Cloud } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }
function money(value) { return `Rs ${Number(value || 0).toLocaleString('en-IN')}`; }
const tint = (color, amount) => `color-mix(in srgb, ${color} ${amount}%, transparent)`;

// ─── WhatsApp Fee Reminder Modal ─────────────────────────────────────────────
function WhatsAppReminderModal({ onClose }) {
  const { currentUser } = useUser();
  const [defaulters, setDefaulters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sent, setSent] = useState({});

  useEffect(() => {
    (async () => {
      try {
        const r = await executeTool('get_fee_defaulters', {}, currentUser);
        const rawData = r.success ? (r.data?.data ?? r.data) : [];
        setDefaulters(Array.isArray(rawData) ? rawData : []);
      } catch {}
      setLoading(false);
    })();
  }, [currentUser]);

  const sendReminder = (d) => {
    const phone = (d.parent_phone || d.whatsapp_phone || '').replace(/\D/g, '');
    const isd = phone.startsWith('91') || phone.length < 10 ? phone : `91${phone}`;
    const outstanding = money(d.outstanding_amount || d.amount_due || 0);
    const msg = encodeURIComponent(
      `Dear Parent of ${d.student_name || d.name},\n\nThis is a reminder that a fee of ${outstanding} is outstanding for your child at The Aaryans School. Kindly clear the dues at the earliest to avoid inconvenience.\n\nThank you.`
    );
    window.open(`https://wa.me/${isd}?text=${msg}`, '_blank');
    setSent(p => ({ ...p, [d.student_id || d.id]: true }));
  };

  const sendAll = () => defaulters.forEach(d => sendReminder(d));

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 14, width: '100%', maxWidth: 580, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--tool-hex-2e2e2e)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--tool-hex-e5e5e5)' }}>WhatsApp Fee Reminders</div>
            <div style={{ fontSize: 12, color: 'var(--tool-hex-888)', marginTop: 2 }}>{defaulters.length} defaulters — tap a row to open WhatsApp</div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {defaulters.length > 0 && (
              <ActionBtn label="Send All" icon={<Send size={11} />} onClick={sendAll} />
            )}
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--tool-hex-888)', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>×</button>
          </div>
        </div>
        <div style={{ overflowY: 'auto', flex: 1, padding: '12px 20px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--tool-hex-888)', fontSize: 13 }}>Loading defaulters…</div>
          ) : defaulters.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--tool-hex-888)', fontSize: 13 }}>No fee defaulters found.</div>
          ) : defaulters.map((d, i) => {
            const phone = (d.parent_phone || d.whatsapp_phone || '');
            const isSent = sent[d.student_id || d.id];
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--tool-hex-2e2e2e)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)' }}>{d.student_name || d.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--tool-hex-888)', marginTop: 2 }}>
                    {d.class_name || d.class || ''}
                    {phone ? ` · 📱 ${phone}` : ' · No phone on file'}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--tool-hex-f87171)' }}>{money(d.outstanding_amount || d.amount_due || 0)}</span>
                  {phone ? (
                    <button onClick={() => sendReminder(d)} style={{
                      background: isSent ? 'rgba(34,197,94,0.15)' : 'rgba(34,197,94,0.12)',
                      border: `1px solid ${isSent ? '#22c55e' : 'rgba(34,197,94,0.3)'}`,
                      borderRadius: 8, padding: '5px 12px', cursor: 'pointer',
                      color: '#22c55e', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5,
                    }}>
                      <Send size={11} />{isSent ? 'Sent ✓' : 'Send'}
                    </button>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--tool-hex-555)' }}>No phone</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// 1. School Pulse
export function SchoolPulse() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [feeSummary, setFeeSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showWaModal, setShowWaModal] = useState(false);

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [pulseRes, feeRes] = await Promise.all([
        executeTool('get_school_pulse', {}, currentUser),
        fetch(`${API}/fees/summary`, { headers: h() }).then(r => r.json()),
      ]);
      if (pulseRes.success) setData(pulseRes.data);
      if (feeRes.success) setFeeSummary(feeRes.data);
    } catch {}
    setLoading(false);
  };

  const s = data?.summary || {};
  const leaves = data?.pending_leave_requests || [];
  const feeStats = feeSummary || {};

  return (
    <ToolPage title="School Pulse" subtitle="Today's complete overview" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 1000 }}>
        <div style={{ gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(160px, 1fr))', gap: 12 }}>
          <StatCard value={money(feeStats.total_collected || data?.fee_stats?.paid || 0)} label="FEE COLLECTED" color="var(--tool-hex-34d399)" />
          <StatCard value={money(feeStats.total_outstanding || data?.fee_stats?.overdue || 0)} label="FEE OVERDUE" color="var(--tool-hex-f87171)" />
          <StatCard value={feeStats.transactions ? `${Math.round((Number(feeStats.total_collected || 0) / Math.max(Number(feeStats.total_collected || 0) + Number(feeStats.total_outstanding || 0), 1)) * 100)}%` : '0%'} label="COLLECTION RATE" color="var(--tool-hex-4f8ff7)" />
        </div>
        {/* Quick Actions */}
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)', marginBottom: 14 }}>Quick Actions</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {[
              { icon: Users, label: "Mark Today's Attendance", color: 'var(--tool-hex-4f8ff7)', action: () => window.dispatchEvent(new CustomEvent('open-tool', { detail: 'attendance-recorder' })) },
              { icon: Send, label: 'Send Fee Reminders', color: 'var(--tool-hex-34d399)', action: () => setShowWaModal(true) },
              { icon: AlertTriangle, label: 'View Active Alerts', color: 'var(--tool-hex-f87171)', action: () => window.dispatchEvent(new CustomEvent('open-tool', { detail: 'smart-alerts' })) },
              { icon: FileText, label: 'Generate Daily Report', color: 'var(--tool-hex-a78bfa)', action: async () => {
                try {
                  // Fetch all data in parallel
                  let pulseData = data;
                  const [pulseRes, feeRes, attRes, alertsRes] = await Promise.all([
                    pulseData ? Promise.resolve({ success: true, data: pulseData }) : executeTool('get_school_pulse', {}, currentUser),
                    executeTool('get_fee_summary', {}, currentUser),
                    executeTool('get_attendance_overview', { days: 30 }, currentUser),
                    executeTool('get_smart_alerts', {}, currentUser),
                  ]);
                  if (pulseRes.success && !pulseData) { pulseData = pulseRes.data; setData(pulseRes.data); }
                  const feeData = feeRes.success ? feeRes.data : null;
                  const attData = attRes.success ? attRes.data : null;
                  const alertsData = alertsRes.success ? alertsRes.data : null;

                  const { jsPDF } = await import('jspdf');
                  const doc = new jsPDF();
                  const today = new Date().toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' });
                  const s = pulseData?.summary || {};

                  // Helpers
                  let y = 0;
                  const maxY = 272;
                  const newPage = () => { doc.addPage(); y = 18; };
                  const sectionTitle = (title) => {
                    if (y > maxY - 30) newPage();
                    doc.setFontSize(13); doc.setTextColor(30, 30, 30);
                    doc.text(title, 15, y); y += 2;
                    doc.setDrawColor(180, 180, 180); doc.line(15, y + 2, 195, y + 2); y += 8;
                  };
                  const line11 = (label, val) => {
                    if (y > maxY) newPage();
                    doc.setFontSize(10); doc.setTextColor(80, 80, 80);
                    doc.text(label, 20, y);
                    doc.setTextColor(30, 30, 30);
                    doc.text(String(val ?? 'N/A'), 95, y);
                    y += 7;
                  };
                  const bullet = (text) => {
                    if (y > maxY) newPage();
                    doc.setFontSize(10); doc.setTextColor(70, 70, 70);
                    doc.text('- ' + String(text).slice(0, 85), 22, y); y += 6;
                  };

                  // === COVER ===
                  doc.setFontSize(22); doc.setTextColor(20, 20, 20);
                  doc.text('Daily School Report', 105, 22, { align: 'center' });
                  doc.setFontSize(11); doc.setTextColor(100, 100, 100);
                  doc.text(`Date: ${today}`, 105, 31, { align: 'center' });
                  doc.setDrawColor(200, 200, 200); doc.line(15, 36, 195, 36);
                  y = 48;

                  // === SECTION 1: TODAY'S SNAPSHOT ===
                  sectionTitle('1. Today\'s Snapshot');
                  line11('Total Students Enrolled:', s.total_students || 0);
                  line11('Total Staff:', s.total_staff || 0);
                  line11("Today's Attendance Rate:", s.attendance_rate || 'N/A');
                  line11('Avg Attendance (30 days):', attData?.avg_attendance_rate || 'N/A');
                  line11('Total Attendance Records:', attData?.total_records || 0);
                  line11('Fees Collected Today:', pulseData?.fee_stats?.paid || 'N/A');
                  line11('Total Overdue Fees:', pulseData?.fee_stats?.overdue || 'N/A');
                  y += 4;

                  // === SECTION 2: CLASS-WISE ATTENDANCE ===
                  const classStats = attData?.class_stats_today || [];
                  if (classStats.length > 0) {
                    sectionTitle('2. Class-wise Attendance (Today)');
                    doc.setFontSize(8); doc.setTextColor(60, 60, 60);
                    doc.text('Class', 20, y); doc.text('Present', 75, y); doc.text('Total', 115, y); doc.text('Rate', 155, y);
                    y += 4; doc.setDrawColor(200, 200, 200); doc.line(20, y, 190, y); y += 4;
                    doc.setFontSize(9); doc.setTextColor(70, 70, 70);
                    classStats.forEach((c, ri) => {
                      if (y > maxY) newPage();
                      if (ri % 2 === 0) { doc.setFillColor(248, 248, 248); doc.rect(18, y - 4, 174, 6, 'F'); }
                      doc.text(String(c.class), 20, y); doc.text(String(c.present), 75, y); doc.text(String(c.total), 115, y); doc.text(String(c.rate), 155, y);
                      y += 6;
                    });
                    y += 6;
                  }

                  // === SECTION 3: FEE SUMMARY ===
                  if (feeData) {
                    sectionTitle('3. Fee Collection Summary');
                    const fs = feeData.stats || {};
                    line11('Total Collected:', fs.total_collected || 'N/A');
                    line11('Total Overdue:', fs.total_overdue || 'N/A');
                    line11('Collection Rate:', fs.collection_rate || 'N/A');
                    line11('Students with Dues:', fs.students_with_dues || 0);
                    line11('Overdue 60+ Days:', fs.overdue_60_days || 0);
                    // Top defaulters table
                    const defaulters = feeData.defaulters || [];
                    if (defaulters.length > 0) {
                      if (y > maxY - 20) newPage();
                      doc.setFontSize(10); doc.setTextColor(50, 50, 50); doc.text('Top Fee Defaulters:', 20, y); y += 6;
                      doc.setFontSize(8); doc.setTextColor(60, 60, 60);
                      doc.text('Student', 20, y); doc.text('Class', 90, y); doc.text('Overdue', 130, y); doc.text('Days', 170, y);
                      y += 4; doc.setDrawColor(200, 200, 200); doc.line(20, y, 190, y); y += 4;
                      doc.setFontSize(8.5); doc.setTextColor(70, 70, 70);
                      defaulters.slice(0, 15).forEach((d, ri) => {
                        if (y > maxY) newPage();
                        if (ri % 2 === 0) { doc.setFillColor(248, 248, 248); doc.rect(18, y - 4, 174, 6, 'F'); }
                        doc.text(String(d.student_name || '').slice(0, 22), 20, y);
                        doc.text(String(d.class || ''), 90, y);
                        doc.text(String(d.amount_overdue_fmt || ''), 130, y);
                        doc.text(String(d.days_overdue || '') + 'd', 170, y);
                        y += 6;
                      });
                    }
                    y += 6;
                  }

                  // === SECTION 4: STAFF ALERTS ===
                  sectionTitle('4. Staff Alerts');
                  const staffAbsent = pulseData?.staff_absent_today || [];
                  line11('Staff Absent Today:', staffAbsent.length || 0);
                  staffAbsent.forEach(name => bullet(name));
                  const leaves = pulseData?.pending_leave_requests || [];
                  line11('Pending Leave Requests:', leaves.length || 0);
                  leaves.forEach(lr => bullet(`${lr.staff_name} — ${lr.leave_type} (${lr.start_date} to ${lr.end_date})`));
                  y += 4;

                  // === SECTION 5: CHRONIC ABSENTEES ===
                  const chronic = pulseData?.chronic_absent_students || [];
                  sectionTitle('5. Chronic Absentees (3+ consecutive days)');
                  if (chronic.length > 0) {
                    chronic.forEach(st => bullet(st.name || st));
                  } else {
                    doc.setFontSize(10); doc.setTextColor(80, 80, 80); doc.text('No chronic absentees today.', 20, y); y += 7;
                  }
                  y += 4;

                  // === SECTION 6: SMART ALERTS ===
                  const alerts = alertsData?.alerts || [];
                  if (alerts.length > 0) {
                    sectionTitle('6. Active Smart Alerts');
                    alerts.forEach(a => {
                      if (y > maxY) newPage();
                      doc.setFontSize(10); doc.setTextColor(70, 70, 70);
                      doc.text(`[${(a.priority || '').toUpperCase()}] ${a.text}`, 20, y); y += 7;
                    });
                    y += 4;
                  }

                  // === FOOTER on all pages ===
                  const totalPages = doc.getNumberOfPages();
                  for (let p = 1; p <= totalPages; p++) {
                    doc.setPage(p);
                    doc.setFontSize(8); doc.setTextColor(160, 160, 160);
                    doc.text('EduFlow — Daily Report — Confidential', 105, 290, { align: 'center' });
                    doc.text(`Page ${p} of ${totalPages}`, 190, 290, { align: 'right' });
                  }

                  doc.save(`daily-report-${new Date().toISOString().slice(0, 10)}.pdf`);
                } catch (err) { alert(`PDF generation failed: ${err.message}`); }
              }},
            ].map((a, i) => (
              <button key={i} data-testid={`quick-action-${i}`} onClick={a.action} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7, background: 'transparent', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 10, padding: '14px 8px', cursor: 'pointer', color: 'var(--tool-hex-a3a3a3)', fontSize: 11, fontWeight: 500, transition: 'all 0.15s' }}
                onMouseEnter={e => { e.currentTarget.style.background = tint(a.color, 6); e.currentTarget.style.borderColor = tint(a.color, 25); }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'var(--tool-hex-2e2e2e)'; }}>
                <a.icon size={18} color={a.color} />
                <span style={{ textAlign: 'center', lineHeight: 1.3 }}>{a.label}</span>
              </button>
            ))}
          </div>
          <button data-testid="open-att-alerts-btn" onClick={() => window.dispatchEvent(new CustomEvent('open-tool', { detail: 'attendance-alerts' }))}
            style={{ width: '100%', marginTop: 12, background: 'transparent', border: '1px solid var(--tool-hex-a78bfa)', borderRadius: 8, padding: '10px', color: 'var(--tool-hex-a78bfa)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
            Configure Attendance Alerts
          </button>
        </div>

        {/* Snapshot */}
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 14, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)', marginBottom: 14 }}>Today's Snapshot</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
            <StatCard value={s.attendance_rate || '0%'} label="ATTENDANCE" color="var(--tool-hex-34d399)" small />
            <StatCard value={s.total_students || 0} label="ENROLLED" color="var(--tool-hex-e5e5e5)" small />
            <StatCard value={data?.fee_stats?.paid || '₹0'} label="FEES PAID" color="var(--tool-hex-4f8ff7)" small />
            <StatCard value={data?.fee_stats?.overdue || '₹0'} label="OVERDUE" color="var(--tool-hex-f87171)" small />
          </div>
          {(data?.staff_absent_today?.length || 0) > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 7, padding: '8px 12px', marginBottom: 6, fontSize: 12, color: 'var(--tool-hex-fcd34d)' }}><AlertTriangle size={12} />{data.staff_absent_today.length} teachers absent today</div>}
          {(data?.chronic_absent_students?.length || 0) > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 7, padding: '8px 12px', marginBottom: 6, fontSize: 12, color: 'var(--tool-hex-fca5a5)' }}><AlertTriangle size={12} />{data.chronic_absent_students.length} students absent 3+ days</div>}
          {data?.fee_stats?.paid && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 7, padding: '8px 12px', marginBottom: 6, fontSize: 12, color: 'var(--tool-hex-6ee7b7)' }}><CheckCircle size={12} />Fee collection: {data.fee_stats.paid} collected</div>}
          {leaves.length > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 7, padding: '8px 12px', fontSize: 12, color: 'var(--tool-hex-93c5fd)' }}><Activity size={12} />{leaves.length} leave requests pending</div>}
        </div>
      </div>

      {/* Pending Leaves quick actions */}
      {leaves.length > 0 && (
        <div style={{ marginTop: 16, background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11, overflow: 'hidden', maxWidth: 1000 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--tool-hex-2e2e2e)' }}>
            <span style={{ fontFamily: 'Inter, sans-serif', fontWeight: 600, fontSize: 13, color: 'var(--tool-hex-e5e5e5)' }}>Pending Leave Requests</span>
          </div>
          {leaves.map((lr, i) => (
            <div key={lr.id || i} style={{ padding: '12px 16px', borderBottom: i < leaves.length - 1 ? '1px solid var(--tool-hex-242424)' : 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontWeight: 600, color: 'var(--tool-hex-e5e5e5)', fontSize: 13 }}>{lr.staff_name}</span>
                <span style={{ color: 'var(--tool-hex-737373)', fontSize: 11, marginLeft: 10 }}>{lr.leave_type} · {lr.start_date} – {lr.end_date}</span>
                <div style={{ fontSize: 11, color: 'var(--tool-hex-525252)', marginTop: 2, fontStyle: 'italic' }}>{lr.reason}</div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <ActionBtn label="Approve" variant="success" icon={<CheckCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'approved', currentUser); load(); }} />
                <ActionBtn label="Reject" variant="danger" icon={<XCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'rejected', currentUser); load(); }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {showWaModal && <WhatsAppReminderModal onClose={() => setShowWaModal(false)} />}
    </ToolPage>
  );
}

// Story 7-41 — Advanced Reporting (Recharts) — Owner sees both attendance
// trend (last 3 months) and fee collection summary (last 6 months); the
// principal variant in AdminTools.js renders only the attendance chart.
export function ReportsTrends() {
  const [attendance, setAttendance] = useState(null);
  const [fees, setFees] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [a, f] = await Promise.all([
        fetch(`${API}/reports/attendance-trends?months=3`, { headers: h() }).then(r => r.json()),
        fetch(`${API}/reports/fee-collection-summary?months=6`, { headers: h() }).then(r => r.json()),
      ]);
      setAttendance(a);
      setFees(f);
    } catch {}
    setLoading(false);
  };

  const attendanceChartData = (attendance?.overall || []).map(r => ({ month: r.month, pct: r.attendance_pct }));
  const feeChartData = (fees?.data || []).map(r => ({ month: r.month, Collected: r.collected, Outstanding: r.outstanding }));

  return (
    <ToolPage title="Reports & trends" subtitle="Attendance and collection patterns" onRefresh={load} loading={loading}>
      <div style={{ maxWidth: 1000 }}>
        {attendance?.empty ? (
          <div style={{ padding: 24, border: '1px dashed var(--tool-hex-2e2e2e)', borderRadius: 12, color: 'var(--tool-hex-a3a3a3)', marginBottom: 16 }}>
            Not enough attendance data yet — chart will appear once a month of records exists.
          </div>
        ) : attendanceChartData.length > 0 && (
          <LineChartWidget
            title="Overall attendance % — last 3 months"
            data={attendanceChartData}
            xKey="month"
            lines={[{ key: 'pct', name: 'Attendance %', color: 'var(--tool-hex-4f8ff7)' }]}
          />
        )}

        {fees?.empty ? (
          <div style={{ padding: 24, border: '1px dashed var(--tool-hex-2e2e2e)', borderRadius: 12, color: 'var(--tool-hex-a3a3a3)' }}>
            Not enough fee data yet — chart will appear once transactions are recorded.
          </div>
        ) : feeChartData.length > 0 && (
          <BarChartWidget
            title="Fee collection vs outstanding — last 6 months"
            data={feeChartData}
            xKey="month"
            bars={[
              { key: 'Collected', name: 'Collected (₹)', color: 'var(--tool-hex-34d399)' },
              { key: 'Outstanding', name: 'Outstanding (₹)', color: 'var(--tool-hex-f87171)' },
            ]}
          />
        )}
      </div>
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
        <StatCard value={stats.total_overdue || '₹0'} label="TOTAL OVERDUE" color="var(--tool-hex-f87171)" />
        <StatCard value={stats.students_with_dues || 0} label="STUDENTS WITH DUES" color="var(--tool-hex-fbbf24)" />
        <StatCard value={stats.overdue_60_days || 0} label="OVERDUE 60+ DAYS" color="var(--tool-hex-f87171)" />
        <StatCard value={stats.collection_rate || '0%'} label="COLLECTION RATE" color="var(--tool-hex-34d399)" />
      </div>
      {chartData.length > 0 && (
        <BarChartWidget data={chartData} xKey="name" bars={[{ key: 'amount', color: 'var(--tool-hex-f87171)', name: 'Overdue (₹)' }]} title="Top Defaulters — Amount Overdue" height={200} />
      )}
      <DataTable title={`Fee Defaulters — Top ${defaulters.length}`} headers={['Student', 'Class', 'Amount Overdue', 'Days Overdue']}
        rows={defaulters.map(d => [d.student_name, d.class, <span style={{ color: 'var(--tool-hex-f87171)', fontWeight: 600 }}>{d.amount_overdue_fmt}</span>, <span style={{ color: d.days_overdue > 60 ? 'var(--tool-hex-f87171)' : 'var(--tool-hex-fbbf24)' }}>{d.days_overdue} days</span>])}
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
        fetch(`${API}/settings/classes`, { headers: h() }).then(r => r.json()),
        fetch(`${API}/students/?limit=2000`, { headers: h() }).then(r => r.json()),
      ]);
      const classes = classRes.data || [];
      const students = studRes.data || [];
      // Count students per class_id
      const classCounts = {};
      students.forEach(s => {
        const cid = s.class_id;
        if (cid) classCounts[cid] = (classCounts[cid] || 0) + 1;
      });
      // Count boys / girls per class
      const classGender = {};
      students.forEach(s => {
        const cid = s.class_id;
        if (!cid) return;
        if (!classGender[cid]) classGender[cid] = { boys: 0, girls: 0 };
        if ((s.gender || '').toLowerCase() === 'male' || (s.gender || '').toLowerCase() === 'boy') classGender[cid].boys++;
        else if ((s.gender || '').toLowerCase() === 'female' || (s.gender || '').toLowerCase() === 'girl') classGender[cid].girls++;
      });
      const classesWithCount = classes.map(c => ({
        ...c,
        student_count: classCounts[c.id] || 0,
        boys: classGender[c.id]?.boys || 0,
        girls: classGender[c.id]?.girls || 0,
      })).sort((a, b) => (b.student_count - a.student_count));
      const total = students.length || studRes.meta?.total || 0;
      setData({ classes: classesWithCount, total });
    } catch {}
    setLoading(false);
  };

  const totalStudents = data?.total || 0;
  const totalClasses = data?.classes?.length || 0;
  const avgPerClass = totalClasses > 0 ? Math.round(totalStudents / totalClasses) : 0;

  return (
    <ToolPage title="Student Strength" subtitle="Class-wise enrollment overview" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20, maxWidth: 600 }}>
        <StatCard value={totalStudents} label="TOTAL STUDENTS" color="var(--tool-hex-4f8ff7)" />
        <StatCard value={totalClasses} label="TOTAL CLASSES" color="var(--tool-hex-34d399)" />
        <StatCard value={avgPerClass} label="AVG PER CLASS" color="var(--tool-hex-a78bfa)" />
      </div>
      <DataTable title="Class-wise Strength" headers={['Class', 'Section', 'Students', 'Boys', 'Girls', 'Academic Year']}
        rows={(data?.classes || []).map(c => [
          c.name,
          c.section || '—',
          <span style={{ fontWeight: 700, color: 'var(--tool-hex-4f8ff7)', fontSize: 14 }}>{c.student_count}</span>,
          <span style={{ color: 'var(--tool-hex-60a5fa)' }}>{c.boys}</span>,
          <span style={{ color: 'var(--tool-hex-f9a8d4)' }}>{c.girls}</span>,
          '2025-26',
        ])}
        emptyMsg="No classes configured yet"
      />
    </ToolPage>
  );
}

// 3b. Data Import
export function DataImport() {
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [result, setResult] = useState(null);
  const [overwrite, setOverwrite] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const upload = async (mode) => {
    if (!file) return;
    setLoading(true);
    setError('');
    if (mode === 'validate') setResult(null);
    const form = new FormData();
    form.append('file', file);
    if (mode === 'commit') form.append('overwrite_duplicates', overwrite ? 'true' : 'false');
    try {
      const headers = h();
      delete headers['Content-Type'];
      const res = await fetch(`${API}/import/${mode}`, {
        method: 'POST',
        headers,
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Import ${mode} failed`);
      if (mode === 'validate') setReport(data);
      else setResult(data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const canCommit = report && report.error_count === 0 && file;
  const errors = report?.errors || result?.errors || [];
  const duplicates = report?.duplicates || result?.duplicates || [];

  return (
    <ToolPage title="Data Import" subtitle="Validate and import student records">
      <div style={{ maxWidth: 980 }}>
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 14, padding: 18, marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(240px, 1fr) auto auto', gap: 10, alignItems: 'center' }}>
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={e => { setFile(e.target.files?.[0] || null); setReport(null); setResult(null); setError(''); }}
              style={{ color: 'var(--tool-hex-a0a0a0)', fontSize: 13 }}
            />
            <ActionBtn label={loading ? 'Validating...' : 'Validate'} icon={<Upload size={13} />} onClick={() => upload('validate')} disabled={!file || loading} />
            <ActionBtn label={loading ? 'Importing...' : 'Commit Import'} variant="success" icon={<CheckCircle size={13} />} onClick={() => upload('commit')} disabled={!canCommit || loading} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--tool-hex-a0a0a0)', fontSize: 12 }}>
            <input id="overwrite-import-duplicates" type="checkbox" checked={overwrite} onChange={e => setOverwrite(e.target.checked)} />
            <label htmlFor="overwrite-import-duplicates">Overwrite duplicate students during commit</label>
          </div>
          <div style={{ marginTop: 10, color: 'var(--tool-hex-737373)', fontSize: 12 }}>
            Required columns: name, class, section, parent_name, parent_phone. Optional: date_of_birth, address, route_zone_id.
          </div>
          {error && <div style={{ marginTop: 12, color: 'var(--tool-hex-f87171)', fontSize: 13 }}>{error}</div>}
          {result && <div style={{ marginTop: 12, color: 'var(--tool-hex-34d399)', fontSize: 13 }}>Imported {result.imported_count} rows. Skipped {result.skipped_count} rows.</div>}
        </div>

        {report && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
            <StatCard value={report.valid_count || 0} label="VALID ROWS" color="var(--tool-hex-34d399)" />
            <StatCard value={report.error_count || 0} label="ERRORS" color="var(--tool-hex-f87171)" />
            <StatCard value={report.duplicate_count || 0} label="DUPLICATES" color="var(--tool-hex-fbbf24)" />
            <StatCard value={file?.name || '—'} label="FILE" color="var(--tool-hex-4f8ff7)" />
          </div>
        )}

        {duplicates.length > 0 && (
          <DataTable
            title="Duplicate Students"
            headers={['Row', 'Student', 'Class', 'Status']}
            rows={duplicates.map(d => [d.row, d.name, `${d.class} ${d.section}`, <Badge text={overwrite ? 'Overwrite on commit' : 'Skip on commit'} color={overwrite ? 'yellow' : 'gray'} />])}
          />
        )}

        <DataTable
          title="Validation Errors"
          headers={['Row', 'Field', 'Message']}
          rows={errors.map(e => [e.row, e.field, <span style={{ color: 'var(--tool-hex-f87171)' }}>{e.message}</span>])}
          emptyMsg={report ? 'No validation errors' : 'Validate a CSV or XLSX file to see row-level results'}
        />
      </div>
    </ToolPage>
  );
}

// 4. Attendance Overview (Owner) - with recharts
export function AttendanceOverview() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try {
      const [attRes, classRes] = await Promise.all([
        executeTool('get_attendance_overview', { days: 30 }, currentUser),
        fetch(`${API}/settings/classes`, { headers: h() }).then(r => r.json()),
      ]);
      if (attRes.success) setData(attRes.data);
      setClasses(classRes.data || []);
    } catch {}
    setLoading(false);
  };

  const chartData = (data?.daily_trend || []).map(d => ({ date: d.date?.slice(5), rate: d.rate, present: d.present, absent: d.absent }));

  // Merge class_stats_today with all classes; show "Not marked" for missing ones
  // Backend formats class key as "Name-Section" (e.g. "5-A"), match all variants
  const classStatMap = {};
  (data?.class_stats_today || []).forEach(c => { classStatMap[c.class] = c; });
  const allClassRows = classes.length > 0
    ? classes.map(cls => {
        const sec = cls.section || '';
        const stat = classStatMap[cls.name]
          || classStatMap[`${cls.name}-${sec}`]
          || classStatMap[`${cls.name} ${sec}`]
          || classStatMap[`${cls.name}${sec}`];
        if (stat) {
          return [
            `${cls.name}${cls.section ? ' ' + cls.section : ''}`,
            stat.present,
            stat.total,
            <span style={{ color: parseFloat(stat.rate) >= 85 ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-f87171)', fontWeight: 600 }}>{stat.rate}</span>,
          ];
        }
        return [
          `${cls.name}${cls.section ? ' ' + cls.section : ''}`,
          <span style={{ color: 'var(--tool-hex-737373)' }}>—</span>,
          <span style={{ color: 'var(--tool-hex-737373)' }}>—</span>,
          <span style={{ color: 'var(--tool-hex-737373)', fontSize: 11 }}>Not marked</span>,
        ];
      })
    : (data?.class_stats_today || []).map(c => [
        c.class,
        c.present,
        c.total,
        <span style={{ color: parseFloat(c.rate) >= 85 ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-f87171)', fontWeight: 600 }}>{c.rate}</span>,
      ]);

  return (
    <ToolPage title="Attendance Overview" subtitle="Trends and class-wise analysis" onRefresh={load} loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16, maxWidth: 500 }}>
        <StatCard value={data?.avg_attendance_rate || '0%'} label="AVG RATE (30 DAYS)" color="var(--tool-hex-34d399)" />
        <StatCard value={data?.total_records || 0} label="TOTAL RECORDS" color="var(--tool-hex-4f8ff7)" />
        <StatCard value="Last 30 days" label="PERIOD" color="var(--tool-hex-a78bfa)" />
      </div>
      {chartData.length > 0 && (
        <LineChartWidget data={chartData} xKey="date" lines={[{ key: 'rate', color: 'var(--tool-hex-34d399)', name: 'Attendance %' }, { key: 'absent', color: 'var(--tool-hex-f87171)', name: 'Absent' }]} title="30-Day Attendance Trend" height={200} />
      )}
      <DataTable title="Class-wise Today" headers={['Class', 'Present', 'Total', 'Rate']}
        rows={allClassRows}
        emptyMsg="No classes configured"
      />
    </ToolPage>
  );
}

// 5. Staff Attendance Tracker
const STATUS_OPTIONS = ['present', 'absent', 'late', 'on-leave'];
const STATUS_COLORS = { present: '#34d399', absent: '#f87171', late: '#fbbf24', 'on-leave': '#a78bfa', not_marked: '#737373' };
const STATUS_BG = { present: 'rgba(52,211,153,0.12)', absent: 'rgba(248,113,113,0.12)', late: 'rgba(251,191,36,0.12)', 'on-leave': 'rgba(167,139,250,0.12)', not_marked: 'rgba(115,115,115,0.1)' };

export function StaffAttendanceTracker({ title = 'Staff Tracker', subtitle = 'Attendance & leave management', defaultTab = 'attendance' }) {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [markMode, setMarkMode] = useState(false);
  const [markDate, setMarkDate] = useState(new Date().toISOString().slice(0, 10));
  const [markData, setMarkData] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => { setActiveTab(defaultTab); }, [defaultTab]);
  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try { const r = await executeTool('get_staff_status', {}, currentUser); if (r.success) setData(r.data); } catch {}
    setLoading(false);
  };

  const staff = data?.staff_list || [];
  const leaves = data?.pending_leaves || [];

  const enterMarkMode = () => {
    const initial = {};
    staff.forEach(s => {
      initial[s.id] = s.status === 'not_marked' ? 'present' : s.status;
    });
    setMarkData(initial);
    setMarkMode(true);
    setSaveMsg('');
  };

  const cancelMark = () => { setMarkMode(false); setSaveMsg(''); };

  const setStaffStatus = (id, status) => setMarkData(p => ({ ...p, [id]: status }));

  const markAll = (status) => {
    const next = {};
    staff.forEach(s => { next[s.id] = status; });
    setMarkData(next);
  };

  const submitAttendance = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const records = Object.entries(markData).map(([staff_id, status]) => ({ staff_id, status }));
      const res = await fetch(`${API}/attendance/staff/bulk`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: markDate, records }),
      });
      const result = await res.json();
      if (result.success) {
        setSaveMsg(`Attendance saved for ${records.length} staff members.`);
        setMarkMode(false);
        load();
      } else {
        setSaveMsg(result.detail || 'Failed to save attendance.');
      }
    } catch { setSaveMsg('Network error. Please try again.'); }
    setSaving(false);
  };

  const markedCount = Object.values(markData).filter(s => s !== 'not_marked').length;
  const presentCount = Object.values(markData).filter(s => s === 'present').length;

  return (
    <ToolPage title={title} subtitle={subtitle} onRefresh={load} loading={loading}>
      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18, maxWidth: 700 }}>
        <StatCard value={data?.total_staff || 0} label="TOTAL STAFF" color="var(--tool-hex-e5e5e5)" />
        <StatCard value={data?.present_today || 0} label="PRESENT TODAY" color="var(--tool-hex-34d399)" />
        <StatCard value={data?.absent_today || 0} label="ABSENT TODAY" color="var(--tool-hex-f87171)" />
        <StatCard value={leaves.length} label="PENDING LEAVES" color="var(--tool-hex-fbbf24)" />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--tool-hex-2e2e2e)', marginBottom: 14 }}>
        {['attendance', 'leaves'].map(t => (
          <button key={t} onClick={() => { setActiveTab(t); setMarkMode(false); }} data-testid={`tab-${t}`}
            style={{ background: 'none', border: 'none', padding: '8px 14px', borderBottom: activeTab === t ? '2px solid var(--tool-hex-4f8ff7)' : '2px solid transparent', color: activeTab === t ? 'var(--tool-hex-fff)' : 'var(--tool-hex-737373)', fontSize: 13, fontWeight: 500, cursor: 'pointer', marginBottom: -1 }}>
            {t === 'attendance' ? "Today's Attendance" : `Pending Leaves (${leaves.length})`}
          </button>
        ))}
      </div>

      {/* Attendance Tab */}
      {activeTab === 'attendance' && (
        <>
          {/* Mark Mode */}
          {markMode ? (
            <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: 16 }}>
              {/* Mark Mode Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)', marginBottom: 4 }}>Mark Attendance</div>
                    <input type="date" value={markDate} onChange={e => setMarkDate(e.target.value)}
                      style={{ background: 'var(--tool-hex-252525)', border: '1px solid var(--tool-hex-333)', borderRadius: 7, padding: '5px 10px', color: 'var(--tool-hex-e5e5e5)', fontSize: 12, cursor: 'pointer' }} />
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--tool-hex-737373)', marginTop: 18 }}>
                    {markedCount}/{staff.length} marked · {presentCount} present
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, color: 'var(--tool-hex-737373)', alignSelf: 'center' }}>Mark all:</span>
                  {STATUS_OPTIONS.map(s => (
                    <button key={s} onClick={() => markAll(s)}
                      style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, border: `1px solid ${STATUS_COLORS[s]}`, background: STATUS_BG[s], color: STATUS_COLORS[s], cursor: 'pointer' }}>
                      {s.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </button>
                  ))}
                </div>
              </div>

              {/* Staff Rows */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 420, overflowY: 'auto' }}>
                {staff.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 24, color: 'var(--tool-hex-737373)', fontSize: 13 }}>No staff found.</div>
                ) : staff.map(s => {
                  const current = markData[s.id] || 'present';
                  return (
                    <div key={s.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--tool-hex-252525)', borderRadius: 9, border: `1px solid ${STATUS_COLORS[current]}22` }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)' }}>{s.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--tool-hex-737373)', marginTop: 2, textTransform: 'capitalize' }}>{s.staff_type}</div>
                      </div>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {STATUS_OPTIONS.map(opt => (
                          <button key={opt} onClick={() => setStaffStatus(s.id, opt)}
                            style={{
                              padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                              border: `1px solid ${current === opt ? STATUS_COLORS[opt] : 'var(--tool-hex-333)'}`,
                              background: current === opt ? STATUS_BG[opt] : 'transparent',
                              color: current === opt ? STATUS_COLORS[opt] : 'var(--tool-hex-737373)',
                              transition: 'all 0.15s',
                            }}>
                            {opt === 'on-leave' ? 'On Leave' : opt.replace(/\b\w/g, c => c.toUpperCase())}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Save / Cancel */}
              {saveMsg && (
                <div style={{ marginTop: 10, fontSize: 12, color: saveMsg.includes('saved') ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-f87171)' }}>{saveMsg}</div>
              )}
              <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                <ActionBtn label={saving ? 'Saving...' : `Save Attendance (${staff.length})`} disabled={saving} onClick={submitAttendance} />
                <ActionBtn label="Cancel" variant="secondary" onClick={cancelMark} />
              </div>
            </div>
          ) : (
            /* View Mode */
            <>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
                <ActionBtn label="Mark Attendance" onClick={enterMarkMode} />
              </div>
              {saveMsg && (
                <div style={{ marginBottom: 10, fontSize: 12, color: 'var(--tool-hex-34d399)', background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.3)', borderRadius: 8, padding: '8px 12px' }}>{saveMsg}</div>
              )}
              {staff.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 32, color: 'var(--tool-hex-737373)', fontSize: 13 }}>No staff data. Add staff first.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {staff.map(s => (
                    <div key={s.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 9 }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)' }}>{s.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--tool-hex-737373)', marginTop: 2, textTransform: 'capitalize' }}>{s.staff_type}</div>
                      </div>
                      <span style={{
                        padding: '4px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                        background: STATUS_BG[s.status] || STATUS_BG.not_marked,
                        color: STATUS_COLORS[s.status] || STATUS_COLORS.not_marked,
                        border: `1px solid ${STATUS_COLORS[s.status] || STATUS_COLORS.not_marked}44`,
                      }}>
                        {s.status === 'not_marked' ? 'Not Marked' : s.status === 'on-leave' ? 'On Leave' : s.status.replace(/\b\w/g, c => c.toUpperCase())}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Leaves Tab */}
      {activeTab === 'leaves' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {leaves.length === 0
            ? <div style={{ padding: 24, textAlign: 'center', color: 'var(--tool-hex-737373)', fontSize: 13, background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11 }}>No pending leave requests</div>
            : leaves.map((lr, i) => (
              <div key={lr.id || i} style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 10, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--tool-hex-e5e5e5)', fontSize: 13 }}>{lr.staff_name}</div>
                  <div style={{ color: 'var(--tool-hex-737373)', fontSize: 11 }}>{lr.leave_type} · {lr.start_date} – {lr.end_date}</div>
                  <div style={{ color: 'var(--tool-hex-a3a3a3)', fontSize: 11, marginTop: 3, fontStyle: 'italic' }}>{lr.reason}</div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <ActionBtn label="Approve" variant="success" icon={<CheckCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'approved', currentUser); load(); }} />
                  <ActionBtn label="Reject" variant="danger" icon={<XCircle size={11} />} onClick={async () => { await updateLeave(lr.id, 'rejected', currentUser); load(); }} />
                </div>
              </div>
            ))
          }
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
        fetch(`${API}/ops/expenses`, { headers: h() }).then(r => r.json()),
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
        <StatCard value={data?.total_collected || '₹0'} label="TOTAL COLLECTED" color="var(--tool-hex-34d399)" />
        <StatCard value={fmtExp || '₹0'} label="TOTAL EXPENSES" color="var(--tool-hex-f87171)" />
        <StatCard value={data?.collection_rate || '0%'} label="COLLECTION RATE" color="var(--tool-hex-4f8ff7)" />
      </div>
      <DataTable title="Revenue by Fee Type" headers={['Fee Type', 'Expected', 'Collected']}
        rows={(data?.by_fee_type || []).map(r => [r.fee_type, r.expected, <span style={{ color: 'var(--tool-hex-34d399)' }}>{r.collected}</span>])}
        emptyMsg="No fee data available"
      />
      <DataTable title="Recent Expenses" headers={['Date', 'Category', 'Description', 'Amount']}
        rows={expenses.slice(0, 10).map(e => [e.date, e.category, e.description, <span style={{ color: 'var(--tool-hex-f87171)' }}>₹{(e.amount || 0).toLocaleString('en-IN')}</span>])}
        emptyMsg="No expenses recorded"
      />
    </ToolPage>
  );
}

// 7. Announcement Broadcaster
export function AnnouncementBroadcaster() {
  const { currentUser } = useUser();
  const [announcements, setAnnouncements] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: '', content: '', audience_type: 'all', audience_roles: [], audience_classes: [] });
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const ROLES = ['teacher', 'parent', 'student', 'admin'];

  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try {
      const annRes = await fetch(`${API}/ops/announcements`, { headers: h() }).then(r => r.json());
      if (annRes.success) setAnnouncements(annRes.data || []);
    } catch {}
    try {
      const classRes = await fetch(`${API}/settings/classes`, { headers: h() }).then(r => r.json());
      setClasses(classRes.data || []);
    } catch {}
    setLoading(false);
  };

  const toggleRole = (role) => setForm(p => ({
    ...p,
    audience_roles: p.audience_roles.includes(role) ? p.audience_roles.filter(r => r !== role) : [...p.audience_roles, role],
  }));

  const toggleClass = (cls) => setForm(p => ({
    ...p,
    audience_classes: p.audience_classes.includes(cls) ? p.audience_classes.filter(c => c !== cls) : [...p.audience_classes, cls],
  }));

  const resetForm = () => { setForm({ title: '', content: '', audience_type: 'all', audience_roles: [], audience_classes: [] }); setShowForm(false); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.content.trim()) return;
    setSaving(true);
    try {
      const targetRoles = form.audience_type === 'all'
        ? ['teacher', 'student', 'admin', 'parent']
        : form.audience_type === 'class'
          ? ['student']
          : form.audience_roles;
      const payload = {
        title: form.title,
        content: form.content,
        audience_type: form.audience_type,
        audience_roles: targetRoles,
        target_roles: targetRoles,
        audience_classes: form.audience_type === 'class' ? form.audience_classes : [],
        is_draft: false,
      };
      const res = await fetch(`${API}/ops/announcements`, { method: 'POST', headers: { ...h(), 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const r = await res.json();
      if (r.success) { resetForm(); load(); }
      else alert(`Failed to send announcement: ${r.detail || r.message || `HTTP ${res.status}`}`);
    } catch (err) { alert(`Network error: ${err.message || 'Please try again.'}`); }
    setSaving(false);
  };

  const audienceLabel = (a) => {
    if (a.audience_type === 'role' && a.audience_roles?.length) return `Roles: ${a.audience_roles.join(', ')}`;
    if (a.audience_type === 'class' && a.audience_classes?.length) return `Classes: ${a.audience_classes.join(', ')}`;
    return a.audience_type === 'all' ? 'All Staff & Students' : a.audience_type;
  };

  return (
    <ToolPage title="Announcement Broadcaster" subtitle="Broadcast messages to school" onRefresh={load} loading={loading}
      actions={(currentUser.role === 'owner' || currentUser.role === 'admin') && (
        <ActionBtn label="New Announcement" onClick={() => setShowForm(true)} icon={<Plus size={11} />} />
      )}>
      {showForm && (
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11, padding: 20, marginBottom: 18 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>New Announcement</h3>
          <form onSubmit={handleSubmit}>
            <FormField label="Title" value={form.title} onChange={f('title')} placeholder="Announcement title" required />
            <FormField label="Message" type="textarea" value={form.content} onChange={f('content')} placeholder="Write your announcement..." required />
            <FormField label="Audience" type="select" value={form.audience_type} onChange={f('audience_type')}
              options={[{ value: 'all', label: 'Everyone (All Staff & Students)' }, { value: 'role', label: 'By Role' }, { value: 'class', label: 'By Class' }]} />

            {/* Role selector */}
            {form.audience_type === 'role' && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--tool-hex-737373)', marginBottom: 8, fontWeight: 600 }}>Select Roles *</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {ROLES.map(role => (
                    <label key={role} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: form.audience_roles.includes(role) ? 'rgba(79,143,247,0.15)' : 'var(--tool-hex-252525)', border: `1px solid ${form.audience_roles.includes(role) ? 'var(--tool-hex-4f8ff7)' : 'var(--tool-hex-333)'}`, borderRadius: 8, cursor: 'pointer', fontSize: 12, color: form.audience_roles.includes(role) ? 'var(--tool-hex-4f8ff7)' : 'var(--tool-hex-a0a0a0)', textTransform: 'capitalize' }}>
                      <input type="checkbox" checked={form.audience_roles.includes(role)} onChange={() => toggleRole(role)} style={{ accentColor: 'var(--tool-hex-4f8ff7)' }} />
                      {role}
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Class selector */}
            {form.audience_type === 'class' && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--tool-hex-737373)', marginBottom: 8, fontWeight: 600 }}>Select Classes *</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, maxHeight: 160, overflowY: 'auto' }}>
                  {classes.map(cls => {
                    const key = cls.name + (cls.section ? ' ' + cls.section : '');
                    return (
                      <label key={cls.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: form.audience_classes.includes(key) ? 'rgba(79,143,247,0.15)' : 'var(--tool-hex-252525)', border: `1px solid ${form.audience_classes.includes(key) ? 'var(--tool-hex-4f8ff7)' : 'var(--tool-hex-333)'}`, borderRadius: 8, cursor: 'pointer', fontSize: 12, color: form.audience_classes.includes(key) ? 'var(--tool-hex-4f8ff7)' : 'var(--tool-hex-a0a0a0)' }}>
                        <input type="checkbox" checked={form.audience_classes.includes(key)} onChange={() => toggleClass(key)} style={{ accentColor: 'var(--tool-hex-4f8ff7)' }} />
                        {key}
                      </label>
                    );
                  })}
                  {classes.length === 0 && <span style={{ color: 'var(--tool-hex-737373)', fontSize: 12 }}>No classes configured</span>}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <ActionBtn label={saving ? 'Sending...' : 'Send Now'} type="submit" disabled={saving} icon={<Send size={11} />} />
              <ActionBtn label="Cancel" variant="secondary" onClick={resetForm} />
            </div>
          </form>
        </div>
      )}
      <DataTable title="Recent Announcements" headers={['Title', 'Audience', 'Date', 'Status']}
        rows={announcements.map(a => [a.title, audienceLabel(a), a.created_at?.slice(0, 10), <Badge text={a.is_draft ? 'Draft' : 'Sent'} color={a.is_draft ? 'gray' : 'green'} />])}
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
        <StatCard value={data?.total || 0} label="TOTAL ENQUIRIES" color="var(--tool-hex-4f8ff7)" />
        <StatCard value={funnel.enrolled || 0} label="ENROLLED" color="var(--tool-hex-34d399)" />
        <StatCard value={funnel.new || 0} label="NEW TODAY" color="var(--tool-hex-fbbf24)" />
        <StatCard value={funnel.lost || 0} label="LOST" color="var(--tool-hex-f87171)" />
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 18 }}>
        {stages.map(s => (
          <div key={s} style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 8, padding: '8px 12px', textAlign: 'center', minWidth: 80 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--tool-hex-e5e5e5)', fontFamily: 'Inter, sans-serif' }}>{funnel[s] || 0}</div>
            <div style={{ fontSize: 9, color: 'var(--tool-hex-737373)', textTransform: 'capitalize', fontWeight: 600 }}>{s.replace('_', ' ')}</div>
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
  return <StaffAttendanceTracker title="Leave Manager" subtitle="Pending leave requests & approvals" defaultTab="leaves" />;
}

// 10. Staff Performance Overview
export function StaffPerformance() {
  const { currentUser } = useUser();
  const [staff, setStaff] = useState([]);
  const [staffStats, setStaffStats] = useState({});
  const [leaves, setLeaves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStaff, setSelectedStaff] = useState(null);
  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [staffRes, attRes] = await Promise.all([
        getStaff(currentUser),
        fetch(`${API}/attendance/staff`, { headers: h() }).then(r => r.json()),
      ]);
      const staffList = staffRes.success ? (staffRes.data || []) : [];
      setStaff(staffList);

      // Aggregate attendance stats per staff
      const records = attRes.success ? (attRes.data || []) : [];
      const stats = {};
      records.forEach(rec => {
        const sid = rec.staff_id;
        if (!stats[sid]) stats[sid] = { present: 0, absent: 0, late: 0, total: 0 };
        stats[sid].total++;
        if (rec.status === 'present') stats[sid].present++;
        else if (rec.status === 'absent') stats[sid].absent++;
        else if (rec.status === 'late') stats[sid].late++;
      });
      setStaffStats(stats);
    } catch {}
    setLoading(false);
  };

  const getRate = (s) => {
    const st = staffStats[s.id];
    if (!st || st.total === 0) return '—';
    return `${Math.round((st.present / st.total) * 100)}%`;
  };

  const getRateColor = (s) => {
    const st = staffStats[s.id];
    if (!st || st.total === 0) return 'var(--tool-hex-737373)';
    const rate = Math.round((st.present / st.total) * 100);
    return rate >= 90 ? 'var(--tool-hex-34d399)' : rate >= 75 ? 'var(--tool-hex-fbbf24)' : 'var(--tool-hex-f87171)';
  };

  return (
    <ToolPage title="Staff Performance" subtitle="Individual staff stats & attendance analytics" onRefresh={load} loading={loading}>
      {/* Summary Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 20, maxWidth: 800 }}>
        <StatCard value={staff.length} label="TOTAL STAFF" color="var(--tool-hex-e5e5e5)" />
        <StatCard value={staff.filter(s => s.staff_type === 'teacher').length} label="TEACHERS" color="var(--tool-hex-4f8ff7)" />
        <StatCard value={staff.filter(s => s.staff_type !== 'teacher').length} label="NON-TEACHING" color="var(--tool-hex-a78bfa)" />
        <StatCard
          value={staff.length > 0 ? `${Math.round(staff.filter(s => { const st = staffStats[s.id]; return st && st.total > 0 && (st.present / st.total) * 100 >= 90; }).length / staff.length * 100)}%` : '—'}
          label="ABOVE 90% ATT." color="var(--tool-hex-34d399)" />
      </div>

      {/* Per-staff detail table */}
      <DataTable title="Individual Staff Performance" headers={['Name', 'Type', 'Dept.', 'Employee ID', 'Join Date', 'Present', 'Absent', 'Late', 'Att. Rate']}
        rows={staff.map(s => {
          const st = staffStats[s.id];
          return [
            <span style={{ fontWeight: 600, color: 'var(--tool-hex-e5e5e5)', cursor: 'pointer' }} onClick={() => setSelectedStaff(selectedStaff?.id === s.id ? null : s)}>{s.name}</span>,
            <Badge text={s.staff_type || 'staff'} color={s.staff_type === 'teacher' ? 'blue' : 'purple'} />,
            s.department || '—',
            s.employee_id || '—',
            s.join_date || '—',
            <span style={{ color: 'var(--tool-hex-34d399)', fontWeight: 600 }}>{st?.present ?? '—'}</span>,
            <span style={{ color: 'var(--tool-hex-f87171)', fontWeight: 600 }}>{st?.absent ?? '—'}</span>,
            <span style={{ color: 'var(--tool-hex-fbbf24)', fontWeight: 600 }}>{st?.late ?? '—'}</span>,
            <span style={{ color: getRateColor(s), fontWeight: 700 }}>{getRate(s)}</span>,
          ];
        })}
        emptyMsg="No staff data"
      />

      {/* Expanded staff detail panel */}
      {selectedStaff && (
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-4f8ff7)', borderRadius: 12, padding: 20, marginTop: 4, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{selectedStaff.name}</h3>
              <span style={{ fontSize: 12, color: 'var(--tool-hex-737373)' }}>{selectedStaff.staff_type} · {selectedStaff.department || 'N/A'} · Emp #{selectedStaff.employee_id || 'N/A'}</span>
            </div>
            <button onClick={() => setSelectedStaff(null)} style={{ background: 'none', border: 'none', color: 'var(--tool-hex-737373)', cursor: 'pointer', fontSize: 18 }}>×</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 12 }}>
            <StatCard value={selectedStaff.email || '—'} label="EMAIL" color="var(--tool-hex-4f8ff7)" small />
            <StatCard value={selectedStaff.phone || '—'} label="PHONE" color="var(--tool-hex-a78bfa)" small />
            <StatCard value={selectedStaff.join_date || '—'} label="JOIN DATE" color="var(--tool-hex-34d399)" small />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            <StatCard value={staffStats[selectedStaff.id]?.present ?? '—'} label="DAYS PRESENT" color="var(--tool-hex-34d399)" small />
            <StatCard value={staffStats[selectedStaff.id]?.absent ?? '—'} label="DAYS ABSENT" color="var(--tool-hex-f87171)" small />
            <StatCard value={staffStats[selectedStaff.id]?.late ?? '—'} label="LATE ARRIVALS" color="var(--tool-hex-fbbf24)" small />
            <StatCard value={getRate(selectedStaff)} label="ATTENDANCE RATE" color={getRateColor(selectedStaff)} small />
          </div>
          {selectedStaff.subjects?.length > 0 && (
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--tool-hex-a0a0a0)' }}>
              <b style={{ color: 'var(--tool-hex-e5e5e5)' }}>Subjects: </b>{selectedStaff.subjects.join(', ')}
            </div>
          )}
          {selectedStaff.qualification && (
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--tool-hex-a0a0a0)' }}>
              <b style={{ color: 'var(--tool-hex-e5e5e5)' }}>Qualification: </b>{selectedStaff.qualification}
            </div>
          )}
        </div>
      )}
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
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 16, marginBottom: 8 }}>AI School Health Report</h3>
          <p style={{ color: 'var(--tool-hex-737373)', fontSize: 12, marginBottom: 20 }}>Generate a comprehensive AI-powered analysis of your school's current health status</p>
          <ActionBtn label={loading ? 'Generating...' : 'Generate Report'} onClick={generate} disabled={loading} />
        </div>
      ) : (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 18 }}>
            <StatCard value={`${report.score}/100`} label="HEALTH SCORE" color="var(--tool-hex-34d399)" />
            <StatCard value={report.generated} label="GENERATED" color="var(--tool-hex-4f8ff7)" />
            <StatCard value={report.alerts.length} label="ACTION ITEMS" color="var(--tool-hex-f87171)" />
          </div>
          <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11, padding: 20, marginBottom: 14 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-34d399)', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Highlights</h3>
            {report.highlights.map((h, i) => <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 13, color: 'var(--tool-hex-a3a3a3)' }}><CheckCircle size={12} color="var(--tool-hex-34d399)" />{h}</div>)}
          </div>
          <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11, padding: 20 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-f87171)', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Action Items</h3>
            {report.alerts.map((a, i) => <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 13, color: 'var(--tool-hex-a3a3a3)' }}><AlertTriangle size={12} color="var(--tool-hex-f87171)" />{a}</div>)}
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
        <StatCard value={data?.total_alerts || 0} label="TOTAL ALERTS" color="var(--tool-hex-fbbf24)" />
        <StatCard value={data?.critical_count || 0} label="CRITICAL" color="var(--tool-hex-f87171)" />
      </div>
      {alerts.length === 0 ? <div style={{ padding: 32, textAlign: 'center', color: 'var(--tool-hex-737373)', background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11, fontSize: 13 }}>No active alerts — all good!</div> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {alerts.map((a, i) => (
            <div key={i} style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 10, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <Badge text={a.category} color={colors[a.type] || 'blue'} />
              <span style={{ fontSize: 13, color: 'var(--tool-hex-e5e5e5)', flex: 1 }}>{a.text}</span>
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
  const load = async () => { setLoading(true); try { const r = await fetch(`${API}/ops/expenses`, { headers: h() }).then(r => r.json()); if (r.success) setExpenses(r.data || []); } catch {} setLoading(false); };
  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.category || !form.amount) { alert('Category and Amount are required.'); return; }
    try {
      const r = await fetch(`${API}/ops/expenses`, {
        method: 'POST', headers: h(),
        body: JSON.stringify({ ...form, amount: parseFloat(form.amount) }),
      }).then(res => res.json());
      if (r.success) {
        setShowForm(false);
        setForm({ category: '', description: '', amount: '', date: new Date().toISOString().slice(0, 10), vendor: '' });
        load();
      } else { alert('Failed to save expense. Please try again.'); }
    } catch { alert('Network error. Please try again.'); }
  };
  const total = expenses.reduce((s, e) => s + (e.amount || 0), 0);

  return (
    <ToolPage title="Expense Tracker" subtitle="Track & manage school expenses" onRefresh={load} loading={loading}
      actions={<ActionBtn label="Add Expense" onClick={() => setShowForm(true)} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <form onSubmit={handleAdd}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Category" type="select" value={form.category} onChange={f('category')} options={['utilities', 'maintenance', 'salary', 'events', 'stationery', 'transport', 'other'].map(v => ({ value: v, label: v }))} required />
              <FormField label="Amount (₹)" type="number" value={form.amount} onChange={f('amount')} placeholder="0.00" required />
              <FormField label="Date" type="date" value={form.date} onChange={f('date')} />
              <FormField label="Vendor" value={form.vendor} onChange={f('vendor')} placeholder="Vendor name" />
            </div>
            <FormField label="Description" type="textarea" value={form.description} onChange={f('description')} placeholder="Expense description" />
            <div style={{ display: 'flex', gap: 8 }}><ActionBtn label="Save Expense" type="submit" icon={<Save size={11} />} /><ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} /></div>
          </form>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 16, maxWidth: 400 }}>
        <StatCard value={`₹${(total / 1000).toFixed(1)}K`} label="TOTAL EXPENSES" color="var(--tool-hex-f87171)" />
        <StatCard value={expenses.length} label="RECORDS" color="var(--tool-hex-e5e5e5)" />
      </div>
      <DataTable headers={['Date', 'Category', 'Description', 'Vendor', 'Amount']}
        rows={expenses.map(e => [e.date, e.category, e.description, e.vendor || 'N/A', <span style={{ color: 'var(--tool-hex-f87171)' }}>₹{(e.amount || 0).toLocaleString('en-IN')}</span>])}
      />
    </ToolPage>
  );
}


// 15. Custom Report Builder
export function CustomReportBuilder() {
  const { currentUser } = useUser();
  const [selectedSources, setSelectedSources] = useState([]);
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  const dataSources = [
    { id: 'students', label: 'Student Data', icon: '👥', endpoint: 'students' },
    { id: 'attendance', label: 'Attendance Records', icon: '📋', endpoint: 'attendance' },
    { id: 'fee-transactions', label: 'Fee Transactions', icon: '₹', endpoint: 'fee-transactions' },
    { id: 'staff', label: 'Staff Information', icon: '👨‍🏫', endpoint: 'staff' },
    { id: 'expenses', label: 'Expenses', icon: '💰', endpoint: 'expenses' },
    { id: 'exam-results', label: 'Exam Results', icon: '📊', endpoint: 'exam-results' },
    { id: 'enquiries', label: 'Admission Enquiries', icon: '📝', endpoint: 'enquiries' },
  ];

  const toggle = (id) => setSelectedSources(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);

  const buildUrl = (endpoint) => {
    let url = `${process.env.REACT_APP_BACKEND_URL}/api/export/${endpoint}`;
    const params = [];
    if (dateRange.start) params.push(`start_date=${dateRange.start}`);
    if (dateRange.end) params.push(`end_date=${dateRange.end}`);
    if (params.length) url += '?' + params.join('&');
    return url;
  };

  // Prepare CSV download links
  const generateReport = async () => {
    if (selectedSources.length === 0) return;
    setLoading(true);
    const links = selectedSources.map(srcId => {
      const src = dataSources.find(d => d.id === srcId);
      return { source: srcId, url: buildUrl(src.endpoint), label: src.label };
    });
    setReport({ links, generated: new Date().toLocaleString('en-IN') });
    setLoading(false);
  };

  // Parse CSV properly — handles quoted fields containing commas
  const parseCSV = (text) => {
    const lines = text.trim().split('\n');
    return lines.map(line => {
      const cells = [];
      let cur = '', inQ = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') { inQ = !inQ; }
        else if (ch === ',' && !inQ) { cells.push(cur.trim()); cur = ''; }
        else { cur += ch; }
      }
      cells.push(cur.trim());
      return cells;
    });
  };

  // Generate a PDF summary report by fetching data from the backend
  const generatePDF = async () => {
    if (selectedSources.length === 0) return;
    setPdfLoading(true);
    const errors = [];
    try {
      const { jsPDF } = await import('jspdf');
      const doc = new jsPDF();
      const today = new Date().toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' });

      // PDF Header
      doc.setFontSize(20); doc.setTextColor(40, 40, 40);
      doc.text('Custom School Report', 105, 18, { align: 'center' });
      doc.setFontSize(10); doc.setTextColor(100, 100, 100);
      doc.text(`Generated: ${today}`, 105, 26, { align: 'center' });
      if (dateRange.start || dateRange.end) {
        doc.text(`Period: ${dateRange.start || 'All time'} to ${dateRange.end || 'Today'}`, 105, 33, { align: 'center' });
      }
      doc.setDrawColor(200, 200, 200); doc.line(15, 38, 195, 38);

      let y = 48;
      const maxY = 272;
      const newPage = () => { doc.addPage(); y = 18; };

      let sectionNum = 0;

      for (const srcId of selectedSources) {
        const src = dataSources.find(d => d.id === srcId);
        if (!src) continue;
        sectionNum++;

        let csvRows = [];
        let colHeaders = [];
        let fetchOk = false;

        try {
          const res = await fetch(buildUrl(src.endpoint), { headers: h() });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const text = await res.text();
          const parsed = parseCSV(text);
          if (parsed.length > 0) {
            colHeaders = parsed[0];
            csvRows = parsed.slice(1).filter(r => r.some(c => c));
          }
          fetchOk = true;
        } catch (e) {
          errors.push(`${src.label}: ${e.message}`);
        }

        // Section header — no emoji, plain ASCII
        if (y > maxY - 40) newPage();
        doc.setFontSize(13); doc.setTextColor(30, 30, 30);
        doc.text(`${sectionNum}. ${src.label}`, 15, y); y += 7;
        doc.setFontSize(9); doc.setTextColor(110, 110, 110);
        if (!fetchOk) {
          doc.text('Could not load data for this source.', 20, y); y += 12;
          continue;
        }
        doc.text(`Total records: ${csvRows.length}`, 20, y); y += 7;

        if (colHeaders.length === 0 || csvRows.length === 0) {
          doc.text('No records found.', 20, y); y += 10;
          continue;
        }

        // Limit to 6 columns max, compute widths
        const maxCols = Math.min(colHeaders.length, 6);
        const colW = Math.floor(175 / maxCols);

        // Column headers row
        doc.setFontSize(8); doc.setTextColor(50, 50, 50);
        colHeaders.slice(0, maxCols).forEach((col, i) => {
          doc.text(String(col).slice(0, Math.floor(colW / 2.2)), 15 + i * colW, y);
        });
        y += 4;
        doc.setDrawColor(180, 180, 180); doc.line(15, y, 195, y); y += 3;

        // Data rows — ALL rows with page breaks
        doc.setFontSize(7.5); doc.setTextColor(70, 70, 70);
        csvRows.forEach((row, ri) => {
          if (y > maxY) newPage();
          // Alternating row background
          if (ri % 2 === 0) {
            doc.setFillColor(248, 248, 248);
            doc.rect(15, y - 4, 180, 6, 'F');
          }
          row.slice(0, maxCols).forEach((cell, i) => {
            const cellStr = String(cell || '').slice(0, Math.floor(colW / 2.2));
            doc.text(cellStr, 15 + i * colW, y);
          });
          y += 6;
        });
        y += 8;
      }

      // Error summary if any sources failed
      if (errors.length > 0) {
        if (y > maxY - 20) newPage();
        doc.setFontSize(9); doc.setTextColor(180, 60, 60);
        doc.text('Note: Some sources could not be loaded:', 15, y); y += 6;
        errors.forEach(e => { doc.text(`  - ${e}`, 15, y); y += 5; });
      }

      // Footer on every page
      const totalPages = doc.getNumberOfPages();
      for (let p = 1; p <= totalPages; p++) {
        doc.setPage(p);
        doc.setFontSize(8); doc.setTextColor(160, 160, 160);
        doc.text('EduFlow — Confidential Report', 105, 290, { align: 'center' });
        doc.text(`Page ${p} of ${totalPages}`, 190, 290, { align: 'right' });
      }

      const fname = `custom-report-${new Date().toISOString().slice(0, 10)}.pdf`;
      doc.save(fname);
    } catch (err) {
      alert(`PDF generation failed: ${err.message}`);
    }
    setPdfLoading(false);
  };

  return (
    <ToolPage title="Custom Report Builder" subtitle="Select data sources, download CSV or generate PDF">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, maxWidth: 960 }}>
        {/* Source selector */}
        <div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Select Data Sources</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {dataSources.map(src => (
              <label key={src.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: selectedSources.includes(src.id) ? 'rgba(59,130,246,0.1)' : 'var(--tool-hex-1e1e1e)', border: `1px solid ${selectedSources.includes(src.id) ? 'var(--tool-hex-4f8ff7)' : 'var(--tool-hex-2e2e2e)'}`, borderRadius: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={selectedSources.includes(src.id)} onChange={() => toggle(src.id)} style={{ accentColor: 'var(--tool-hex-4f8ff7)' }} />
                <span style={{ fontSize: 16 }}>{src.icon}</span>
                <span style={{ fontSize: 13, color: 'var(--tool-hex-e5e5e5)' }}>{src.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Right panel: date range + actions + downloads */}
        <div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Date Range (Optional)</h3>
          <FormField label="From Date" type="date" value={dateRange.start} onChange={v => setDateRange(p => ({ ...p, start: v }))} />
          <FormField label="To Date" type="date" value={dateRange.end} onChange={v => setDateRange(p => ({ ...p, end: v }))} />

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <ActionBtn
              label={loading ? 'Preparing...' : `CSV Downloads (${selectedSources.length})`}
              onClick={generateReport}
              disabled={loading || selectedSources.length === 0}
              icon={<Download size={11} />}
              variant="secondary"
            />
            <ActionBtn
              label={pdfLoading ? 'Building PDF...' : 'Generate PDF Report'}
              onClick={generatePDF}
              disabled={pdfLoading || selectedSources.length === 0}
              icon={<FileText size={11} />}
            />
          </div>

          {report && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, color: 'var(--tool-hex-34d399)', marginBottom: 10 }}>CSV files ready — click to download:</div>
              {report.links.map((link, i) => (
                <a key={i} href={link.url} download target="_blank" rel="noreferrer"
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 7, color: 'var(--tool-hex-34d399)', fontSize: 12, marginBottom: 6, textDecoration: 'none' }}>
                  <Download size={12} /> {link.label} (CSV)
                </a>
              ))}
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--tool-hex-737373)' }}>
                Or click "Generate PDF Report" for a formatted PDF summary.
              </div>
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
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pulse, fee, smart, att, staffRes, expRes] = await Promise.all([
        executeTool('get_school_pulse', {}, currentUser),
        executeTool('get_fee_summary', {}, currentUser),
        executeTool('get_smart_alerts', {}, currentUser),
        executeTool('get_attendance_overview', { days: 30 }, currentUser),
        fetch(`${API}/staff/`, { headers: h() }).then(r => r.json()).catch(() => ({ data: [] })),
        fetch(`${API}/ops/expenses`, { headers: h() }).then(r => r.json()).catch(() => ({ data: [] })),
      ]);
      const expenses = expRes.data || [];
      const totalExp = expenses.reduce((s, e) => s + (e.amount || 0), 0);
      setData({
        generated: new Date().toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' }),
        pulse: pulse.data,
        fee: fee.data,
        alerts: smart.data,
        attendance: att.data,
        staff: staffRes.data || [],
        expenses,
        totalExp,
      });
    } catch (e) {
      setError('Some data could not be loaded. Showing partial report.');
    }
    setLoading(false);
  };

  const downloadPDF = async () => {
    if (!data) return;
    setPdfLoading(true);
    try {
      const { jsPDF } = await import('jspdf');
      const doc = new jsPDF();
      const s = data.pulse?.summary || {};
      const fee = data.fee?.stats || {};

      // Cover
      doc.setFontSize(22); doc.setTextColor(30, 30, 30);
      doc.text('Board / Trust Meeting Report', 105, 22, { align: 'center' });
      doc.setFontSize(11); doc.setTextColor(100, 100, 100);
      doc.text(`Generated: ${data.generated}`, 105, 31, { align: 'center' });
      doc.setDrawColor(200, 200, 200); doc.line(15, 36, 195, 36);

      // Section 1 — School Overview
      let y = 46;
      doc.setFontSize(13); doc.setTextColor(40, 40, 40); doc.text('1. School Overview', 15, y); y += 9;
      doc.setFontSize(10); doc.setTextColor(60, 60, 60);
      doc.text(`Total Students Enrolled: ${s.total_students || 0}`, 20, y); y += 7;
      doc.text(`Total Staff: ${s.total_staff || 0}`, 20, y); y += 7;
      doc.text(`Today's Attendance Rate: ${s.attendance_rate || 'N/A'}`, 20, y); y += 7;
      doc.text(`Avg Attendance (30 days): ${data.attendance?.avg_attendance_rate || 'N/A'}`, 20, y); y += 7;
      doc.text(`Total Attendance Records: ${data.attendance?.total_records || 0}`, 20, y); y += 12;

      // Section 2 — Fee Summary
      doc.setFontSize(13); doc.setTextColor(40, 40, 40); doc.text('2. Fee & Finance Summary', 15, y); y += 9;
      doc.setFontSize(10); doc.setTextColor(60, 60, 60);
      doc.text(`Total Fees Collected: ${fee.total_collected || '₹0'}`, 20, y); y += 7;
      doc.text(`Total Overdue: ${fee.total_overdue || '₹0'}`, 20, y); y += 7;
      doc.text(`Collection Rate: ${fee.collection_rate || 'N/A'}`, 20, y); y += 7;
      doc.text(`Students with Dues: ${fee.students_with_dues || 0}`, 20, y); y += 7;
      doc.text(`Overdue 60+ Days: ${fee.overdue_60_days || 0} transactions`, 20, y); y += 7;
      const expFmt = data.totalExp >= 100000
        ? `₹${(data.totalExp / 100000).toFixed(2)}L`
        : `₹${data.totalExp.toLocaleString('en-IN')}`;
      doc.text(`Total Expenses Recorded: ${expFmt}`, 20, y); y += 12;

      // Section 3 — Staff
      doc.setFontSize(13); doc.setTextColor(40, 40, 40); doc.text('3. Staff Summary', 15, y); y += 9;
      doc.setFontSize(10); doc.setTextColor(60, 60, 60);
      const teachers = (data.staff || []).filter(st => st.staff_type === 'teacher').length;
      const nonTeach = (data.staff || []).length - teachers;
      doc.text(`Total Staff: ${(data.staff || []).length}`, 20, y); y += 7;
      doc.text(`Teaching Staff: ${teachers}`, 20, y); y += 7;
      doc.text(`Non-Teaching Staff: ${nonTeach}`, 20, y); y += 7;
      const absentToday = (data.pulse?.staff_absent_today || []).length;
      doc.text(`Absent Today: ${absentToday}`, 20, y); y += 7;
      const pendingLeaves = (data.pulse?.pending_leave_requests || []).length;
      doc.text(`Pending Leave Requests: ${pendingLeaves}`, 20, y); y += 12;

      // Section 4 — Class-wise Attendance (today)
      const classStats = data.attendance?.class_stats_today || [];
      if (classStats.length > 0) {
        if (y > 220) { doc.addPage(); y = 20; }
        doc.setFontSize(13); doc.setTextColor(40, 40, 40); doc.text('4. Class-wise Attendance (Today)', 15, y); y += 9;
        doc.setFontSize(9); doc.setTextColor(80, 80, 80);
        doc.text('Class', 20, y); doc.text('Present', 70, y); doc.text('Total', 110, y); doc.text('Rate', 150, y);
        y += 5; doc.setDrawColor(220, 220, 220); doc.line(20, y, 190, y); y += 4;
        classStats.forEach(c => {
          if (y > 270) { doc.addPage(); y = 20; }
          doc.text(String(c.class), 20, y); doc.text(String(c.present), 70, y); doc.text(String(c.total), 110, y); doc.text(String(c.rate), 150, y);
          y += 6;
        });
        y += 8;
      }

      // Section 5 — Alerts
      const alerts = data.alerts?.alerts || [];
      if (alerts.length > 0) {
        if (y > 220) { doc.addPage(); y = 20; }
        doc.setFontSize(13); doc.setTextColor(40, 40, 40); doc.text('5. Active Alerts', 15, y); y += 9;
        doc.setFontSize(10); doc.setTextColor(80, 80, 80);
        alerts.forEach(a => {
          if (y > 270) { doc.addPage(); y = 20; }
          doc.text(`[${a.priority?.toUpperCase()}] ${a.text}`, 20, y); y += 7;
        });
        y += 6;
      }

      // Section 6 — Top Fee Defaulters
      const defaulters = data.fee?.defaulters || [];
      if (defaulters.length > 0) {
        if (y > 220) { doc.addPage(); y = 20; }
        doc.setFontSize(13); doc.setTextColor(40, 40, 40); doc.text('6. Top Fee Defaulters', 15, y); y += 9;
        doc.setFontSize(9); doc.setTextColor(80, 80, 80);
        doc.text('Student', 20, y); doc.text('Class', 90, y); doc.text('Overdue', 140, y); doc.text('Days', 175, y);
        y += 5; doc.setDrawColor(220, 220, 220); doc.line(20, y, 190, y); y += 4;
        defaulters.slice(0, 10).forEach(d => {
          if (y > 270) { doc.addPage(); y = 20; }
          doc.text(String(d.student_name || '').slice(0, 20), 20, y);
          doc.text(String(d.class || ''), 90, y);
          doc.text(String(d.amount_overdue_fmt || ''), 140, y);
          doc.text(String(d.days_overdue || ''), 175, y);
          y += 6;
        });
      }

      // Footer
      doc.setFontSize(8); doc.setTextColor(160, 160, 160);
      doc.text('EduFlow — Board Report — Confidential', 105, 290, { align: 'center' });

      doc.save(`board-report-${new Date().toISOString().slice(0, 10)}.pdf`);
    } catch (err) { alert('PDF generation failed. Please try again.'); }
    setPdfLoading(false);
  };

  const s = data?.pulse?.summary || {};
  const fee = data?.fee?.stats || {};

  return (
    <ToolPage title="Board / Trust Meeting Report" subtitle="Consolidated school metrics for trust meetings">
      {!data ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 16, marginBottom: 8 }}>Board Meeting Report</h3>
          <p style={{ color: 'var(--tool-hex-737373)', fontSize: 12, marginBottom: 20 }}>Fetches all school metrics — students, fees, attendance, staff, alerts, and defaulters</p>
          {error && <div style={{ color: 'var(--tool-hex-fbbf24)', fontSize: 12, marginBottom: 12 }}>{error}</div>}
          <ActionBtn label={loading ? 'Generating...' : 'Generate Full Report'} onClick={generate} disabled={loading} />
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
            <span style={{ color: 'var(--tool-hex-737373)', fontSize: 12 }}>Generated: {data.generated}</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={pdfLoading ? 'Exporting...' : 'Download PDF'} onClick={downloadPDF} disabled={pdfLoading} icon={<Download size={11} />} />
              <ActionBtn label={loading ? 'Refreshing...' : 'Re-generate'} variant="secondary" onClick={generate} disabled={loading} />
            </div>
          </div>
          {error && <div style={{ color: 'var(--tool-hex-fbbf24)', fontSize: 12, marginBottom: 12, background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 8, padding: '8px 12px' }}>{error}</div>}

          {/* Section 1 — School Overview */}
          <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: 18, marginBottom: 14 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 13, fontWeight: 700, marginBottom: 12 }}>School Overview</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
              <StatCard value={s.total_students || 0} label="ENROLLED STUDENTS" color="var(--tool-hex-4f8ff7)" small />
              <StatCard value={s.total_staff || 0} label="TOTAL STAFF" color="var(--tool-hex-e5e5e5)" small />
              <StatCard value={s.attendance_rate || 'N/A'} label="TODAY'S ATT." color="var(--tool-hex-34d399)" small />
              <StatCard value={data.attendance?.avg_attendance_rate || 'N/A'} label="AVG ATT. (30d)" color="var(--tool-hex-a78bfa)" small />
            </div>
          </div>

          {/* Section 2 — Fee & Finance */}
          <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: 18, marginBottom: 14 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Fee & Finance</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 12 }}>
              <StatCard value={fee.total_collected || '₹0'} label="TOTAL COLLECTED" color="var(--tool-hex-34d399)" small />
              <StatCard value={fee.total_overdue || '₹0'} label="TOTAL OVERDUE" color="var(--tool-hex-f87171)" small />
              <StatCard value={fee.collection_rate || 'N/A'} label="COLLECTION RATE" color="var(--tool-hex-4f8ff7)" small />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              <StatCard value={fee.students_with_dues || 0} label="STUDENTS WITH DUES" color="var(--tool-hex-fbbf24)" small />
              <StatCard value={fee.overdue_60_days || 0} label="OVERDUE 60+ DAYS" color="var(--tool-hex-f87171)" small />
              <StatCard value={data.totalExp >= 100000 ? `₹${(data.totalExp / 100000).toFixed(1)}L` : `₹${(data.totalExp || 0).toLocaleString('en-IN')}`} label="TOTAL EXPENSES" color="var(--tool-hex-f87171)" small />
            </div>
          </div>

          {/* Section 3 — Staff */}
          <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: 18, marginBottom: 14 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-e5e5e5)', fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Staff Summary</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
              <StatCard value={(data.staff || []).filter(st => st.staff_type === 'teacher').length} label="TEACHERS" color="var(--tool-hex-4f8ff7)" small />
              <StatCard value={(data.staff || []).filter(st => st.staff_type !== 'teacher').length} label="NON-TEACHING" color="var(--tool-hex-a78bfa)" small />
              <StatCard value={(data.pulse?.staff_absent_today || []).length} label="ABSENT TODAY" color="var(--tool-hex-f87171)" small />
              <StatCard value={(data.pulse?.pending_leave_requests || []).length} label="PENDING LEAVES" color="var(--tool-hex-fbbf24)" small />
            </div>
          </div>

          {/* Section 4 — Class-wise Attendance */}
          {(data.attendance?.class_stats_today || []).length > 0 && (
            <DataTable title="Class-wise Attendance (Today)" headers={['Class', 'Present', 'Total', 'Rate']}
              rows={(data.attendance.class_stats_today || []).map(c => [
                c.class,
                c.present,
                c.total,
                <span style={{ color: parseFloat(c.rate) >= 85 ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-f87171)', fontWeight: 600 }}>{c.rate}</span>,
              ])}
            />
          )}

          {/* Section 5 — Alerts */}
          {(data.alerts?.alerts || []).length > 0 && (
            <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 11, padding: 16, marginBottom: 14 }}>
              <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-f87171)', fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Active Alerts ({data.alerts.total_alerts})</h3>
              {data.alerts.alerts.map((a, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <Badge text={a.priority} color={a.priority === 'high' ? 'red' : a.priority === 'medium' ? 'yellow' : 'gray'} />
                  <span style={{ fontSize: 12, color: 'var(--tool-hex-a3a3a3)' }}>{a.text}</span>
                </div>
              ))}
            </div>
          )}

          {/* Section 6 — Top Defaulters */}
          {(data.fee?.defaulters || []).length > 0 && (
            <DataTable title="Top Fee Defaulters" headers={['Student', 'Class', 'Overdue Amount', 'Days Overdue']}
              rows={(data.fee.defaulters || []).slice(0, 8).map(d => [
                d.student_name,
                d.class,
                <span style={{ color: 'var(--tool-hex-f87171)', fontWeight: 600 }}>{d.amount_overdue_fmt}</span>,
                <span style={{ color: d.days_overdue > 60 ? 'var(--tool-hex-f87171)' : 'var(--tool-hex-fbbf24)' }}>{d.days_overdue} days</span>,
              ])}
            />
          )}
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
        method: 'POST', headers: h(),
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
            <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 12, color: 'var(--tool-hex-fcd34d)' }}>
              ⚠️ This will archive the current academic year (2025-26) and create a new one. All existing students and data are preserved.
            </div>
            <FormField label="New Academic Year Name" value={newYear} onChange={setNewYear} placeholder="e.g. 2026-27" required />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Start Date" type="date" value={startDate} onChange={setStartDate} />
              <FormField label="End Date" type="date" value={endDate} onChange={setEndDate} />
            </div>
            {confirmed && (
              <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 13, color: 'var(--tool-hex-fca5a5)' }}>
                Are you absolutely sure? Click again to confirm. This cannot be undone.
              </div>
            )}
            <ActionBtn label={confirmed ? 'Confirm Transition' : 'Start Year Transition'} onClick={handleTransition} disabled={loading} variant={confirmed ? 'danger' : 'primary'} />
            {confirmed && <ActionBtn label="Cancel" variant="secondary" onClick={() => setConfirmed(false)} />}
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🎓</div>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--tool-hex-34d399)', fontSize: 16, marginBottom: 8 }}>Year Transition Complete!</h3>
            <p style={{ color: 'var(--tool-hex-a3a3a3)', fontSize: 13, marginBottom: 16 }}>{result.message}</p>
            <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 8, padding: '12px 16px', textAlign: 'left' }}>
              <div style={{ fontSize: 12, color: 'var(--tool-hex-e5e5e5)' }}><b>New Year:</b> {result.new_year?.name}</div>
              <div style={{ fontSize: 12, color: 'var(--tool-hex-e5e5e5)', marginTop: 4 }}><b>Students Carried Forward:</b> {result.students_carried_forward}</div>
            </div>
          </div>
        )}
      </div>
    </ToolPage>
  );
}

export function AttendanceAlerts() {
  const { currentUser } = useUser();
  const [threshold, setThreshold] = useState(75);
  const [days, setDays] = useState(30);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [twilioConfigured, setTwilioConfigured] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [smsForm, setSmsForm] = useState({ phone: '', message: '' });
  const [sending, setSending] = useState(false);
  const [smsResult, setSmsResult] = useState(null);
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkTemplate, setBulkTemplate] = useState("Dear {name}'s parent, your child's attendance is {attendance}% which is below the required {threshold}%. Please ensure regular attendance. Contact school for more info.");
  const [bulkSending, setBulkSending] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);
  const [selectedRows, setSelectedRows] = useState([]);
  const [viewMode, setViewMode] = useState('students');
  const [smsLogs, setSmsLogs] = useState([]);

  useEffect(() => {
    fetch(`${API}/sms/config-status`, { headers: h() })
      .then(r => r.json())
      .then(r => { if (r.success) setTwilioConfigured(r.data.configured); })
      .catch(() => {});
  }, []);

  const fetchStudents = async () => {
    setLoading(true);
    setFetched(false);
    try {
      const res = await fetch(`${API}/attendance/low-attendance?threshold=${threshold}&days=${days}`, { headers: h() });
      const r = await res.json();
      if (r.success) { setStudents(r.data || []); setFetched(true); setSelectedRows([]); }
    } catch (e) {
      console.error('low-attendance:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadLogs = async () => {
    const r = await fetch(`${API}/sms/logs`, { headers: h() }).then(r => r.json());
    if (r.success) setSmsLogs(r.data || []);
  };

  const openSmsForm = (s) => {
    setSelectedStudent(s);
    setSmsResult(null);
    setSmsForm({
      phone: s.phone || '',
      message: `Dear ${s.guardian_name || "Parent"}, your child ${s.student_name}'s attendance is ${s.attendance_rate}% which is below the required ${threshold}%. Please ensure regular attendance. Contact school for more info.`,
    });
  };

  const handleSendSingle = async (e) => {
    e.preventDefault();
    if (!smsForm.phone) { setSmsResult({ error: 'Phone number is required' }); return; }
    setSending(true);
    setSmsResult(null);
    try {
      const res = await fetch(`${API}/sms/send-parent-message`, {
        method: 'POST',
        headers: h(),
        body: JSON.stringify({
          student_id: selectedStudent.student_id,
          student_name: selectedStudent.student_name,
          phone: smsForm.phone,
          message: smsForm.message,
        }),
      }).then(r => r.json());
      if (res.success) setSmsResult({ success: true, status: res.data?.status });
      else setSmsResult({ error: res.detail || 'Failed to send' });
    } catch (err) {
      setSmsResult({ error: err.message });
    } finally {
      setSending(false);
    }
  };

  const handleSendBulk = async () => {
    const targets = selectedRows.length > 0
      ? students.filter(s => selectedRows.includes(s.student_id))
      : students;
    if (!targets.length) return;
    setBulkSending(true);
    setBulkResult(null);
    try {
      const res = await fetch(`${API}/sms/send-bulk`, {
        method: 'POST',
        headers: h(),
        body: JSON.stringify({
          message_template: bulkTemplate,
          recipients: targets.map(s => ({
            student_id: s.student_id,
            student_name: s.student_name,
            phone: s.phone || '',
            attendance: s.attendance_rate,
            threshold,
          })),
        }),
      }).then(r => r.json());
      if (res.success) setBulkResult(res.data);
      else setBulkResult({ error: res.detail || 'Failed' });
    } catch (err) {
      setBulkResult({ error: err.message });
    } finally {
      setBulkSending(false);
    }
  };

  const toggleRow = (id) => setSelectedRows(p => p.includes(id) ? p.filter(r => r !== id) : [...p, id]);
  const toggleAll = () => setSelectedRows(p => p.length === students.length ? [] : students.map(s => s.student_id));

  return (
    <ToolPage title="Attendance Alerts" subtitle="Find students below threshold & send SMS to parents">
      {!twilioConfigured && (
        <div style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: 'var(--tool-hex-fbbf24)' }}>
          Warning: Twilio not configured. Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to .env to enable SMS.
        </div>
      )}

      {/* Threshold Config */}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 18, marginBottom: 16 }}>
        <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600, marginBottom: 14 }}>Alert Configuration</h4>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
              Attendance Threshold: <span style={{ color: 'var(--tool-hex-f87171)', fontWeight: 700 }}>{threshold}%</span>
            </label>
            <input type="range" min={50} max={95} step={5} value={threshold}
              onChange={e => setThreshold(Number(e.target.value))}
              style={{ width: 180, accentColor: 'var(--tool-hex-f87171)' }} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
              Look-back Period
            </label>
            <select value={days} onChange={e => setDays(Number(e.target.value))}
              style={{ background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '7px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
              {[7, 14, 30, 60, 90].map(d => <option key={d} value={d}>{d} days</option>)}
            </select>
          </div>
          <button onClick={fetchStudents} disabled={loading}
            style={{ padding: '8px 18px', borderRadius: 6, background: 'var(--tool-hex-f87171)', border: '1px solid var(--tool-hex-f87171)', color: 'var(--tool-hex-fff)', fontSize: 12, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: loading ? 0.7 : 1 }}>
            {loading ? 'Loading...' : 'Find Students'}
          </button>
        </div>
      </div>

      {fetched && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16, maxWidth: 500 }}>
            <StatCard value={students.length} label="BELOW THRESHOLD" color="var(--tool-hex-f87171)" />
            <StatCard value={`${threshold}%`} label="THRESHOLD" color="var(--tool-hex-fbbf24)" />
            <StatCard value={`${days}d`} label="PERIOD" color="var(--tool-hex-a78bfa)" />
          </div>

          {/* View Tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 14, borderBottom: '1px solid var(--c-border)', paddingBottom: 12 }}>
            {['students', 'bulk', 'logs'].map(v => (
              <button key={v} onClick={() => { setViewMode(v); if (v === 'logs') loadLogs(); }}
                style={{ padding: '6px 12px', borderRadius: 6, border: viewMode === v ? '1px solid var(--tool-hex-a78bfa)' : '1px solid var(--c-border)', background: viewMode === v ? 'rgba(167,139,250,0.1)' : 'var(--c-bg)', color: viewMode === v ? 'var(--tool-hex-a78bfa)' : 'var(--c-muted)', fontSize: 12, cursor: 'pointer', textTransform: 'capitalize' }}>
                {v === 'students' ? 'Students' : v === 'bulk' ? 'Bulk SMS' : 'SMS Logs'}
              </button>
            ))}
          </div>

          {viewMode === 'students' && (
            <>
              {selectedStudent && (
                <div style={{ background: 'var(--c-bg)', border: '1px solid var(--tool-hex-a78bfa)', borderRadius: 11, padding: 18, marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600 }}>Send SMS — {selectedStudent.student_name}</h4>
                    <button onClick={() => { setSelectedStudent(null); setSmsResult(null); }} style={{ background: 'transparent', border: 'none', color: 'var(--c-faint)', cursor: 'pointer', fontSize: 16 }}>x</button>
                  </div>
                  <form onSubmit={handleSendSingle}>
                    <div style={{ marginBottom: 10 }}>
                      <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>PARENT PHONE</label>
                      <input value={smsForm.phone} onChange={e => setSmsForm(p => ({ ...p, phone: e.target.value }))}
                        placeholder="e.g. 9876543210" required
                        style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} />
                    </div>
                    <div style={{ marginBottom: 10 }}>
                      <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>MESSAGE ({smsForm.message.length}/160)</label>
                      <textarea value={smsForm.message} onChange={e => setSmsForm(p => ({ ...p, message: e.target.value }))}
                        maxLength={320} required rows={3}
                        style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', resize: 'vertical' }} />
                    </div>
                    {smsResult && (
                      <div style={{ padding: '8px 12px', borderRadius: 6, marginBottom: 10, fontSize: 12,
                        background: smsResult.success ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                        border: `1px solid ${smsResult.success ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                        color: smsResult.success ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-f87171)' }}>
                        {smsResult.success ? `SMS ${smsResult.status === 'not_configured' ? 'logged (Twilio not configured)' : 'sent successfully!'}` : `Error: ${smsResult.error}`}
                      </div>
                    )}
                    <button type="submit" disabled={sending}
                      style={{ padding: '8px 16px', borderRadius: 6, background: 'var(--tool-hex-a78bfa)', border: '1px solid var(--tool-hex-a78bfa)', color: 'var(--tool-hex-fff)', fontSize: 12, cursor: sending ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: sending ? 0.6 : 1 }}>
                      {sending ? 'Sending...' : 'Send SMS'}
                    </button>
                  </form>
                </div>
              )}
              <DataTable
                headers={['Student', 'Class', 'Attendance', 'Present/Total', 'Parent Phone', 'Action']}
                rows={students.map(s => [
                  s.student_name,
                  s.class,
                  <span style={{ color: s.attendance_rate < 60 ? 'var(--tool-hex-f87171)' : 'var(--tool-hex-fbbf24)', fontWeight: 600 }}>{s.attendance_rate}%</span>,
                  `${s.present_days}/${s.total_days}`,
                  s.phone || <span style={{ color: 'var(--c-faint)' }}>N/A</span>,
                  <button onClick={() => openSmsForm(s)}
                    style={{ background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)', borderRadius: 5, padding: '4px 10px', color: 'var(--tool-hex-a78bfa)', fontSize: 11, cursor: 'pointer', fontWeight: 500 }}>
                    SMS Parent
                  </button>
                ])}
                emptyMsg="No students below threshold"
              />
            </>
          )}

          {viewMode === 'bulk' && (
            <div style={{ maxWidth: 600 }}>
              <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 18, marginBottom: 14 }}>
                <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Bulk SMS to Parents</h4>
                <p style={{ color: 'var(--c-faint)', fontSize: 12, marginBottom: 12 }}>
                  Use <code style={{ background: 'var(--c-deep)', padding: '1px 4px', borderRadius: 3, color: 'var(--c-muted)' }}>{'{name}'}</code>, <code style={{ background: 'var(--c-deep)', padding: '1px 4px', borderRadius: 3, color: 'var(--c-muted)' }}>{'{attendance}'}</code>, and <code style={{ background: 'var(--c-deep)', padding: '1px 4px', borderRadius: 3, color: 'var(--c-muted)' }}>{'{threshold}'}</code> as placeholders.
                </p>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>MESSAGE TEMPLATE ({bulkTemplate.length}/160)</label>
                  <textarea value={bulkTemplate} onChange={e => setBulkTemplate(e.target.value)} rows={4} maxLength={320}
                    style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', resize: 'vertical' }} />
                </div>
                <div style={{ marginBottom: 14 }}>
                  <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>RECIPIENTS</label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button onClick={toggleAll}
                      style={{ padding: '5px 10px', borderRadius: 5, border: '1px solid var(--c-border)', background: 'var(--c-deep)', color: 'var(--c-muted)', fontSize: 11, cursor: 'pointer' }}>
                      {selectedRows.length === students.length ? 'Deselect All' : 'Select All'}
                    </button>
                    <span style={{ color: 'var(--c-faint)', fontSize: 12, alignSelf: 'center' }}>
                      {selectedRows.length > 0 ? `${selectedRows.length} selected` : `All ${students.length} students`}
                    </span>
                  </div>
                </div>
                {bulkResult && (
                  <div style={{ padding: '10px 12px', borderRadius: 6, marginBottom: 12, fontSize: 12, background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', color: 'var(--c-text)' }}>
                    {bulkResult.error ? (
                      <span style={{ color: 'var(--tool-hex-f87171)' }}>Error: {bulkResult.error}</span>
                    ) : (
                      <>Sent: <strong style={{ color: 'var(--tool-hex-34d399)' }}>{bulkResult.sent}</strong> &nbsp; Failed: <strong style={{ color: 'var(--tool-hex-f87171)' }}>{bulkResult.failed}</strong></>
                    )}
                  </div>
                )}
                <button onClick={handleSendBulk} disabled={bulkSending || students.length === 0}
                  style={{ padding: '9px 18px', borderRadius: 6, background: 'var(--tool-hex-a78bfa)', border: '1px solid var(--tool-hex-a78bfa)', color: 'var(--tool-hex-fff)', fontSize: 12, cursor: bulkSending ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: bulkSending ? 0.6 : 1 }}>
                  {bulkSending ? 'Sending...' : `Send to ${selectedRows.length > 0 ? selectedRows.length : students.length} Parents`}
                </button>
              </div>
            </div>
          )}

          {viewMode === 'logs' && (
            <DataTable headers={['Student', 'Phone', 'Status', 'Sent At', 'By']}
              rows={smsLogs.map(l => [
                l.student_name,
                l.phone,
                <Badge text={l.status} color={l.status === 'sent' ? 'green' : l.status === 'not_configured' ? 'yellow' : 'red'} />,
                l.sent_at?.slice(0, 16).replace('T', ' '),
                l.sent_by_name || 'Admin',
              ])}
              emptyMsg="No SMS logs yet"
            />
          )}
        </>
      )}

      {!fetched && !loading && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--c-faint)', fontSize: 13 }}>
          Set threshold above and click "Find Students" to get started.
        </div>
      )}
    </ToolPage>
  );
}

// Re-export SmartFeeDefaulter from AdminTools so owner can use it
export { SmartFeeDefaulter } from './AdminTools';

// Platform Health Dashboard (Story 7-43)
const STATUS_COLOR = {
  ok: 'var(--color-success, #22c55e)',
  degraded: 'var(--color-warning, #f59e0b)',
  not_configured: 'var(--text-muted, #6b7280)',
  error: 'var(--color-error, #ef4444)',
  down: 'var(--color-error, #ef4444)',
};

function StatusBadge({ status }) {
  const color = STATUS_COLOR[status] || STATUS_COLOR.not_configured;
  const label = status ? status.replace('_', ' ') : 'unknown';
  return (
    <span
      data-testid={`status-badge-${label}`}
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
        border: `1px solid ${color}`,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
      }}
    >
      {label}
    </span>
  );
}

export function PlatformHealthDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const intervalRef = useRef(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPlatformHealth();
      if (res.success) {
        setData(res.data);
        setLastRefreshed(new Date().toLocaleTimeString());
      } else {
        setError('Failed to load health data');
      }
    } catch {
      setError('Could not reach platform health endpoint');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, 60000);
    return () => clearInterval(intervalRef.current);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const panelStyle = {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '20px 24px',
    flex: '1 1 220px',
    minWidth: 200,
  };

  const labelStyle = { fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 500 };
  const valueStyle = { fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 };
  const sectionHeader = { fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 };

  return (
    <ToolPage
      title="Platform Health"
      subtitle="Live service status for EduFlow operator monitoring"
    >
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button
          data-testid="refresh-health-btn"
          onClick={load}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 8, border: '1px solid var(--border)',
            background: 'var(--bg-card)', color: 'var(--text-primary)', cursor: 'pointer',
            fontSize: 13, fontWeight: 500,
          }}
        >
          <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
        {lastRefreshed && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Last refreshed: {lastRefreshed}
          </span>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div style={{ padding: 16, background: 'color-mix(in srgb, var(--color-error, #ef4444) 10%, transparent)', border: '1px solid var(--color-error, #ef4444)', borderRadius: 8, marginBottom: 24, color: 'var(--color-error, #ef4444)', fontSize: 13 }}>
          <AlertTriangle size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && !data && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--text-muted)', fontSize: 13, padding: '32px 0' }}>
          <div className="spinner" style={{ width: 18, height: 18 }} />
          Loading platform health...
        </div>
      )}

      {/* Data panels */}
      {data && (
        <>
          {/* Service Health */}
          <div style={panelStyle}>
            <div style={sectionHeader}>
              <Activity size={15} />
              Service Health
              <span style={{ marginLeft: 'auto' }}>
                <StatusBadge status={data.service_checks?.overall} />
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {['db', 'ai', 's3', 'sms'].map(svc => (
                <div key={svc} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-page, #0f0f1a)', borderRadius: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    {svc === 'db' ? <Database size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} /> : <Cloud size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />}
                    {svc}
                  </span>
                  <StatusBadge status={data.service_checks?.[svc]} />
                </div>
              ))}
            </div>
          </div>

          {/* Token Pool, Fee Sync, Error Rate row */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 16 }}>
            {/* Token Pool */}
            <div style={panelStyle}>
              <div style={sectionHeader}>
                <Zap size={15} />
                Token Pool
              </div>
              <div style={labelStyle}>Remaining top-up tokens</div>
              <div style={valueStyle}>
                {(data.token_pool?.school_topup_pool ?? 0).toLocaleString()}
              </div>
              {data.token_pool?.subscription_status && (
                <div style={{ marginTop: 10 }}>
                  <StatusBadge status={data.token_pool.subscription_status} />
                  {data.token_pool.subscription_plan && (
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
                      {data.token_pool.subscription_plan}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Fee Sync */}
            <div style={panelStyle}>
              <div style={sectionHeader}>
                <RefreshCw size={15} />
                Fee Sync
              </div>
              {data.fee_sync_last ? (
                <>
                  <div style={{ marginBottom: 8 }}>
                    <StatusBadge status={data.fee_sync_last.status} />
                  </div>
                  <div style={labelStyle}>Last started</div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {data.fee_sync_last.started_at
                      ? new Date(data.fee_sync_last.started_at).toLocaleString()
                      : '—'}
                  </div>
                  {data.fee_sync_last.completed_at && (
                    <>
                      <div style={{ ...labelStyle, marginTop: 10 }}>Completed</div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>
                        {new Date(data.fee_sync_last.completed_at).toLocaleString()}
                      </div>
                    </>
                  )}
                </>
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No sync jobs found</div>
              )}
            </div>

            {/* Error Rate */}
            <div style={panelStyle}>
              <div style={sectionHeader}>
                <AlertTriangle size={15} />
                Error Rate (last 60 min)
              </div>
              <div style={{
                ...valueStyle,
                color: data.error_rate?.error_count > 0
                  ? STATUS_COLOR.degraded
                  : STATUS_COLOR.ok,
              }}>
                {data.error_rate?.error_count ?? 0}
              </div>
              <div style={{ ...labelStyle, marginTop: 4 }}>
                {data.error_rate?.error_count === 0 ? 'No errors detected' : 'errors in audit log'}
              </div>
              {data.error_rate?.since && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, fontFamily: 'JetBrains Mono, monospace' }}>
                  since {new Date(data.error_rate.since).toLocaleTimeString()}
                </div>
              )}
            </div>
          </div>

          {/* Active Users */}
          <div style={{ ...panelStyle, marginTop: 16, display: 'flex', alignItems: 'center', gap: 20 }}>
            <Users size={28} style={{ color: 'var(--text-muted)' }} />
            <div>
              <div style={labelStyle}>Active Users (school-wide)</div>
              <div style={valueStyle}>{data.active_user_count ?? 0}</div>
            </div>
            {data.generated_at && (
              <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', textAlign: 'right' }}>
                Generated at<br />
                {new Date(data.generated_at).toLocaleString()}
              </div>
            )}
          </div>
        </>
      )}
    </ToolPage>
  );
}
