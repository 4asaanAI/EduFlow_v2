import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import { getAllClasses, getStaff, getStudents, STAFF_PAGE_MAX, STUDENTS_PAGE_MAX } from '../../lib/api';
import { fetchAllRows } from '../../lib/fetchAllRows';
import { collectAllRows } from '../../lib/exportTable';
import { EnrolmentBadge } from '../ui/EnrolmentControls';
import { readState } from '../../lib/enrolmentStates';
import DataTable, { cellValue } from '../ui/DataTable';
import WholeSchoolExportButton from '../ui/WholeSchoolExportButton';
import { ALL_ROWS, useTablePageSize } from '../../hooks/useTablePrefs';
import { ArrowRight, RefreshCw, Search, Users } from 'lucide-react';
import SearchableSelect from '../ui/SearchableSelect';

// ─── The school's own staff vocabulary (Epic 7, owner decision 2026-07-23) ──────
//
// The staff attendance register uses PRIN / NTT / PRT / TGT / PGT / Other. The
// owner asked to see those codes rather than the machine `role / sub_category`.
//
// HONESTY CONSTRAINT (the D-15b / Epic 4 lesson). The teacher tier - NTT, PRT,
// TGT, PGT - is NOT stored anywhere in the platform. Only `designation`
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
  return null; // teacher tier is not in the data - do not invent it
}

// The readable job title a human would say, mirroring StaffTracker.designationOf.
function designationOf(profile) {
  if (profile.designation) return profile.designation;
  const raw = profile.sub_category || profile.role || profile.staff_type;
  if (!raw) return '-';
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
          Find any person in the school - students and staff, in one place.
        </div>
        {/* The whole school as one workbook. It lives here because this is the screen
            about the school's own records, and it hides itself for anyone but the
            owner and the principal. The server refuses them too - the hiding is a
            courtesy, not the rule. */}
        <div style={{ marginTop: 12 }}>
          <WholeSchoolExportButton user={currentUser} />
        </div>
      </div>

      {/* Tabs - reflected in the URL */}
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
          // The Directory is the single door now (owner note 2026-08-07), so it has to
          // carry the things that only live on the full screen: adding a student, the
          // recycle bin, class strength. Without this the merge would strand them.
          onOpenFullScreen={() => setSearchParams({ tool: 'student-database' })}
          // Deep-link straight to this student's profile - StudentDatabase reads
          // `focus` and opens the detail panel (fetches by id, so the student
          // need not be on that screen's current page).
          onOpen={(s) => setSearchParams({ tool: 'student-database', focus: s.id })}
        />
      ) : (
        // D-44 CLOSED 2026-08-04: the row now opens that person's record, not just
        // the list. Staff Tracker reads `focus` and fetches the staff member by id,
        // so it works whatever page that paginated list happens to be showing, and
        // says so plainly if the record cannot be opened.
        <StaffTab
          onOpen={(s) => setSearchParams({ tool: 'staff-tracker', focus: s.id })}
          onOpenFullScreen={() => setSearchParams({ tool: 'staff-tracker' })}
        />
      )}
    </div>
  );
}

// ─── Students tab ───────────────────────────────────────────────────────────────

