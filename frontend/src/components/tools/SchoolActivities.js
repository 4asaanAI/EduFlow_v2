import React, { useCallback, useEffect, useState } from 'react';
import { useUser } from '../../contexts/UserContext';
import { Award, Plus, Shield, Star, Trash2, Trophy, Users, X } from 'lucide-react';
import { getAuthHeaders } from '../../lib/authSession';

const API = process.env.REACT_APP_BACKEND_URL;

// Normalize FastAPI error shapes into a plain string.
// FastAPI 422 returns {"detail": [{msg, loc, type}]} — not a string.
// FastAPI 400/404 returns {"detail": "string"}.
function extractDetail(data, fallback = 'An error occurred') {
  if (!data) return fallback;
  if (Array.isArray(data.detail)) {
    return data.detail.map(e => e.msg || String(e)).join(', ') || fallback;
  }
  if (typeof data.detail === 'string') return data.detail;
  return fallback;
}

async function apiFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  let data;
  try {
    data = await res.json();
  } catch {
    return { success: false, detail: `Error ${res.status}` };
  }
  if (!res.ok) {
    return { success: false, detail: extractDetail(data, `Error ${res.status}`) };
  }
  return data;
}

const listHouses = () => apiFetch(`${API}/api/activities/houses`, { headers: getAuthHeaders() });
const awardPoints = (houseId, delta, reason) => apiFetch(`${API}/api/activities/houses/${houseId}/points`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ delta, reason }) });
const listPositions = () => apiFetch(`${API}/api/activities/positions`, { headers: getAuthHeaders() });
const assignPosition = (data) => apiFetch(`${API}/api/activities/positions`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(data) });
const removePosition = (id) => apiFetch(`${API}/api/activities/positions/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
const listTeams = () => apiFetch(`${API}/api/activities/teams`, { headers: getAuthHeaders() });
const createTeam = (data) => apiFetch(`${API}/api/activities/teams`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(data) });
const deleteTeam = (id) => apiFetch(`${API}/api/activities/teams/${id}`, { method: 'DELETE', headers: getAuthHeaders() });

// ─── Shared UI ────────────────────────────────────────────────────────────────

const inp = {
  width: '100%', background: 'var(--c-bg)', border: '1px solid var(--c-border)',
  borderRadius: 8, padding: '9px 12px', color: 'var(--c-text)', fontSize: 13,
  outline: 'none', boxSizing: 'border-box',
};

function Btn({ children, onClick, disabled, variant = 'primary', type = 'button', title, small }) {
  const secondary = variant === 'secondary';
  const danger = variant === 'danger';
  return (
    <button type={type} title={title} onClick={onClick} disabled={disabled} style={{
      minHeight: small ? 30 : 36, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
      background: danger ? '#7f1d1d' : secondary ? 'var(--c-bg)' : '#4f8ff7',
      border: secondary ? '1px solid var(--c-border)' : 'none',
      borderRadius: 7, padding: small ? '4px 10px' : '7px 13px',
      color: danger || !secondary ? '#fff' : 'var(--c-muted)',
      fontSize: small ? 11 : 12, fontWeight: 600,
      cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.6 : 1,
    }}>{children}</button>
  );
}

function ErrorMsg({ msg }) {
  if (!msg) return null;
  return <div style={{ color: '#f87171', fontSize: 11, marginTop: 8 }}>{msg}</div>;
}

// ─── House colour mapping ─────────────────────────────────────────────────────

const HOUSE_STYLES = {
  Blue:   { bg: 'rgba(59,130,246,0.12)',  border: 'rgba(59,130,246,0.35)',  text: '#3b82f6' },
  Green:  { bg: 'rgba(34,197,94,0.12)',   border: 'rgba(34,197,94,0.35)',   text: '#22c55e' },
  Red:    { bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.35)',   text: '#ef4444' },
  Yellow: { bg: 'rgba(234,179,8,0.12)',   border: 'rgba(234,179,8,0.35)',   text: '#eab308' },
};

// ─── Houses tab ───────────────────────────────────────────────────────────────

function HousesTab({ canManage }) {
  const [houses, setHouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pointsModal, setPointsModal] = useState(null);
  const [delta, setDelta] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [pointsError, setPointsError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listHouses();
      if (res.success) setHouses(res.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const sorted = [...houses].sort((a, b) => b.points - a.points);
  const maxPoints = Math.max(...houses.map(h => h.points || 0), 1);

  const openPointsModal = (house, defaultDelta) => {
    setPointsModal(house);
    setDelta(defaultDelta);
    setReason('');
    setPointsError('');
  };

  const submitPoints = async () => {
    const parsed = parseInt(delta);
    if (!delta || isNaN(parsed)) return;
    setSaving(true);
    setPointsError('');
    const res = await awardPoints(pointsModal.id, parsed, reason);
    if (res.success) {
      setPointsModal(null);
      setDelta('');
      setReason('');
      load();
    } else {
      setPointsError(res.detail || 'Failed to update points');
    }
    setSaving(false);
  };

  return (
    <div>
      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>Loading houses…</div>
      ) : (
        <>
          {/* Leaderboard podium */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-end', gap: 12, marginBottom: 28, padding: '0 8px' }}>
            {sorted.slice(0, 4).map((house, i) => {
              const style = HOUSE_STYLES[house.name] || HOUSE_STYLES.Blue;
              const heights = [120, 90, 75, 60];
              return (
                <div key={house.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, flex: 1 }}>
                  {i === 0 && <Trophy size={20} color={style.text} />}
                  <div style={{ fontWeight: 700, fontSize: 18, color: style.text }}>{house.points}</div>
                  <div style={{ width: '100%', height: heights[i], background: style.bg, border: `2px solid ${style.border}`, borderRadius: '8px 8px 0 0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: style.text }}>{house.name}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 600 }}>#{i + 1}</div>
                </div>
              );
            })}
          </div>

          {/* Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            {sorted.map(house => {
              const style = HOUSE_STYLES[house.name] || HOUSE_STYLES.Blue;
              const pct = maxPoints > 0 ? Math.round((house.points / maxPoints) * 100) : 0;
              return (
                <div key={house.id} style={{ background: style.bg, border: `1px solid ${style.border}`, borderRadius: 12, padding: '16px 18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: style.text }}>{house.name} House</div>
                      <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--c-text)', marginTop: 2 }}>{house.points} <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--c-faint)' }}>pts</span></div>
                    </div>
                    <Shield size={22} color={style.text} style={{ opacity: 0.7 }} />
                  </div>
                  <div style={{ height: 5, background: 'var(--c-border)', borderRadius: 4, overflow: 'hidden', marginBottom: 12 }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: style.text, borderRadius: 4, transition: 'width 0.4s ease' }} />
                  </div>
                  {canManage && (
                    <div style={{ display: 'flex', gap: 6 }}>
                      <Btn small onClick={() => openPointsModal(house, '+5')} style={{ flex: 1, justifyContent: 'center' }}>+ Award</Btn>
                      <Btn small variant="secondary" onClick={() => openPointsModal(house, '-5')}>Deduct</Btn>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Points modal */}
      {pointsModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 16 }}>
          <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 12, padding: 24, width: 380, maxWidth: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--c-text)' }}>
                {parseInt(delta) >= 0 ? 'Award' : 'Deduct'} Points — {pointsModal.name} House
              </h3>
              <button onClick={() => setPointsModal(null)} style={{ border: 'none', background: 'none', color: 'var(--c-faint)', cursor: 'pointer' }}><X size={16} /></button>
            </div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--c-faint)', marginBottom: 6 }}>
              Points (use negative to deduct)
            </label>
            <input type="number" value={delta} onChange={e => setDelta(e.target.value)} style={{ ...inp, marginBottom: 12 }} placeholder="+5 or -2" />
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--c-faint)', marginBottom: 6 }}>Reason</label>
            <input value={reason} onChange={e => setReason(e.target.value)} style={{ ...inp, marginBottom: 4 }} placeholder="e.g. Won cricket match" />
            <ErrorMsg msg={pointsError} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <Btn variant="secondary" onClick={() => setPointsModal(null)}>Cancel</Btn>
              <Btn disabled={!delta || isNaN(parseInt(delta)) || saving} onClick={submitPoints}>
                {saving ? 'Saving…' : 'Confirm'}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Positions tab ────────────────────────────────────────────────────────────

const ALL_POSITIONS = [
  'Head Boy', 'Head Girl', 'Vice Head Boy', 'Vice Head Girl',
  'House Captain', 'Vice House Captain', 'Sports Captain', 'Vice Sports Captain',
  'Class Monitor', 'Assistant Monitor', 'Prefect', 'Council Member',
];

function PositionsTab({ canManage }) {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ student_name: '', position: '', house: '', academic_year: '', notes: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listPositions();
      if (res.success) setPositions(res.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const openModal = () => {
    setForm({ student_name: '', position: '', house: '', academic_year: '', notes: '' });
    setError('');
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setError('');
  };

  const active = positions.filter(p => p.is_active !== false);
  const grouped = ALL_POSITIONS.reduce((acc, pos) => {
    const match = active.filter(p => p.position === pos);
    if (match.length > 0) acc[pos] = match;
    return acc;
  }, {});

  const submit = async () => {
    if (!form.student_name.trim()) { setError('Student name is required'); return; }
    if (!form.position) { setError('Position is required'); return; }
    setSaving(true);
    setError('');
    const res = await assignPosition({
      ...form,
      student_name: form.student_name.trim(),
      student_id: form.student_name.trim().toLowerCase().replace(/\s+/g, '-') + '-' + Date.now(),
    });
    if (res.success) {
      closeModal();
      load();
    } else {
      setError(res.detail || 'Unable to assign position');
    }
    setSaving(false);
  };

  const handleRemove = async (p) => {
    const res = await removePosition(p.id);
    if (res.success) {
      load();
    }
  };

  const POSITION_ICONS = { 'Head Boy': '👑', 'Head Girl': '👑', 'Prefect': '⭐', 'House Captain': '🛡️', 'Sports Captain': '🏅', 'Class Monitor': '📋' };

  const handleRemoveAll = async () => {
    if (!window.confirm(`Remove all ${active.length} active position${active.length !== 1 ? 's' : ''}? This cannot be undone.`)) return;
    for (const p of active) { await removePosition(p.id); }
    load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontSize: 13, color: 'var(--c-muted)' }}>{active.length} active position{active.length !== 1 ? 's' : ''}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {canManage && active.length > 0 && (
            <Btn variant="danger" small onClick={handleRemoveAll}><Trash2 size={12} />Remove All</Btn>
          )}
          {canManage && <Btn onClick={openModal}><Plus size={13} />Assign Position</Btn>}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>Loading…</div>
      ) : active.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>No positions assigned yet</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
          {Object.entries(grouped).map(([posName, holders]) =>
            holders.map(p => {
              const hs = p.house ? HOUSE_STYLES[p.house] : null;
              return (
                <div key={p.id} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <div style={{ width: 36, height: 36, borderRadius: 8, background: hs ? hs.bg : 'var(--c-input)', border: `1px solid ${hs ? hs.border : 'var(--c-border)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>
                      {POSITION_ICONS[posName] || '🎖️'}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--c-text)' }}>{p.student_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--c-faint)', marginTop: 2 }}>{posName}</div>
                      {p.house && <div style={{ fontSize: 10, fontWeight: 600, color: hs?.text, marginTop: 2 }}>{p.house} House</div>}
                    </div>
                  </div>
                  {canManage && (
                    <button onClick={() => handleRemove(p)} title="Remove position" style={{ border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.07)', borderRadius: 6, cursor: 'pointer', color: '#ef4444', padding: '4px 6px', display: 'flex', alignItems: 'center' }}><Trash2 size={12} /></button>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 16 }}>
          <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 12, padding: 24, width: 420, maxWidth: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--c-text)' }}>Assign Position</h3>
              <button onClick={closeModal} style={{ border: 'none', background: 'none', color: 'var(--c-faint)', cursor: 'pointer' }}><X size={16} /></button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Student Name
                <input
                  value={form.student_name}
                  onChange={e => setForm(f => ({ ...f, student_name: e.target.value }))}
                  style={{ ...inp, marginTop: 5 }}
                  placeholder="Full name"
                />
              </label>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Position
                <select
                  value={form.position}
                  onChange={e => setForm(f => ({ ...f, position: e.target.value }))}
                  style={{ ...inp, marginTop: 5 }}
                >
                  <option value="">Select position</option>
                  {ALL_POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </label>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>House
                <select
                  value={form.house}
                  onChange={e => setForm(f => ({ ...f, house: e.target.value }))}
                  style={{ ...inp, marginTop: 5 }}
                >
                  <option value="">No house</option>
                  {['Blue', 'Green', 'Red', 'Yellow'].map(h => <option key={h} value={h}>{h}</option>)}
                </select>
              </label>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--c-faint)', fontWeight: 700 }}>Academic Year
                <input
                  value={form.academic_year}
                  onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))}
                  style={{ ...inp, marginTop: 5 }}
                  placeholder="e.g. 2025-26"
                />
              </label>
            </div>
            <ErrorMsg msg={error} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <Btn variant="secondary" onClick={closeModal}>Cancel</Btn>
              <Btn disabled={saving} onClick={submit}>{saving ? 'Saving…' : 'Assign'}</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sports Teams tab ─────────────────────────────────────────────────────────

