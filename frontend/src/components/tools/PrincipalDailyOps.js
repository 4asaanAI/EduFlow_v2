import React, { useCallback, useEffect, useState } from 'react';
import {
  CalendarDays, CheckCircle, XCircle, UserCheck, IndianRupee,
  BookOpen, Users, ClipboardList, Award, AlertCircle, RefreshCw,
} from 'lucide-react';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, ActionBtn } from './ToolPage';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const h = () => getAuthHeaders();
const money = v => `₹${Number(v || 0).toLocaleString('en-IN')}`;

// ─── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title, count, color = 'var(--tool-hex-4f8ff7)', icon: Icon }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
      {Icon && <Icon size={15} color={color} />}
      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--tool-hex-e5e5e5)', letterSpacing: '0.02em' }}>{title}</span>
      {count !== undefined && (
        <span style={{ background: color, color: '#fff', fontSize: 10, fontWeight: 700, borderRadius: 20, padding: '1px 7px', marginLeft: 2 }}>{count}</span>
      )}
    </div>
  );
}

function KpiCard({ value, label, color, icon: Icon }) {
  return (
    <div style={{
      background: 'var(--tool-hex-1e1e1e)', border: `1px solid var(--tool-hex-2e2e2e)`,
      borderRadius: 12, padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 14,
    }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: `color-mix(in srgb, ${color} 15%, transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Icon size={18} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--tool-hex-f5f5f5)', lineHeight: 1.1 }}>{value}</div>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--tool-hex-888)', letterSpacing: '0.07em', marginTop: 2, textTransform: 'uppercase' }}>{label}</div>
      </div>
    </div>
  );
}

function LeaveCard({ leave, onApprove, onReject }) {
  const [busy, setBusy] = useState(false);
  const act = async fn => { setBusy(true); await fn(); setBusy(false); };
  return (
    <div style={{ background: 'var(--tool-hex-252525)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 10, padding: '12px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {leave.staff?.name || leave.staff_name || leave.staff_id}
        </div>
        <div style={{ fontSize: 11, color: 'var(--tool-hex-888)', marginTop: 3 }}>
          {leave.leave_type || 'Leave'} · {leave.start_date || ''}{leave.end_date ? ` → ${leave.end_date}` : ''}
        </div>
        {leave.reason && <div style={{ fontSize: 10, color: 'var(--tool-hex-666)', marginTop: 2, fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{leave.reason}</div>}
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <button disabled={busy} onClick={() => act(onApprove)} style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.35)', borderRadius: 7, padding: '5px 10px', color: '#22c55e', cursor: 'pointer', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, opacity: busy ? 0.6 : 1 }}>
          <CheckCircle size={11} />Approve
        </button>
        <button disabled={busy} onClick={() => act(onReject)} style={{ background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 7, padding: '5px 10px', color: '#f87171', cursor: 'pointer', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, opacity: busy ? 0.6 : 1 }}>
          <XCircle size={11} />Reject
        </button>
      </div>
    </div>
  );
}

function CertCard({ cert, onApprove, onReject }) {
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');
  const isPending = cert.status === 'pending_approval';
  const isApproved = cert.status === 'approved';
  const statusColor = isApproved ? '#22c55e' : isPending ? '#fbbf24' : '#f87171';
  const statusLabel = isApproved ? 'Approved' : isPending ? 'Pending' : cert.status === 'rejected' ? 'Rejected' : cert.status || 'Unknown';

  const handleReject = async () => {
    if (!reason.trim()) return;
    setBusy(true);
    await onReject(reason.trim());
    setBusy(false);
    setRejecting(false);
    setReason('');
  };

  return (
    <div style={{ background: 'var(--tool-hex-252525)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 10, padding: '12px 14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)' }}>{cert.student_name || cert.student_id}</div>
          <div style={{ fontSize: 11, color: 'var(--tool-hex-888)', marginTop: 3 }}>
            {cert.cert_type || cert.type} · {cert.created_at?.slice(0, 10)}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexShrink: 0 }}>
          <span style={{ background: `color-mix(in srgb, ${statusColor} 15%, transparent)`, border: `1px solid color-mix(in srgb, ${statusColor} 35%, transparent)`, borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700, color: statusColor }}>
            {statusLabel}
          </span>
          {isPending && !rejecting && (
            <>
              <button disabled={busy} onClick={async () => { setBusy(true); await onApprove(); setBusy(false); }} style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.35)', borderRadius: 7, padding: '5px 10px', color: '#22c55e', cursor: 'pointer', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, opacity: busy ? 0.6 : 1 }}>
                <CheckCircle size={11} />Approve
              </button>
              <button disabled={busy} onClick={() => setRejecting(true)} style={{ background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 7, padding: '5px 10px', color: '#f87171', cursor: 'pointer', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, opacity: busy ? 0.6 : 1 }}>
                <XCircle size={11} />Reject
              </button>
            </>
          )}
        </div>
      </div>
      {rejecting && (
        <div style={{ marginTop: 10, display: 'flex', gap: 7, alignItems: 'center' }}>
          <input
            autoFocus
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Reason for rejection..."
            style={{ flex: 1, background: 'var(--tool-hex-1a1a1a)', border: '1px solid var(--tool-hex-3e3e3e)', borderRadius: 6, padding: '6px 10px', color: 'var(--tool-hex-e5e5e5)', fontSize: 11, outline: 'none' }}
          />
          <button disabled={busy || !reason.trim()} onClick={handleReject} style={{ background: 'rgba(248,113,113,0.15)', border: '1px solid rgba(248,113,113,0.4)', borderRadius: 6, padding: '5px 10px', color: '#f87171', cursor: 'pointer', fontSize: 11, fontWeight: 600, opacity: (busy || !reason.trim()) ? 0.5 : 1 }}>
            Confirm
          </button>
          <button onClick={() => { setRejecting(false); setReason(''); }} style={{ background: 'none', border: '1px solid var(--tool-hex-3e3e3e)', borderRadius: 6, padding: '5px 10px', color: 'var(--tool-hex-888)', cursor: 'pointer', fontSize: 11 }}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

function AttendanceBar({ pct }) {
  const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#fbbf24' : '#f87171';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 5, background: 'var(--tool-hex-2e2e2e)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.4s ease' }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, width: 34, textAlign: 'right' }}>{pct}%</span>
    </div>
  );
}

function SubRow({ item, onAssign }) {
  const assigned = item.assigned_substitute;
  const candidate = item.candidate_substitutes?.[0];
  return (
    <tr style={{ borderBottom: '1px solid var(--tool-hex-2e2e2e)' }}>
      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--tool-hex-f87171)', fontWeight: 600 }}>{item.absent_teacher_name}</td>
      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--tool-hex-888)' }}>P{item.period_number}</td>
      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--tool-hex-e5e5e5)' }}>{item.class_name}</td>
      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--tool-hex-aaa)' }}>{item.subject_name}</td>
      <td style={{ padding: '10px 12px' }}>
        {assigned
          ? <span style={{ background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>Assigned</span>
          : <span style={{ background: 'rgba(248,113,113,0.12)', color: '#f87171', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 20, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>Open</span>
        }
      </td>
      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--tool-hex-aaa)' }}>
        {assigned?.substitute_teacher_name || candidate?.name || '—'}
      </td>
      <td style={{ padding: '10px 12px' }}>
        {!assigned && candidate && (
          <ActionBtn label="Assign" icon={<UserCheck size={11} />} onClick={() => onAssign(item, candidate.id)} />
        )}
      </td>
    </tr>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

export default function PrincipalDailyOps() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [items, setItems] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [feeSummary, setFeeSummary] = useState(null);
  const [meta, setMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lessonCompletion, setLessonCompletion] = useState([]);
  const [lessonLoading, setLessonLoading] = useState(true);
  const [classSummary, setClassSummary] = useState([]);
  const [classSummaryLoading, setClassSummaryLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [subsRes, leavesRes, certsRes, feesRes] = await Promise.allSettled([
        fetch(`${API}/academics/substitutions?date=${date}`, { headers: h() }),
        fetch(`${API}/staff/leaves/pending`, { headers: h() }),
        fetch(`${API}/ops/certificates`, { headers: h() }),
        fetch(`${API}/fees/summary`, { headers: h() }),
      ]);
      const subsJson = subsRes.status === 'fulfilled' ? await subsRes.value.json() : { success: false };
      if (!subsJson.success) throw new Error(subsJson.detail || 'Unable to load substitution data');
      setItems(subsJson.data || []);
      setMeta(subsJson.meta || {});
      const leavesJson = leavesRes.status === 'fulfilled' ? await leavesRes.value.json() : {};
      const certsJson = certsRes.status === 'fulfilled' ? await certsRes.value.json() : {};
      const feesJson = feesRes.status === 'fulfilled' ? await feesRes.value.json() : {};
      setLeaves((leavesJson.data || []).slice(0, 8));
      setCertificates((certsJson.data || []).slice(0, 10));
      setFeeSummary(feesJson.data || null);
    } catch (err) {
      setError(err.message || 'Unable to load daily ops');
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    (async () => {
      setLessonLoading(true);
      try {
        const month = new Date().toISOString().slice(0, 7);
        const res = await fetch(`${API}/academics/lesson-plan-completion?month=${month}`, { headers: h() });
        if (res.ok) { const d = await res.json(); setLessonCompletion(d.data || []); }
      } catch {}
      setLessonLoading(false);
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setClassSummaryLoading(true);
      try {
        const res = await fetch(`${API}/attendance/class-summary`, { headers: h() });
        if (res.ok) { const d = await res.json(); setClassSummary(d?.data || []); }
      } catch {}
      setClassSummaryLoading(false);
    })();
  }, []);

  const assign = async (item, teacherId) => {
    if (!teacherId) return;
    const res = await fetch(`${API}/academics/substitutions`, {
      method: 'POST',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date, absent_teacher_id: item.absent_teacher_id,
        substitute_teacher_id: teacherId,
        class_id: item.class_id, subject_id: item.subject_id,
        period_number: item.period_number,
      }),
    });
    if (res.ok) load();
  };

  const decideLeave = async (leaveId, status) => {
    await fetch(`${API}/staff/leaves/${leaveId}`, {
      method: 'PATCH',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, rejection_reason: status === 'rejected' ? 'Rejected by principal' : undefined }),
    });
    load();
  };

  const approveCert = async certId => {
    await fetch(`${API}/ops/certificates/${certId}/approve`, { method: 'PATCH', headers: h() });
    load();
  };

  const rejectCert = async (certId, reason) => {
    await fetch(`${API}/ops/certificates/${certId}/reject`, {
      method: 'PATCH',
      headers: { ...h(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    load();
  };

  const uncovered = meta.uncovered_period_count || items.filter(i => !i.assigned_substitute).length;

  return (
    <ToolPage
      title="Principal Daily"
      subtitle="Today's school operations at a glance"
      loading={loading}
      onRefresh={load}
      actions={
        <label style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--tool-hex-888)', fontSize: 12, cursor: 'pointer' }}>
          <CalendarDays size={13} />
          <input
            type="date" value={date} onChange={e => setDate(e.target.value)}
            style={{ background: 'var(--tool-hex-252525)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 8, color: 'var(--tool-hex-e5e5e5)', padding: '6px 10px', fontSize: 12, cursor: 'pointer' }}
          />
        </label>
      }
    >
      {error && (
        <div style={{ background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 10, padding: '10px 14px', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, color: '#f87171', fontSize: 12 }}>
          <AlertCircle size={14} />{error}
          <button onClick={load} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: 11, textDecoration: 'underline' }}>Retry</button>
        </div>
      )}

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 12, marginBottom: 24 }}>
        <KpiCard value={meta.absent_teacher_count || 0} label="Absent Teachers" color="#f87171" icon={Users} />
        <KpiCard value={items.length} label="Affected Periods" color="#fb923c" icon={CalendarDays} />
        <KpiCard value={uncovered} label="Need Substitute" color={uncovered > 0 ? '#fbbf24' : '#22c55e'} icon={UserCheck} />
        <KpiCard value={leaves.length} label="Pending Leaves" color="#a78bfa" icon={ClipboardList} />
        <KpiCard value={certificates.filter(c => c.status === 'pending_approval').length} label="Cert Approvals" color="#4f8ff7" icon={Award} />
        <KpiCard value={feeSummary ? money(feeSummary.total_collected || 0) : '—'} label="Fee Collected" color="#22c55e" icon={IndianRupee} />
      </div>

      {/* Two-column: leaves + certs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20, marginBottom: 24 }}>
        {/* Leave Approvals */}
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: '16px 18px' }}>
          <SectionHeader title="Leave Approvals" count={leaves.length} color="#a78bfa" icon={ClipboardList} />
          {loading ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>
              <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite', display: 'block', margin: '0 auto 6px' }} />
              Loading...
            </div>
          ) : leaves.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>No pending leave requests</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {leaves.map(l => (
                <LeaveCard
                  key={l.id}
                  leave={l}
                  onApprove={() => decideLeave(l.id, 'approved')}
                  onReject={() => decideLeave(l.id, 'rejected')}
                />
              ))}
            </div>
          )}
        </div>

        {/* Certificate Approvals */}
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: '16px 18px' }}>
          <SectionHeader title="Certificates" count={certificates.length} color="#4f8ff7" icon={Award} />
          {loading ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>
              <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite', display: 'block', margin: '0 auto 6px' }} />
              Loading...
            </div>
          ) : certificates.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>No certificates found</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {certificates.map(c => (
                <CertCard key={c.id} cert={c} onApprove={() => approveCert(c.id)} onReject={reason => rejectCert(c.id, reason)} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Substitution Plan */}
      <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: '16px 18px', marginBottom: 24 }}>
        <SectionHeader title="Substitution Plan" count={items.length} color="#fb923c" icon={UserCheck} />
        {loading ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>
            <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite', display: 'block', margin: '0 auto 6px' }} />
            Loading...
          </div>
        ) : items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>
            No absent-teacher conflicts for {date}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--tool-hex-2e2e2e)' }}>
                  {['Absent Teacher', 'Period', 'Class', 'Subject', 'Status', 'Suggested Sub', 'Action'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--tool-hex-666)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => <SubRow key={i} item={item} onAssign={assign} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bottom row: Attendance + Lesson Plans */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
        {/* Class Attendance */}
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: '16px 18px' }}>
          <SectionHeader title="Today's Attendance" color="#34d399" icon={Users} />
          {classSummaryLoading ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>
              <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite', display: 'block', margin: '0 auto 6px' }} />
              Loading...
            </div>
          ) : classSummary.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>No attendance data yet</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {classSummary.map(cls => (
                <div key={cls.class_id}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)' }}>{cls.class_name}</span>
                    <span style={{ fontSize: 11, color: 'var(--tool-hex-888)' }}>{cls.present}P / {cls.absent}A</span>
                  </div>
                  <AttendanceBar pct={cls.attendance_pct || 0} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Lesson Plan Completion */}
        <div style={{ background: 'var(--tool-hex-1e1e1e)', border: '1px solid var(--tool-hex-2e2e2e)', borderRadius: 12, padding: '16px 18px' }}>
          <SectionHeader title="Lesson Plan Completion" color="#4f8ff7" icon={BookOpen} />
          {lessonLoading ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>
              <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite', display: 'block', margin: '0 auto 6px' }} />
              Loading...
            </div>
          ) : lessonCompletion.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--tool-hex-555)', fontSize: 12 }}>No lesson plans for this month</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {lessonCompletion.map(cls => (
                <div key={cls.class_id}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <div>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--tool-hex-e5e5e5)' }}>{cls.class_name}</span>
                      {cls.teacher_name && <span style={{ fontSize: 10, color: 'var(--tool-hex-666)', marginLeft: 6 }}>{cls.teacher_name}</span>}
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--tool-hex-888)' }}>{cls.completed}/{cls.total_plans}</span>
                  </div>
                  <AttendanceBar pct={cls.completion_pct || 0} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </ToolPage>
  );
}