function StudentsTab({ user, onOpen, onOpenFullScreen }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  // Owner note, 2026-08-07: the Directory is now the single place to find anybody,
  // so it needs to be searchable. The search goes to the SERVER, not to the rows
  // already on screen, or it would only ever find people on the current page.
  const [search, setSearch] = useState('');
  // Release 3, item C. Search alone is not a filter: it finds a child you can already
  // name. A class filter is how somebody works THROUGH a group - the register for 5 A,
  // the fee chase for 6 B - and 1,876 children is far past what anyone reads by hand.
  // It goes to the SERVER for the same reason the search does: filtering the rows on
  // screen would narrow one page and quietly hide the rest.
  const [classId, setClassId] = useState('');
  const [classList, setClassList] = useState([]);
  // Keyed per tab so sizing students does not resize staff (UX-DR10).
  const [pageSize, setPageSize] = useTablePageSize('directory-students');
  const changeSort = useCallback((next) => { setSort(next); setPage(1); }, []);
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); }, [setPageSize]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // "All" is a sentinel (-1), never a limit to send. Passed through, every
      // server clamps it with max(1, ...) and answers with a SINGLE ROW.
      if (pageSize === ALL_ROWS) {
        const all = await fetchAllRows(
          ({ page: cursor, limit }) => getStudents({ page: cursor, sort, limit, ...(search ? { search } : {}), ...(classId ? { class_id: classId } : {}) }),
          { pageMax: STUDENTS_PAGE_MAX },
        );
        if (all.success) { setRows(all.data); setTotal(all.total); }
        else { setError(all.detail || "Couldn't load students"); }
        setLoading(false);
        return;
      }
      const res = await getStudents({ page, sort, limit: pageSize, ...(search ? { search } : {}), ...(classId ? { class_id: classId } : {}) });
      if (res.success) {
        setRows(res.data || []);
        setTotal(res.meta?.total || 0);
      } else {
        setError(res.detail || "Couldn't load students");
      }
    } catch (err) {
      setError(err.message || "Couldn't load students");
    }
    setLoading(false);
  }, [page, sort, pageSize, search, classId]);

  // The class list for the filter. Loaded once; it does not change while somebody
  // is looking at the directory.
  useEffect(() => {
    getAllClasses().then((r) => { if (r.success) setClassList(r.data || []); }).catch(() => {});
  }, []);

  // The download takes BOTH FILTERS with it. Someone who has narrowed to 5 A and
  // searched for "Sharma" and presses Download means those children, not all 1,876 -
  // and a file that quietly holds the whole roll instead is as wrong as one that
  // holds a page, and worse, because it leaves the building under the wrong name.
  const exportRows = useCallback(
    () => collectAllRows(
      ({ page: cursor, limit }) => getStudents({ page: cursor, sort, limit, ...(search ? { search } : {}), ...(classId ? { class_id: classId } : {}) }),
      { pageMax: STUDENTS_PAGE_MAX, what: 'students' },
    ),
    [sort, search, classId],
  );

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
    // payload - it loads with the profile - so it is deliberately not a column
    // here rather than a column that always reads "not recorded". Sort is
    // server-side (sortKey: 'class').
    // `exportValue` wherever the cell is drawn from something other than a field of
    // the same name. Without it the column reads correctly on screen and comes out
    // BLANK in the downloaded file, which nobody would think to check.
    { key: 'class', label: 'Class', sortKey: 'class', exportValue: (s) => (s.class_info ? `${s.class_info.name}-${s.class_info.section}` : ''), render: (s) => (s.class_info ? `${s.class_info.name}-${s.class_info.section}` : cellValue(null)) },
    { key: 'roll', label: 'Roll', exportValue: (s) => s.roll_number, render: (s) => cellValue(s.roll_number) },
    { key: 'phone', label: 'Phone', exportValue: (s) => s.primary_phone, render: (s) => cellValue(s.primary_phone) },
    { key: 'house', label: 'House', sortKey: 'house', render: (s) => cellValue(s.house) },
    // Owner request 10: the Directory is the single place now, so it has to say
    // whether somebody is on the roll, on the NSO list, or has left.
    { key: 'status', label: 'Status', exportValue: (s) => readState(s), render: (s) => <EnrolmentBadge state={readState(s)} /> },
    {
      key: 'open', label: '',
      // A link, not data.
      exportSkip: true,
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
      <div style={{ display: 'flex', gap: 10, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 340 }}>
          <Search size={13} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--c-faint)' }} />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            data-testid="directory-students-search"
            aria-label="Search students by name or admission number"
            placeholder="Name or admission number"
            style={{ ...selectStyle, paddingLeft: 32, width: '100%' }}
          />
        </div>
        <SearchableSelect
          data-testid="directory-students-class"
          value={classId}
          onChange={(e) => { setClassId(e.target.value); setPage(1); }}
          aria-label="Filter students by class"
          style={selectStyle}
        >
          <option value="">All classes</option>
          {classList.map((c) => (
            <option key={c.id} value={c.id}>{`${c.name || ''} ${c.section || ''}`.trim()}</option>
          ))}
        </SearchableSelect>
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
        <button
          type="button"
          onClick={onOpenFullScreen}
          data-testid="directory-open-student-records"
          style={linkButtonStyle}
        >
          Add, restore or erase a student <ArrowRight size={12} />
        </button>
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
        exportTable={{ title: 'Students', getRows: exportRows }}
        emptyTitle="No students found"
        emptyMessage="Try a different sort."
      />
    </>
  );
}

