import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import { getStaff, getStudents } from '../../lib/api';
import DataTable, { cellValue } from '../ui/DataTable';
import { useTablePageSize } from '../../hooks/useTablePrefs';
import { ArrowRight, RefreshCw, Users } from 'lucide-react';

// ─── The school's own staff vocabulary (Epic 7, owner decision 2026-07-23) ──────
//
// The staff attendance register uses PRIN / NTT / PRT / TGT / PGT / Other. The
// owner asked to see those codes rather than the machine `role / sub_category`.
//
// HONESTY CONSTRAINT (the D-15b / Epic 4 lesson). The teacher tier — NTT, PRT,
// TGT, PGT — is NOT stored anywhere in the platform. Only `designation`
// ("Class Teacher" / "Teacher" / "Principal"), `staff_type`, `role` and
// `sub_category` exist. So a code is shown ONLY where it can be derived without
// inventing data (Principal → PRIN); every other teacher falls back to the
// readable designation. Fabricating PRT/TGT/PGT from data that does not carry
// the distinction would be the failure-that-looks-like-a-fact defect in a new
// place. The tier codes wait on the Track 2 data load (D-09), and the Staff tab
// says so in a legend rather than hiding the gap.
const REGISTER_CODES = {
  PRIN: 'Principal',
  NTT: 'Nursery Teacher Training (pre-primary)',
  PRT: 'Primary Teacher',
  TGT: 'Trained Graduate Teacher',
  PGT: 'Post Graduate Teacher',
};

// Returns { code, full } when a register code is confidently derivable, else null.
function registerCode(profile) {
  const isPrincipal =
    profile.sub_category === 'principal' ||
    profile.role === 'owner' ||
    String(profile.designation || '').trim().toLowerCase() === 'principal';
  if (isPrincipal) return { code: 'PRIN', full: REGISTER_CODES.PRIN };
  return null; // teacher tier is not in the data — do not invent it
}

// The readable job title a human would say, mirroring StaffTracker.designationOf.
function designationOf(profile) {
  if (profile.designation) return profile.designation;
  const raw = profile.sub_category || profile.role || profile.staff_type;
  if (!raw) return '—';
  return String(raw)
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// Designation cell: the register code where derivable (expanded on hover +
// aria-label), otherwise the plain designation. Never `role / sub_category`.
function DesignationCell({ profile }) {
  const rc = registerCode(profile);
  if (rc) {
    return (
      <span title={rc.full} aria-label={rc.full} style={{ fontWeight: 700 }}>
        {rc.code}
        <span style={{ color: 'var(--c-faint)', fontWeight: 400 }}> ({rc.full.split(' (')[0]})</span>
      </span>
    );
  }
  return <span>{designationOf(profile)}</span>;
}

const TABS = [
  { id: 'students', label: 'Students' },
  { id: 'staff', label: 'Staff' },
];

export default function SchoolDirectory() {
  const { currentUser } = useUser();
  const [searchParams, setSearchParams] = useSearchParams();

  // Active tab lives in the URL so a reload or a shared link lands on the same
  // tab (FR81 spirit). Falls back to Students for an unknown value.
  const urlTab = searchParams.get('tab');
  const activeTab = TABS.some((t) => t.id === urlTab) ? urlTab : 'students';
  const setActiveTab = useCallback(
    (tab) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('tool', 'school-directory');
        next.set('tab', tab);
        return next;
      });
    },
    [setSearchParams],
  );

  return (
    <div data-testid="school-directory-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 650, color: 'var(--c-text)', margin: 0, display: 'flex', alignItems: 'center', gap: 9 }}>
          <Users size={20} /> School Directory
        </h1>
        <div style={{ color: 'var(--c-faint)', fontSize: 12, marginTop: 3 }}>
          Find any person in the school — students and staff, in one place.
        </div>
      </div>

      {/* Tabs — reflected in the URL */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--c-border)' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            data-testid={`directory-tab-${t.id}`}
            onClick={() => setActiveTab(t.id)}
            aria-selected={activeTab === t.id}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: activeTab === t.id ? '2px solid var(--tool-hex-4f8ff7)' : '2px solid transparent',
              color: activeTab === t.id ? 'var(--c-text)' : 'var(--c-faint)',
              padding: '9px 16px',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'students' ? (
        <StudentsTab
          user={currentUser}
          // Deep-link straight to this student's profile — StudentDatabase reads
          // `focus` and opens the detail panel (fetches by id, so the student
          // need not be on that screen's current page).
          onOpen={(s) => setSearchParams({ tool: 'student-database', focus: s.id })}
        />
      ) : (
        // D-44 CLOSED 2026-08-04: the row now opens that person's record, not just
        // the list. Staff Tracker reads `focus` and fetches the staff member by id,
        // so it works whatever page that paginated list happens to be showing, and
        // says so plainly if the record cannot be opened.
        <StaffTab onOpen={(s) => setSearchParams({ tool: 'staff-tracker', focus: s.id })} />
      )}
    </div>
  );
}

