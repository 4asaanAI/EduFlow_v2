import React, { useCallback, useEffect, useState } from 'react';
import { CalendarDays, RefreshCw, UserCheck } from 'lucide-react';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, StatCard, DataTable, Badge, ActionBtn, ErrorCard } from './ToolPage';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function PrincipalDailyOps() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/academics/substitutions?date=${date}`, { headers: getAuthHeaders() });
      const json = await res.json();
      if (!json.success) throw new Error(json.detail || 'Unable to load substitution plan');
      setItems(json.data || []);
      setMeta(json.meta || {});
    } catch (err) {
      setError(err.message || 'Unable to load substitution plan');
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

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
    </ToolPage>
  );
}