const ALL_SPORTS = [
  'Cricket', 'Football', 'Basketball', 'Volleyball', 'Kabaddi', 'Badminton',
  'Chess', 'Table Tennis', 'Debate', 'Quiz', 'Athletics', 'Swimming',
  'Kho-Kho', 'Handball',
];

const SPORT_EMOJI = {
  Cricket: '🏏', Football: '⚽', Basketball: '🏀', Volleyball: '🏐',
  Kabaddi: '🤼', Badminton: '🏸', Chess: '♟️', 'Table Tennis': '🏓',
  Debate: '🎤', Quiz: '🧠', Athletics: '🏃', Swimming: '🏊',
  'Kho-Kho': '🏃', Handball: '🤾',
};

function TeamsTab({ canManage }) {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: '', sport: '', captain_name: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listTeams();
      if (res.success) setTeams(res.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const openModal = () => {
    setForm({ name: '', sport: '', captain_name: '' });
    setError('');
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setError('');
  };

  const submit = async () => {
    if (!form.sport) { setError('Please select a sport'); return; }
    if (!form.name.trim()) { setError('Team name is required'); return; }
    setSaving(true);
    setError('');
    try {
      const res = await createTeam({ ...form, name: form.name.trim() });
      if (res.success) {
        closeModal();
        load();
      } else {
        setError(res.detail || 'Failed to create team');
      }
    } catch {
      setError('Network error — please try again');
    }
    setSaving(false);
  };

  const handleDelete = async (team) => {
    if (!window.confirm(`Delete "${team.name}"?`)) return;
    const res = await deleteTeam(team.id);
    if (res.success) load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: 'var(--c-muted)' }}>{teams.length} team{teams.length !== 1 ? 's' : ''}</div>
        {canManage && <Btn onClick={openModal}><Plus size={13} />New Team</Btn>}
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>Loading…</div>
      ) : teams.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>No sports teams created yet</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
          {teams.map(team => (
            <div key={team.id} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 12, padding: '16px 18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div style={{ fontSize: 28 }}>{SPORT_EMOJI[team.sport] || '🏆'}</div>
                {canManage && (
                  <button
                    onClick={() => handleDelete(team)}
                    style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--c-faint)', padding: 2 }}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--c-text)' }}>{team.name}</div>
              <div style={{ fontSize: 12, color: 'var(--c-muted)', marginTop: 2 }}>{team.sport}</div>
              {team.captain_name && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 8, fontSize: 11, color: 'var(--c-faint)' }}>
                  <Star size={11} />Captain: {team.captain_name}
                </div>
              )}
              {team.members?.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, fontSize: 11, color: 'var(--c-faint)' }}>
                  <Users size={11} />{team.members.length} member{team.members.length !== 1 ? 's' : ''}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 16 }}>
          <div style={{ background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 12, padding: 24, width: 400, maxWidth: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--c-text)' }}>New Sports Team</h3>
              <button onClick={closeModal} style={{ border: 'none', background: 'none', color: 'var(--c-faint)', cursor: 'pointer' }}><X size={16} /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, display: 'block' }}>Sport
                <select
                  value={form.sport}
                  onChange={e => setForm(f => ({ ...f, sport: e.target.value }))}
                  style={{ ...inp, marginTop: 5 }}
                >
                  <option value="">Select sport</option>
                  {ALL_SPORTS.map(s => <option key={s} value={s}>{SPORT_EMOJI[s]} {s}</option>)}
                </select>
              </label>
              <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, display: 'block' }}>Team Name
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  style={{ ...inp, marginTop: 5 }}
                  placeholder="e.g. Cricket U-14 Boys"
                />
              </label>
              <label style={{ fontSize: 11, color: 'var(--c-faint)', fontWeight: 700, display: 'block' }}>Captain Name
                <input
                  value={form.captain_name}
                  onChange={e => setForm(f => ({ ...f, captain_name: e.target.value }))}
                  style={{ ...inp, marginTop: 5 }}
                  placeholder="Optional"
                />
              </label>
            </div>
            <ErrorMsg msg={error} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <Btn variant="secondary" onClick={closeModal}>Cancel</Btn>
              <Btn disabled={!form.name.trim() || !form.sport || saving} onClick={submit}>
                {saving ? 'Saving…' : 'Create Team'}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