// ─── Students tab ───────────────────────────────────────────────────────────────

function StudentsTab({ user, onOpen }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  // Keyed per tab so sizing students does not resize staff (UX-DR10).
  const [pageSize, setPageSize] = useTablePageSize('directory-students');
  const changeSort = useCallback((next) => { setSort(next); setPage(1); }, []);
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); }, [setPageSize]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getStudents({ page, sort, limit: pageSize });
      if (res.success) {
        setRows(res.data || []);
        setTotal(res.meta?.total || 0);
      } else {
        setError(res.detail || 'Unable to load students');
      }
    } catch (err) {
      setError(err.message || 'Unable to load students');
    }
    setLoading(false);
  }, [page, sort, pageSize]);

  useEffect(() => { load(); }, [load]);

  const columns = useMemo(() => [
    {
      key: 'name', label: 'Name', sortKey: 'name',
      render: (s) => (
        <div>
          <div style={{ color: 'var(--c-text)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>{cellValue(s.name)}</div>
          <div style={{ color: 'var(--c-faint)', fontSize: 'var(--text-xs)' }}>{s.admission_number || 'No admission no.'}</div>
        </div>
      ),
    },
    // Field names match what the students LIST endpoint actually returns (the
    // same accessors StudentDatabase's own table uses): class via `class_info`,
    // the primary contact via `primary_phone`. Guardian name is not on the list
    // payload — it loads with the profile — so it is deliberately not a column
    // here rather than a column that always reads "not recorded". Sort is
    // server-side (sortKey: 'class').
    { key: 'class', label: 'Class', sortKey: 'class', render: (s) => (s.class_info ? `${s.class_info.name}-${s.class_info.section}` : cellValue(null)) },
    { key: 'phone', label: 'Phone', render: (s) => cellValue(s.primary_phone) },
    {
      key: 'open', label: '',
      render: () => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--tool-hex-4f8ff7)', fontSize: 12 }}>
          Open <ArrowRight size={12} />
        </span>
      ),
    },
  ], []);

  if (loading && rows.length === 0) return <Loading label="Loading students…" />;

  return (
    <>
      {error && <ErrorBanner text={error} />}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
        <select
          data-testid="directory-students-sort"
          value={sort}
          onChange={(e) => changeSort(e.target.value)}
          style={selectStyle}
        >
          <option value="name">Sort by name</option>
          <option value="class">Sort by class</option>
          <option value="created_at">Newest first</option>
        </select>
      </div>
      <DataTable
        tableId="directory-students"
        caption="Students, sortable by column"
        columns={columns}
        rows={rows}
        rowKey={(s) => s.id}
        onRowClick={onOpen}
        sort={sort}
        onSortChange={changeSort}
        page={page}
        total={total}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={changePageSize}
        emptyTitle="No students found"
        emptyMessage="Try a different sort."
      />
    </>
  );
}

// ─── Staff tab ──────────────────────────────────────────────────────────────────

