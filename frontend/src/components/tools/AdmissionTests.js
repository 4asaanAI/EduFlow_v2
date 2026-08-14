import React, { useCallback, useEffect, useState } from 'react';
import { CalendarDays, Plus, RefreshCw } from 'lucide-react';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';

/**
 * B1: an entrance test is a record, not a word.
 *
 * Before this, "assessment scheduled" was a status on an application and nothing else. No
 * date, no place, no list. The school could not pull a list for Sunday, so it lived on
 * paper, and the platform used the word "scheduled" about something it knew nothing about.
 *
 * TWO THINGS ON THIS SCREEN EXIST TO STOP IT LYING.
 *
 * 1. **"Not marked" is drawn as its own state, never as absent.** A register nobody has
 *    filled in and a test nobody came to are opposite facts, and the count line says which
 *    one you are looking at.
 * 2. **A mark goes to the application in the same action.** If the application refuses it,
 *    the screen says so and nothing is stored, so a mark can never sit on this list while
 *    the application shows none.
 */

const blankTest = {
  title: '', scheduled_for: '', start_time: '', place: '', class_applying: '',
  maximum_marks: '', notes: '',
};

async function request(url, options = {}) {
  const response = await apiFetch(url, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'That was refused.');
  return body;
}

export default function AdmissionTests({ reloadKey = 0 }) {
  const [tests, setTests] = useState([]);
  const [openId, setOpenId] = useState('');
  const [detail, setDetail] = useState(null);
  const [applications, setApplications] = useState([]);
  const [form, setForm] = useState(blankTest);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const body = await request(`${API}/admissions/tests`);
      setTests(body.data || []);
    } catch (err) { setError(err.message); }
  }, []);
  useEffect(() => { load(); }, [load, reloadKey]);

  const openTest = useCallback(async (testId) => {
    setError(''); setNotice(''); setOpenId(testId);
    try {
      const [body, applicationBody] = await Promise.all([
        request(`${API}/admissions/tests/${encodeURIComponent(testId)}`),
        request(`${API}/admissions/applications`),
      ]);
      setDetail(body.data);
      setApplications(applicationBody.data || []);
    } catch (err) { setError(err.message); setDetail(null); }
  }, []);

  async function create(event) {
    event.preventDefault();
    setBusy('new'); setError(''); setNotice('');
    try {
      const body = await request(`${API}/admissions/tests`, {
        method: 'POST',
        body: JSON.stringify({ ...form, maximum_marks: Number(form.maximum_marks) }),
      });
      setForm(blankTest); setShowForm(false);
      setNotice(`Test created for ${body.data.scheduled_for} at ${body.data.place}.`);
      await load();
      await openTest(body.data.id);
    } catch (err) { setError(err.message); }
    setBusy('');
  }

  async function seat(applicationId) {
    setBusy(applicationId); setError(''); setNotice('');
    try {
      const body = await request(`${API}/admissions/tests/${encodeURIComponent(openId)}/seats`, {
        method: 'POST', body: JSON.stringify({ application_ids: [applicationId] }),
      });
      // Both halves, always. A partly refused request that reported only its successes
      // would read as a complete one.
      const seated = body.data.seated.length;
      const refused = body.data.refused;
      setNotice(seated
        ? `${body.data.seated[0].applicant_name} added to the list.`
        : `Not added. ${refused[0]?.reason || ''}`);
      await openTest(openId);
    } catch (err) { setError(err.message); }
    setBusy('');
  }

  async function markSeat(seatRow, payload) {
    setBusy(seatRow.id); setError(''); setNotice('');
    try {
      await request(
        `${API}/admissions/tests/${encodeURIComponent(openId)}/seats/${encodeURIComponent(seatRow.id)}`,
        { method: 'PATCH', body: JSON.stringify(payload) },
      );
      await openTest(openId);
    } catch (err) {
      // The mark did not reach the application, so it is not on this list either. Say so
      // rather than leaving the row looking saved.
      setError(`${seatRow.applicant_name}: ${err.message}`);
    }
    setBusy('');
  }

  const counts = detail?.counts;
  const seatedIds = new Set((detail?.seats || []).map(row => row.application_id));
  const seatable = applications.filter(row => !seatedIds.has(row.id)
    && !['enrolled', 'rejected', 'withdrawn'].includes(row.status));

  return (
    <section aria-label="Entrance tests" style={panel}>
      <div style={headerRow}>
        <div>
          <h3 style={title}><CalendarDays size={16} />Entrance tests</h3>
          <p style={hint}>A test with a date, a place, and the list of who is sitting it.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" onClick={() => setShowForm(value => !value)} style={primary}>
            <Plus size={13} />Test
          </button>
          <button type="button" onClick={load} style={icon} aria-label="Refresh tests">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {error && <div role="alert" style={errorBox}>{error}</div>}
      {notice && <div role="status" style={noticeBox}>{notice}</div>}

      {showForm && (
        <form onSubmit={create} style={card}>
          <div style={grid}>
            <label style={label}>Title
              <input value={form.title} required style={input}
                onChange={e => setForm(v => ({ ...v, title: e.target.value }))} />
            </label>
            <label style={label}>Date
              <input type="date" value={form.scheduled_for} required style={input}
                onChange={e => setForm(v => ({ ...v, scheduled_for: e.target.value }))} />
            </label>
            <label style={label}>Start time
              <input type="time" value={form.start_time} style={input}
                onChange={e => setForm(v => ({ ...v, start_time: e.target.value }))} />
            </label>
            <label style={label}>Place
              <input value={form.place} required style={input} placeholder="e.g. Main hall"
                onChange={e => setForm(v => ({ ...v, place: e.target.value }))} />
            </label>
            <label style={label}>Class
              <input value={form.class_applying} style={input} placeholder="Optional"
                onChange={e => setForm(v => ({ ...v, class_applying: e.target.value }))} />
            </label>
            <label style={label}>Total marks
              <input type="number" min="1" value={form.maximum_marks} required style={input}
                onChange={e => setForm(v => ({ ...v, maximum_marks: e.target.value }))} />
            </label>
          </div>
          <p style={hint}>
            Everyone sitting this test is marked out of the same total, and the total is
            locked once the first mark is entered.
          </p>
          <button type="submit" disabled={busy === 'new'} style={primary}>
            {busy === 'new' ? 'Saving...' : 'Create test'}
          </button>
        </form>
      )}

      {tests.length === 0 && <p style={hint}>No entrance tests yet.</p>}

      {tests.map(test => (
        <div key={test.id} style={card}>
          <button type="button" onClick={() => (openId === test.id ? setOpenId('') : openTest(test.id))}
            style={testRow}>
            <span style={{ fontWeight: 600 }}>{test.title}</span>
            <span style={hint}>
              {test.scheduled_for}{test.start_time ? `, ${test.start_time}` : ''} at {test.place}
              {test.status === 'cancelled' && ' (cancelled)'}
            </span>
            <span style={hint}>
              {test.counts.seated} sitting it
              {test.counts.not_yet_marked > 0 && `, ${test.counts.not_yet_marked} not yet marked`}
            </span>
          </button>

          {openId === test.id && detail && (
            <div style={{ marginTop: 12 }}>
              {/* The count line. "Not yet marked" is its own number on purpose: a register
                  nobody has filled in must never read as a test nobody came to. */}
              <p style={countLine}>
                {counts.seated} on the list · {counts.present} present · {counts.absent} absent ·{' '}
                <strong>{counts.not_yet_marked} not yet marked</strong> · {counts.scored} marked
                {counts.present_but_not_yet_scored > 0
                  && ` · ${counts.present_but_not_yet_scored} present with no mark yet`}
              </p>

              <table style={table}>
                <thead>
                  <tr><th style={th}>Applicant</th><th style={th}>Guardian</th>
                    <th style={th}>Turned up?</th><th style={th}>Mark (out of {test.maximum_marks})</th></tr>
                </thead>
                <tbody>
                  {detail.seats.map(row => (
                    <tr key={row.id}>
                      <td style={td}>{row.applicant_name || '(application not found)'}</td>
                      <td style={td}>{row.guardian_name}<br /><span style={hint}>{row.guardian_phone}</span></td>
                      <td style={td}>
                        <button type="button" disabled={busy === row.id}
                          onClick={() => markSeat(row, { attendance: 'present' })}
                          style={row.attendance === 'present' ? chosen : choice}>Present</button>
                        <button type="button" disabled={busy === row.id}
                          onClick={() => markSeat(row, { attendance: 'absent' })}
                          style={row.attendance === 'absent' ? chosen : choice}>Absent</button>
                        {row.attendance === null && <span style={unmarked}>not marked yet</span>}
                      </td>
                      <td style={td}>
                        {row.score !== null && row.score !== undefined
                          ? <span>{row.score}</span>
                          : row.attendance === 'present'
                            ? <input type="number" min="0" max={test.maximum_marks}
                                aria-label={`Mark for ${row.applicant_name}`}
                                style={{ ...input, width: 90 }}
                                onBlur={e => e.target.value !== ''
                                  && markSeat(row, { score: Number(e.target.value) })} />
                            : <span style={hint}>mark them present first</span>}
                      </td>
                    </tr>
                  ))}
                  {detail.seats.length === 0 && (
                    <tr><td style={td} colSpan={4}>Nobody is on this list yet.</td></tr>
                  )}
                </tbody>
              </table>

              {test.status !== 'cancelled' && (
                <div style={{ marginTop: 12 }}>
                  <p style={hint}>Add an applicant to this test:</p>
                  {seatable.length === 0 && <p style={hint}>No applications left to add.</p>}
                  {seatable.slice(0, 25).map(application => (
                    <button key={application.id} type="button" disabled={busy === application.id}
                      onClick={() => seat(application.id)} style={choice}>
                      {application.applicant_name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </section>
  );
}

const panel = { padding: 4 };
const headerRow = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8, marginBottom: 12 };
const title = { display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)' };
const hint = { fontSize: 11, color: 'var(--color-text-secondary)', margin: '2px 0' };
const card = { border: '1px solid var(--color-border)', borderRadius: 10, padding: 14, marginBottom: 12, background: 'var(--color-surface-raised)' };
const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 };
const label = { display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--color-text-secondary)' };
const input = { padding: '9px 10px', minHeight: 40, fontSize: 16, borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-primary)' };
const primary = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 13px', minHeight: 40, borderRadius: 8, border: '1px solid var(--accent-primary)', background: 'var(--accent-primary)', color: '#fff', fontWeight: 600, cursor: 'pointer' };
const icon = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', minWidth: 40, minHeight: 40, borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)', cursor: 'pointer' };
const testRow = { display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start', width: '100%', minHeight: 40, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-text-primary)', textAlign: 'left' };
const countLine = { fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 8 };
const table = { width: '100%', borderCollapse: 'collapse', fontSize: 12 };
const th = { textAlign: 'left', padding: '6px 8px', borderBottom: '1px solid var(--color-border)', color: 'var(--color-text-secondary)', fontSize: 11 };
const td = { padding: '8px', borderBottom: '1px solid var(--color-border)', color: 'var(--color-text-primary)', verticalAlign: 'top' };
const choice = { minHeight: 40, padding: '6px 10px', marginRight: 6, marginBottom: 6, borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-primary)', cursor: 'pointer', fontSize: 11 };
const chosen = { ...choice, border: '1px solid var(--accent-primary)', background: 'var(--accent-primary)', color: '#fff', fontWeight: 600 };
const unmarked = { fontSize: 10, color: 'var(--color-text-secondary)', fontStyle: 'italic' };
const errorBox = { padding: 10, marginBottom: 10, borderRadius: 8, background: 'rgba(248,113,113,.12)', color: 'var(--tool-hex-f87171)', fontSize: 12 };
const noticeBox = { padding: 10, marginBottom: 10, borderRadius: 8, background: 'rgba(16,185,129,.12)', color: '#10b981', fontSize: 12 };
