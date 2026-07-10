/**
 * R10.4 — "What I've Learned" transparency & control surface (Owner/Principal).
 *
 * Lists everything the assistant has learned about you: active memories, saved
 * routines (skills), and pending correction candidates from 👎 Improve feedback.
 * You stay in control: edit / deactivate / delete memories, delete routines, and
 * activate or reject pending corrections. Bulk delete is two-step (preview → confirm).
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { ToolPage } from './ToolPage';
import { Brain, Sparkles, MessageSquareWarning, Trash2, Check, X, Pencil, EyeOff, Eye } from 'lucide-react';
import {
  getLearningOverview, activateCorrection, rejectCorrection,
  editMemory, deactivateMemory, deleteMemory, bulkDeleteMemories, deleteSkill,
} from '../../lib/api';

const tint = (color, amount) => `color-mix(in srgb, ${color} ${amount}%, transparent)`;

function Section({ title, icon: Icon, count, children, isDark }) {
  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#737373';
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Icon size={16} color="#a78bfa" />
        <h2 style={{ fontSize: 15, fontWeight: 700, color: text, margin: 0 }}>{title}</h2>
        <span style={{ fontSize: 12, color: muted }}>({count})</span>
      </div>
      {children}
    </div>
  );
}

function Btn({ onClick, children, color = '#4f8ff7', disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px',
      borderRadius: 7, border: 'none', cursor: disabled ? 'default' : 'pointer',
      background: tint(color, 12), color, fontSize: 12, fontWeight: 600, opacity: disabled ? 0.5 : 1,
    }}>{children}</button>
  );
}

export default function LearningTools() {
  const { isDark } = useTheme();
  const [data, setData] = useState({ memories: [], deactivated_memories: [], skills: [], pending_corrections: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null);   // memory id being edited
  const [editText, setEditText] = useState('');

  const text = isDark ? '#f5f5f5' : '#171717';
  const muted = isDark ? '#888' : '#737373';
  const border = isDark ? '#2e2e2e' : '#e5e5e5';
  const card = isDark ? '#1e1e1e' : '#fff';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getLearningOverview();
      if (res && res.success) setData(res.data);
      else setError('Could not load learned data.');
    } catch {
      setError('Could not load learned data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const rowStyle = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
    background: card, border: `1px solid ${border}`, borderRadius: 10, padding: '10px 14px', marginBottom: 8,
  };

  const onActivate = async (id) => { await activateCorrection(id); load(); };
  const onReject = async (id) => { await rejectCorrection(id); load(); };
  const onDeactivate = async (id) => { await deactivateMemory(id, true); load(); };
  const onReactivate = async (id) => { await deactivateMemory(id, false); load(); };
  const onDeleteMemory = async (id) => { await deleteMemory(id); load(); };
  const onDeleteSkill = async (id) => { await deleteSkill(id); load(); };
  const saveEdit = async (id) => {
    if (editText.trim()) await editMemory(id, editText.trim());
    setEditing(null); setEditText(''); load();
  };

  return (
    <ToolPage
      title="What I've Learned"
      subtitle="Review and control what the assistant remembers about you. Nothing here is used until you approve it."
      onRefresh={load}
      loading={loading}
    >
      {error && <div style={{ color: '#f87171', fontSize: 13, marginBottom: 16 }}>{error}</div>}

      {/* Pending corrections from 👎 Improve feedback */}
      <Section title="Pending suggestions" icon={MessageSquareWarning} count={data.pending_corrections.length} isDark={isDark}>
        {data.pending_corrections.length === 0 && (
          <p style={{ fontSize: 13, color: muted }}>No pending suggestions. When you tap “Improve” on a reply and add a note, it appears here for your approval before the assistant learns from it.</p>
        )}
        {data.pending_corrections.map(c => (
          <div key={c.id} style={rowStyle}>
            <span style={{ flex: 1, fontSize: 13, color: text }}>{c.candidate_correction}</span>
            <div style={{ display: 'flex', gap: 6 }}>
              <Btn onClick={() => onActivate(c.id)} color="#34d399"><Check size={13} /> Activate</Btn>
              <Btn onClick={() => onReject(c.id)} color="#f87171"><X size={13} /> Reject</Btn>
            </div>
          </div>
        ))}
      </Section>

      {/* Active memories */}
      <Section title="Remembered notes" icon={Brain} count={data.memories.length} isDark={isDark}>
        {data.memories.length === 0 && <p style={{ fontSize: 13, color: muted }}>No remembered notes yet.</p>}
        {data.memories.map(m => (
          <div key={m.id} style={rowStyle}>
            {editing === m.id ? (
              <>
                <input
                  value={editText}
                  onChange={e => setEditText(e.target.value)}
                  maxLength={500}
                  style={{ flex: 1, fontSize: 13, padding: '6px 10px', borderRadius: 6, border: `1px solid ${border}`, background: isDark ? '#141414' : '#fff', color: text }}
                />
                <div style={{ display: 'flex', gap: 6 }}>
                  <Btn onClick={() => saveEdit(m.id)} color="#34d399"><Check size={13} /> Save</Btn>
                  <Btn onClick={() => { setEditing(null); setEditText(''); }} color="#888"><X size={13} /></Btn>
                </div>
              </>
            ) : (
              <>
                <span style={{ flex: 1, fontSize: 13, color: text }}>
                  <span style={{ fontSize: 11, color: muted, marginRight: 6 }}>[{m.category}]</span>
                  {m.text}
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <Btn onClick={() => { setEditing(m.id); setEditText(m.text || ''); }} color="#4f8ff7"><Pencil size={13} /> Edit</Btn>
                  <Btn onClick={() => onDeactivate(m.id)} color="#facc15"><EyeOff size={13} /> Deactivate</Btn>
                  <Btn onClick={() => onDeleteMemory(m.id)} color="#f87171"><Trash2 size={13} /> Delete</Btn>
                </div>
              </>
            )}
          </div>
        ))}
      </Section>

      {/* Deactivated memories — kept for history, reactivatable */}
      {data.deactivated_memories.length > 0 && (
        <Section title="Deactivated notes" icon={EyeOff} count={data.deactivated_memories.length} isDark={isDark}>
          {data.deactivated_memories.map(m => (
            <div key={m.id} style={{ ...rowStyle, opacity: 0.7 }}>
              <span style={{ flex: 1, fontSize: 13, color: muted, textDecoration: 'line-through' }}>{m.text}</span>
              <div style={{ display: 'flex', gap: 6 }}>
                <Btn onClick={() => onReactivate(m.id)} color="#34d399"><Eye size={13} /> Reactivate</Btn>
                <Btn onClick={() => onDeleteMemory(m.id)} color="#f87171"><Trash2 size={13} /> Delete</Btn>
              </div>
            </div>
          ))}
        </Section>
      )}

      {/* Saved routines (skills) */}
      <Section title="Saved routines" icon={Sparkles} count={data.skills.length} isDark={isDark}>
        {data.skills.length === 0 && <p style={{ fontSize: 13, color: muted }}>No saved routines yet.</p>}
        {data.skills.map(s => (
          <div key={s.id} style={rowStyle}>
            <span style={{ flex: 1, fontSize: 13, color: text }}>
              {s.title}
              {s.needs_update && (
                <span style={{ marginLeft: 8, fontSize: 11, color: '#facc15' }}>⚠ needs updating</span>
              )}
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <Btn onClick={() => onDeleteSkill(s.id)} color="#f87171"><Trash2 size={13} /> Delete</Btn>
            </div>
          </div>
        ))}
      </Section>
    </ToolPage>
  );
}