function StaffTab({ onOpen }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useTablePageSize('directory-staff');
  const changeSort = useCallback((next) => { setSort(next); setPage(1); }, []);
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); }, [setPageSize]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getStaff({ page, sort, limit: pageSize });
      if (res.success) {
        setRows(res.data || []);
        setTotal(res.meta?.total || 0);
      } else {
        setError(res.detail || 'Unable to load staff');
      }
    } catch (err) {
      setError(err.message || 'Unable to load staff');
    }
    setLoading(false);
  }, [page, sort, pageSize]);

  useEffect(() => { load(); }, [load]);

  const columns = useMemo(() => [
    {
      key: 'name', label: 'Name', sortKey: 'name',
      render: (p) => (
        <div>
          <div style={{ color: 'var(--c-text)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>{cellValue(p.name)}</div>
          <div style={{ color: 'var(--c-faint)', fontSize: 'var(--text-xs)' }}>{p.employee_id || 'No employee ID'}</div>
        </div>
      ),
    },
    { key: 'designation', label: 'Designation', sortKey: 'designation', render: (p) => <DesignationCell profile={p} /> },
    { key: 'department', label: 'Department', sortKey: 'department', render: (p) => cellValue(p.department) },
    { key: 'phone', label: 'Phone', render: (p) => cellValue(p.phone) },
    {
      key: 'open', label: '',
      render: () => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--tool-hex-4f8ff7)', fontSize: 12 }}>
          Open <ArrowRight size={12} />
        </span>
      ),
    },
  ], []);

  if (loading && rows.length === 0) return <Loading label="Loading staff…" />;

  return (
    <>
      {error && <ErrorBanner text={error} />}
      {/* Legend — the register codes, and the honest note that the teacher tier
          is not yet recorded (Track 2 / D-09), so its absence is visible. */}
      <div
        data-testid="directory-staff-legend"
        style={{ fontSize: 11, color: 'var(--c-faint)', marginBottom: 10, lineHeight: 1.6 }}
      >
        Register codes: <strong>PRIN</strong> Principal · <strong>NTT</strong> Nursery ·{' '}
        <strong>PRT</strong> Primary · <strong>TGT</strong> Trained Graduate ·{' '}
        <strong>PGT</strong> Post Graduate. The teacher tier (NTT/PRT/TGT/PGT) is not yet
        recorded per staff member, so teachers show their stored designation until that data
        is loaded.
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
        <select
          data-testid="directory-staff-sort"
          value={sort}
          onChange={(e) => changeSort(e.target.value)}
          style={selectStyle}
        >
          <option value="name">Sort by name</option>
          <option value="staff_type">Sort by type</option>
          <option value="department">Sort by department</option>
          <option value="created_at">Newest first</option>
        </select>
      </div>
      <DataTable
        tableId="directory-staff"
        caption="Staff, sortable by column"
        columns={columns}
        rows={rows}
        rowKey={(p) => p.id}
        onRowClick={onOpen}
        sort={sort}
        onSortChange={changeSort}
        page={page}
        total={total}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={changePageSize}
        emptyTitle="No staff found"
        emptyMessage="Try a different sort."
      />
    </>
  );
}

// ─── Small shared bits ──────────────────────────────────────────────────────────

const selectStyle = {
  width: 180,
  background: 'var(--c-bg)',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  padding: '9px 12px',
  color: 'var(--c-text)',
  fontSize: 13,
  outline: 'none',
};

function Loading({ label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 48, color: 'var(--c-faint)' }}>
      <RefreshCw size={18} style={{ animation: 'spin 0.8s linear infinite', marginRight: 10 }} />
      {label}
    </div>
  );
}

function ErrorBanner({ text }) {
  return (
    <div
      role="alert"
      style={{ color: 'var(--tool-hex-f87171)', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.18)', borderRadius: 8, padding: 10, marginBottom: 12, fontSize: 12 }}
    >
      {text}
    </div>
  );
}

export { registerCode, designationOf, REGISTER_CODES };