const TABS = [
  { id: 'houses', label: 'Houses', icon: Shield },
  { id: 'positions', label: 'Positions', icon: Award },
  { id: 'teams', label: 'Sports Teams', icon: Trophy },
];

export default function SchoolActivities() {
  const { currentUser } = useUser();
  const [tab, setTab] = useState('houses');
  const canManage = ['owner', 'admin'].includes(currentUser.role);

  return (
    <div style={{ padding: 24, overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--c-text)', margin: 0 }}>School Activities</h1>
          <div style={{ fontSize: 12, color: 'var(--c-faint)', marginTop: 3 }}>Houses · Positions · Sports Teams</div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 22, borderBottom: '1px solid var(--c-border)' }}>
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px', fontSize: 13,
              fontWeight: tab === t.id ? 700 : 500,
              color: tab === t.id ? '#4f8ff7' : 'var(--c-muted)',
              background: 'transparent', border: 'none',
              borderBottom: tab === t.id ? '2px solid #4f8ff7' : '2px solid transparent',
              cursor: 'pointer', marginBottom: -1,
            }}>
              <Icon size={14} />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === 'houses' && <HousesTab canManage={canManage} />}
      {tab === 'positions' && <PositionsTab canManage={canManage} />}
      {tab === 'teams' && <TeamsTab canManage={canManage} />}
    </div>
  );
}