// ─── Staff tab ──────────────────────────────────────────────────────────────────

function StaffTab({ onOpen, onOpenFullScreen }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [pageSize, setPageSize] = useTablePageSize('directory-staff');
  const changeSort = useCallback((next) => { setSort(next); setPage(1); }, []);
  const changePageSize = useCallback((n) => { setPageSize(n); setPage(1); }, [setPageSize]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      if (pageSize === ALL_ROWS) {
        const all = await fetchAllRows(
          ({ page: cursor, limit }) => getStaff({ page: cursor, sort, limit, ...(search ? { search } : {}) }),
          { pageMax: STAFF_PAGE_MAX },
        );
        if (all.success) { setRows(all.data); setTotal(all.total); }
        else { setError(all.detail || "Couldn't load staff"); }
        setLoading(false);
        return;
      }
      const res = await getStaff({ page, sort, limit: pageSize, ...(search ? { search } : {}) });
      if (res.success) {
        setRows(res.data || []);
        setTotal(res.meta?.total || 0);
      } else {
        setError(res.detail || "Couldn't load staff");
      }
    } catch (err) {
      setError(err.message || "Couldn't load staff");
    }
    setLoading(false);
  }, [page, sort, pageSize, search]);

  const exportRows = useCallback(
    () => collectAllRows(
      ({ page: cursor, limit }) => getStaff({ page: cursor, sort, limit, ...(search ? { search } : {}) }),
      { pageMax: STAFF_PAGE_MAX, what: 'staff' },
    ),
    [sort, search],
  );

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
    { key: 'designation', label: 'Designation', sortKey: 'designation', exportValue: (p) => p.designation, render: (p) => <DesignationCell profile={p} /> },
    { key: 'department', label: 'Department', sortKey: 'department', render: (p) => cellValue(p.department) },
    { key: 'phone', label: 'Phone', render: (p) => cellValue(p.phone) },
    { key: 'email', label: 'Email', render: (p) => cellValue(p.email) },
    { key: 'status', label: 'Status', exportValue: (p) => readState(p), render: (p) => <EnrolmentBadge state={readState(p)} /> },
    {
      key: 'open', label: '',
      exportSkip: true,
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
      {/* Legend - the register codes, and the honest note that the teacher tier
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
      <div style={{ display: 'flex', gap: 10, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 340 }}>
          <Search size={13} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--c-faint)' }} />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            data-testid="directory-staff-search"
            aria-label="Search staff by name, employee ID, designation or department"
            placeholder="Name, employee ID or department"
            style={{ ...selectStyle, paddingLeft: 32, width: '100%' }}
          />
        </div>
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
        <button
          type="button"
          onClick={onOpenFullScreen}
          data-testid="directory-open-staff-records"
          style={linkButtonStyle}
        >
          Add, restore or erase a staff member <ArrowRight size={12} />
        </button>
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
        exportTable={{ title: 'Staff', getRows: exportRows }}
        emptyTitle="No staff found"
        emptyMessage="Try a different sort."
      />
    </>
  );
}

// ─── Small shared bits ──────────────────────────────────────────────────────────

/**
 * The way through to the full records screen behind each tab.
 *
 * Owner note, 2026-08-07: the Directory is now the only tile in the hub, so the
 * things that live ONLY on the full screen - adding a person, the recycle bin, class
 * strength - have to be reachable from here or the merge would quietly remove them.
 */
const linkButtonStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: 'transparent', border: '1px solid var(--c-border)',
  borderRadius: 8, padding: '9px 12px',
  color: 'var(--tool-hex-4f8ff7)', fontSize: 12, fontWeight: 650, cursor: 'pointer',
};

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

/**
 * The staff finder, exported so the merged School Directory screen
 * (`tools/StudentDatabase`) can host it as its Staff tab (D-44 cluster D, done
 * 2026-08-07 on the owner's instruction).
 *
 * The school's owner reported "two views of the student database for some reason" -
 * this screen and the Student Database both listed every student, one read-only and
 * one with the buttons. There is now one screen, and this is the half of this file
 * that had no equivalent over there.
 */
export { StaffTab };
