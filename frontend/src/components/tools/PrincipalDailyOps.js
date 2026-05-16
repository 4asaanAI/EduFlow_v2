import React, { useCallback, useEffect, useState } from 'react';
import { CalendarDays, CheckCircle, IndianRupee, RefreshCw, UserCheck } from 'lucide-react';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, StatCard, DataTable, Badge, ActionBtn, ErrorCard } from './ToolPage';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function PrincipalDailyOps() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [items, setItems] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [feeSummary, setFeeSummary] = useState([]);
  const [meta, setMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lessonCompletion, setLessonCompletion] = useState([]);
  const [loadingAcademics, setLoadingAcademics] = useState(true);
  const [classSummary, setClassSummary] = useState([]);
  const [loadingAttendance, setLoadingAttendance] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [subsRes, leavesRes, certsRes, feesRes] = await Promise.allSettled([
        fetch(`${API}/academics/substitutions?date=${date}`, { headers: getAuthHeaders() }),
        fetch(`${API}/staff/leaves/pending`, { headers: getAuthHeaders() }),
        fetch(`${API}/operations/certificates`, { headers: getAuthHeaders() }),
        fetch(`${API}/fees/summary`, { headers: getAuthHeaders() }),
      ]);
      const subsJson = subsRes.status === 'fulfilled' ? await subsRes.value.json() : { success: false };
      if (!subsJson.success) throw new Error(subsJson.detail || 'Unable to load daily ops');
      setItems(subsJson.data || []);
      setMeta(subsJson.meta || {});
      const leavesJson = leavesRes.status === 'fulfilled' ? await leavesRes.value.json() : { data: [] };
      const certsJson = certsRes.status === 'fulfilled' ? await certsRes.value.json() : { data: [] };
      const feesJson = feesRes.status === 'fulfilled' ? await feesRes.value.json() : { data: [] };
      setLeaves((leavesJson.data || []).slice(0, 5));
      setCertificates((certsJson.data || []).filter(c => c.status === 'pending_approval').slice(0, 5));
      const summary = feesJson.data || {};
      setFeeSummary(summary.period ? [{
        month: summary.period,
        collected: summary.total_collected || 0,
        outstanding: summary.total_outstanding || 0,
      }] : []);
    } catch (err) {
      setError(err.message || 'Unable to load daily ops');
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const fetchAcademics = useCallback(async () => {
    setLoadingAcademics(true);
    try {
      const res = await fetch(`${API}/academics/lesson-plan-completion`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setLessonCompletion(data.data || []);
      }
    } catch (e) {
      console.error('Failed to load academics:', e);
    } finally {
      setLoadingAcademics(false);
    }
  }, []);

  useEffect(() => { fetchAcademics(); }, [fetchAcademics]);

  const fetchAttendanceSummary = useCallback(async () => {
    setLoadingAttendance(true);
    try {
      const res = await fetch(`${API}/attendance/class-summary`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setClassSummary(data?.data || []);
      }
    } catch (e) {
      console.error('Failed to load attendance summary:', e);
    } finally {
      setLoadingAttendance(false);
    }
  }, []);

  useEffect(() => { fetchAttendanceSummary(); }, [fetchAttendanceSummary]);

  const assign = async (item, teacherId) => {
    if (!teacherId) return;
    const res = await fetch(`${API}/academics/substitutions`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date,
        absent_teacher_id: item.absent_teacher_id,
        substitute_teacher_id: teacherId,
        class_id: item.class_id,
        subject_id: item.subject_id,
        period_number: item.period_number,
      }),
    });
    if (res.ok) load();
  };

  const decideLeave = async (leaveId, status) => {
    await fetch(`${API}/staff/leaves/${leaveId}`, {
      method: 'PATCH',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, rejection_reason: status === 'rejected' ? 'Rejected by principal' : undefined }),
    });
    load();
  };

  const approveCert = async (certId) => {
    await fetch(`${API}/operations/certificates/${certId}/approve`, { method: 'PATCH', headers: getAuthHeaders() });
    load();
  };

  const rows = items.map(item => {
    const assigned = item.assigned_substitute;
    const firstCandidate = item.candidate_substitutes?.[0];
    return [
      item.absent_teacher_name,
      item.period_number,
      item.class_name,
      item.subject_name,
      assigned ? <Badge text="Assigned" color="green" /> : <Badge text="Open" color="red" />,
      assigned?.substitute_teacher_id || firstCandidate?.name || 'No free teacher found',
      !assigned && firstCandidate ? (
        <ActionBtn label="Assign" icon={<UserCheck size={12} />} onClick={() => assign(item, firstCandidate.id)} />
      ) : '',
    ];
  });

  return (
    <ToolPage
      title="Principal Daily"
      subtitle="Absent teachers and substitution coverage for the day"
      loading={loading}
      onRefresh={load}
      actions={(
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--color-text-muted)', fontSize: 12 }}>
          <CalendarDays size={14} />
          <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text-primary)', padding: '7px 10px' }} />
        </label>
      )}
    >
      {error && <ErrorCard message={error} onRetry={load} />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(160px, 1fr))', gap: 12, marginBottom: 16, maxWidth: 780 }}>
        <StatCard value={meta.absent_teacher_count || 0} label="ABSENT TEACHERS" color="var(--color-danger)" />
        <StatCard value={items.length} label="AFFECTED PERIODS" color="var(--color-warning)" />
        <StatCard value={meta.uncovered_period_count || 0} label="NEEDS SUBSTITUTE" color="var(--color-accent-blue)" />
        <StatCard value={leaves.length} label="PENDING LEAVES" color="var(--color-warning)" />
        <StatCard value={certificates.length} label="CERT APPROVALS" color="var(--color-accent-blue)" />
        <StatCard value={`Rs ${feeSummary.reduce((sum, row) => sum + Number(row.collected || 0), 0).toLocaleString('en-IN')}`} label="FEE COLLECTION" color="var(--color-success)" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 16 }}>
        <DataTable
          title="Leave Approvals"
          headers={['Staff', 'Dates', 'Type', 'Action']}
          rows={leaves.map(l => [
            l.staff?.name || l.staff_name || l.staff_id,
            `${l.start_date || ''} ${l.end_date ? `to ${l.end_date}` : ''}`,
            l.leave_type || 'Leave',
            <span style={{ display: 'inline-flex', gap: 6 }}>
              <ActionBtn label="Approve" icon={<CheckCircle size={12} />} onClick={() => decideLeave(l.id, 'approved')} />
              <ActionBtn label="Reject" onClick={() => decideLeave(l.id, 'rejected')} />
            </span>,
          ])}
          emptyMsg="No pending leaves"
          loading={loading}
        />
        <DataTable
          title="Certificate Approvals"
          headers={['Student', 'Type', 'Requested', 'Action']}
          rows={certificates.map(c => [
            c.student_name || c.student_id,
            c.type,
            c.created_at?.slice(0, 10),
            <ActionBtn label="Approve" icon={<CheckCircle size={12} />} onClick={() => approveCert(c.id)} />,
          ])}
          emptyMsg="No pending certificates"
          loading={loading}
        />
        <DataTable
          title="Fee Trend"
          headers={['Month', 'Collected', 'Outstanding']}
          rows={feeSummary.map(row => [
            row.month,
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><IndianRupee size={12} />{Number(row.collected || 0).toLocaleString('en-IN')}</span>,
            Number(row.outstanding || 0).toLocaleString('en-IN'),
          ])}
          emptyMsg="No fee summary"
          loading={loading}
        />
      </div>
      <DataTable
        title="Substitution Plan"
        headers={['Absent Teacher', 'Period', 'Class', 'Subject', 'Status', 'Suggested Substitute', 'Action']}
        rows={rows}
        emptyMsg="No absent-teacher timetable conflicts for this date"
        loading={loading}
      />
      <button onClick={load} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none', color: 'var(--color-accent-blue)', cursor: 'pointer', fontSize: 12 }}>
        <RefreshCw size={13} /> Refresh coverage
      </button>

      {/* Today's Class Attendance */}
      <div className="bg-white rounded-lg border border-gray-200 p-4" style={{ marginTop: 20 }}>
        <h3 className="font-semibold text-gray-700 mb-3">Today's Class Attendance</h3>
        {loadingAttendance ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : classSummary.length === 0 ? (
          <p className="text-sm text-gray-400">No attendance data yet today.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-500 border-b">
                <th className="pb-2">Class</th><th className="pb-2">Present</th>
                <th className="pb-2">Absent</th><th className="pb-2">%</th>
              </tr></thead>
              <tbody>
                {classSummary.map(cls => (
                  <tr key={cls.class_id} className="border-b border-gray-50">
                    <td className="py-1.5 font-medium">{cls.class_name}</td>
                    <td className="py-1.5 text-green-600">{cls.present}</td>
                    <td className="py-1.5 text-red-500">{cls.absent}</td>
                    <td className="py-1.5">
                      <span className={`font-medium ${cls.attendance_pct >= 80 ? 'text-green-600' : 'text-red-500'}`}>
                        {cls.attendance_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Lesson Plan Completion */}
      <div className="bg-white rounded-lg border border-gray-200 p-4" style={{ marginTop: 20 }}>
        <h3 className="font-semibold text-gray-700 mb-3">Lesson Plan Completion</h3>
        {loadingAcademics ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : lessonCompletion.length === 0 ? (
          <p className="text-sm text-gray-400">No lesson plans found for this month.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="pb-2">Class</th>
                  <th className="pb-2">Teacher</th>
                  <th className="pb-2">Completed</th>
                  <th className="pb-2">Total</th>
                  <th className="pb-2">%</th>
                </tr>
              </thead>
              <tbody>
                {lessonCompletion.map(cls => (
                  <tr key={cls.class_id} className="border-b border-gray-50">
                    <td className="py-1.5 font-medium">{cls.class_name}</td>
                    <td className="py-1.5 text-gray-600">{cls.teacher_name}</td>
                    <td className="py-1.5">{cls.completed}</td>
                    <td className="py-1.5">{cls.total_plans}</td>
                    <td className="py-1.5">
                      <span className={`font-semibold ${cls.completion_pct >= 80 ? 'text-green-600' : cls.completion_pct >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {cls.completion_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </ToolPage>
  );
}
