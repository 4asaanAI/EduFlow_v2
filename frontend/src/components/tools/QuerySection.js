import React, { useState, useEffect, useRef } from 'react';
import { useUser } from '../../contexts/UserContext';
import { useTheme } from '../../contexts/ThemeContext';
import { ToolPage } from './ToolPage';
import { getAuthHeaders } from '../../lib/authSession';
import {
  Plus, X, Paperclip, ChevronDown, CheckCircle2, Circle,
  AlertCircle, AlertTriangle, Info, Loader2, Trash2, FileVideo, Image,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

function authHeaders() {
  return getAuthHeaders(null);
}

const PRIORITY_META = {
  low:      { label: 'Low',      color: 'var(--tool-hex-34d399)', bg: 'rgba(52,211,153,0.1)',  icon: Info },
  medium:   { label: 'Medium',   color: 'var(--tool-hex-fbbf24)', bg: 'rgba(251,191,36,0.1)',  icon: AlertCircle },
  high:     { label: 'High',     color: 'var(--tool-hex-fb923c)', bg: 'rgba(251,146,60,0.1)',  icon: AlertTriangle },
  critical: { label: 'Critical', color: 'var(--tool-hex-f87171)', bg: 'rgba(248,113,113,0.1)', icon: AlertCircle },
};

const ROLE_COLORS = { owner: 'var(--tool-hex-fb923c)', admin: 'var(--tool-hex-4f8ff7)', teacher: 'var(--tool-hex-34d399)', student: 'var(--tool-hex-a78bfa)' };

function PriorityBadge({ priority }) {
  const meta = PRIORITY_META[priority] || PRIORITY_META.low;
  const Icon = meta.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: meta.bg, color: meta.color,
      fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 6,
    }}>
      <Icon size={10} />
      {meta.label}
    </span>
  );
}

function AttachmentPreview({ url, type, isDark }) {
  if (!url) return null;
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const bg = isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fafafa)';
  const isVideo = type === 'mp4';
  const isImage = ['png', 'jpg', 'jpeg'].includes(type);
  const fullUrl = process.env.REACT_APP_BACKEND_URL + url;

  if (isImage) {
    return (
      <a href={fullUrl} target="_blank" rel="noopener noreferrer">
        <img src={fullUrl} alt="attachment" style={{
          maxWidth: 180, maxHeight: 120, borderRadius: 8,
          border: `1px solid ${border}`, objectFit: 'cover', cursor: 'zoom-in',
        }} />
      </a>
    );
  }
  if (isVideo) {
    return (
      <a href={fullUrl} target="_blank" rel="noopener noreferrer" style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        background: bg, border: `1px solid ${border}`, borderRadius: 8,
        padding: '6px 10px', textDecoration: 'none', color: isDark ? 'var(--tool-hex-a0a0a0)' : 'var(--tool-hex-525252)',
        fontSize: 12,
      }}>
        <FileVideo size={14} color="var(--tool-hex-a78bfa)" /> View Recording
      </a>
    );
  }
  return null;
}

function isItTech(user) {
  return user.role === 'admin' && user.sub_category === 'it_tech';
}

function TicketCard({ ticket, currentUser, isDark, onResolve, onUnresolve, onDelete }) {
  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const card = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-ffffff)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)';
  const secondary = isDark ? 'var(--tool-hex-a0a0a0)' : 'var(--tool-hex-525252)';
  const resolved = ticket.status === 'resolved';
  const roleColor = ROLE_COLORS[ticket.created_by_role] || 'var(--tool-hex-737373)';
  const canDelete = isItTech(currentUser);
  const canResolve = isItTech(currentUser);

  return (
    <div style={{
      background: card, border: `1px solid ${resolved ? (isDark ? 'var(--tool-hex-1a3a2a)' : 'var(--tool-hex-d1fae5)') : border}`,
      borderRadius: 14, padding: '18px 20px', transition: 'border-color 0.2s ease',
      opacity: resolved ? 0.8 : 1,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <PriorityBadge priority={ticket.priority} />
            {resolved && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                background: 'rgba(52,211,153,0.1)', color: 'var(--tool-hex-34d399)',
                fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 6,
              }}>
                <CheckCircle2 size={10} /> Resolved
              </span>
            )}
          </div>
          <h3 style={{
            fontSize: 15, fontWeight: 600, color: resolved ? muted : text,
            margin: 0, textDecoration: resolved ? 'line-through' : 'none',
            letterSpacing: '-0.01em',
          }}>
            {ticket.title}
          </h3>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {canResolve && (
            <button
              onClick={() => resolved ? onUnresolve(ticket.id) : onResolve(ticket.id)}
              title={resolved ? 'Mark as open' : 'Mark as resolved'}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '6px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                fontSize: 12, fontWeight: 600,
                background: resolved ? (isDark ? 'var(--tool-hex-1a3a2a)' : 'var(--tool-hex-dcfce7)') : (isDark ? 'var(--tool-hex-1a2e1a)' : 'var(--tool-hex-f0fdf4)'),
                color: 'var(--tool-hex-34d399)', transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.75'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}
            >
              {resolved ? <Circle size={12} /> : <CheckCircle2 size={12} />}
              {resolved ? 'Reopen' : 'Resolve'}
            </button>
          )}
          {canDelete && (
            <button
              onClick={() => onDelete(ticket.id)}
              title="Delete ticket"
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 30, height: 30, borderRadius: 8, border: 'none', cursor: 'pointer',
                background: 'transparent', color: muted, transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(248,113,113,0.1)'; e.currentTarget.style.color = 'var(--tool-hex-f87171)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = muted; }}
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Description */}
      <p style={{ fontSize: 13, color: secondary, margin: '0 0 12px', lineHeight: 1.6 }}>
        {ticket.description}
      </p>

      {/* Attachment */}
      {ticket.attachment_url && (
        <div style={{ marginBottom: 12 }}>
          <AttachmentPreview url={ticket.attachment_url} type={ticket.attachment_type} isDark={isDark} />
        </div>
      )}

      {/* Footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            width: 18, height: 18, borderRadius: '50%', background: roleColor,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 9, fontWeight: 700, color: 'var(--tool-hex-fff)', flexShrink: 0,
          }}>
            {(ticket.created_by_name || '?')[0].toUpperCase()}
          </span>
          <span style={{ fontSize: 12, color: muted }}>
            {ticket.created_by_name}
            <span style={{ margin: '0 4px', color: isDark ? 'var(--tool-hex-333)' : 'var(--tool-hex-d5d5d5)' }}>·</span>
            <span style={{ color: roleColor, textTransform: 'capitalize' }}>{ticket.created_by_role}</span>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {resolved && ticket.resolved_by_name && (
            <span style={{ fontSize: 11, color: 'var(--tool-hex-34d399)' }}>
              ✓ by {ticket.resolved_by_name}
            </span>
          )}
          <span style={{ fontSize: 11, color: muted }}>
            {new Date(ticket.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
          </span>
        </div>
      </div>
    </div>
  );
}

export function QuerySection() {
  const { currentUser } = useUser();
  const { isDark } = useTheme();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [filter, setFilter] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', priority: 'medium' });
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [formError, setFormError] = useState('');
  const fileRef = useRef(null);

  const border = isDark ? 'var(--tool-hex-2e2e2e)' : 'var(--tool-hex-e5e5e5)';
  const card = isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-ffffff)';
  const text = isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)';
  const muted = isDark ? 'var(--tool-hex-666)' : 'var(--tool-hex-a3a3a3)';
  const secondary = isDark ? 'var(--tool-hex-a0a0a0)' : 'var(--tool-hex-525252)';
  const inputBg = isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-fafafa)';

  const load = async () => {
    setLoading(true);
    try {
      const params = filter !== 'all' ? `?status=${filter}` : '';
      const res = await fetch(`${API}/queries${params}`, { headers: authHeaders() });
      const data = await res.json();
      if (data.success) setTickets(data.data);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, [filter]);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['mp4', 'png', 'jpg', 'jpeg'].includes(ext)) {
      setFileError('Only mp4, png, jpg files allowed');
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setFileError('File too large. Max 20MB');
      return;
    }
    setFileError('');
    setFile(f);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.description.trim()) {
      setFormError('Title and description are required');
      return;
    }
    setFormError('');
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('title', form.title.trim());
      fd.append('description', form.description.trim());
      fd.append('priority', form.priority);
      if (file) fd.append('attachment', file);

      const res = await fetch(`${API}/queries`, {
        method: 'POST',
        headers: authHeaders(),
        body: fd,
      });
      const data = await res.json();
      if (data.success) {
        setTickets(prev => [data.data, ...prev]);
        setForm({ title: '', description: '', priority: 'medium' });
        setFile(null);
        setShowForm(false);
      } else {
        setFormError(data.detail || 'Failed to submit');
      }
    } catch {
      setFormError('Network error. Please try again.');
    }
    setSubmitting(false);
  };

  const handleResolve = async (id) => {
    try {
      const res = await fetch(`${API}/queries/${id}/resolve`, { method: 'PATCH', headers: authHeaders() });
      const data = await res.json();
      if (data.success) {
        setTickets(prev => prev.map(t => t.id === id
          ? { ...t, status: 'resolved', resolved_at: data.resolved_at, resolved_by_name: currentUser.name }
          : t
        ));
      }
    } catch {}
  };

  const handleUnresolve = async (id) => {
    try {
      const res = await fetch(`${API}/queries/${id}/unresolve`, { method: 'PATCH', headers: authHeaders() });
      const data = await res.json();
      if (data.success) {
        setTickets(prev => prev.map(t => t.id === id
          ? { ...t, status: 'open', resolved_at: null, resolved_by: null, resolved_by_name: null }
          : t
        ));
      }
    } catch {}
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this ticket?')) return;
    try {
      await fetch(`${API}/queries/${id}`, { method: 'DELETE', headers: authHeaders() });
      setTickets(prev => prev.filter(t => t.id !== id));
    } catch {}
  };

  const open = tickets.filter(t => t.status === 'open').length;
  const resolved = tickets.filter(t => t.status === 'resolved').length;

  const visibleTickets = filter === 'all' ? tickets
    : filter === 'open' ? tickets.filter(t => t.status === 'open')
    : tickets.filter(t => t.status === 'resolved');

  const inputStyle = {
    width: '100%', padding: '10px 13px', background: inputBg,
    border: `1px solid ${border}`, borderRadius: 10, color: text,
    fontSize: 14, outline: 'none', boxSizing: 'border-box',
  };

  return (
    <ToolPage
      title="Query & Support"
      subtitle="Submit issues and track resolutions — visible to all users"
      onRefresh={load}
      loading={loading}
      actions={
        <button
          onClick={() => setShowForm(v => !v)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 14px', borderRadius: 10, border: 'none', cursor: 'pointer',
            background: showForm ? (isDark ? 'var(--tool-hex-252525)' : 'var(--tool-hex-f5f5f5)') : (isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)'),
            color: showForm ? muted : (isDark ? 'var(--tool-hex-171717)' : 'var(--tool-hex-fff)'),
            fontSize: 13, fontWeight: 600, transition: 'all 0.15s ease',
          }}
        >
          {showForm ? <X size={14} /> : <Plus size={14} />}
          {showForm ? 'Cancel' : 'New Query'}
        </button>
      }
    >

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        {[
          { label: 'Total', value: tickets.length, color: 'var(--tool-hex-4f8ff7)' },
          { label: 'Open', value: open, color: 'var(--tool-hex-fb923c)' },
          { label: 'Resolved', value: resolved, color: 'var(--tool-hex-34d399)' },
        ].map(s => (
          <div key={s.label} style={{
            flex: '1 1 100px', background: card, border: `1px solid ${border}`,
            borderRadius: 12, padding: '14px 18px', minWidth: 100,
          }}>
            <p style={{ fontSize: 22, fontWeight: 700, color: s.color, margin: '0 0 2px', letterSpacing: '-0.02em' }}>{s.value}</p>
            <p style={{ fontSize: 12, color: muted, margin: 0 }}>{s.label}</p>
          </div>
        ))}
      </div>

      {/* New Query Form */}
      {showForm && (
        <div style={{
          background: card, border: `1px solid ${border}`, borderRadius: 16,
          padding: '22px 24px', marginBottom: 24,
        }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: text, margin: '0 0 18px', letterSpacing: '-0.01em' }}>
            Submit New Query
          </h3>
          <form onSubmit={handleSubmit}>
            {/* Title */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: secondary, marginBottom: 6 }}>
                Title *
              </label>
              <input
                type="text"
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                placeholder="Brief summary of your issue"
                maxLength={200}
                required
                style={inputStyle}
              />
            </div>

            {/* Description */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: secondary, marginBottom: 6 }}>
                Description *
              </label>
              <textarea
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="Describe your issue in detail..."
                maxLength={2000}
                required
                rows={4}
                style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.6 }}
              />
            </div>

            {/* Priority + Attachment row */}
            <div style={{ display: 'flex', gap: 14, marginBottom: 14, flexWrap: 'wrap' }}>
              {/* Priority dropdown */}
              <div style={{ flex: '1 1 160px' }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: secondary, marginBottom: 6 }}>
                  Priority *
                </label>
                <div style={{ position: 'relative' }}>
                  <select
                    value={form.priority}
                    onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                    style={{
                      ...inputStyle, appearance: 'none', paddingRight: 32, cursor: 'pointer',
                      color: PRIORITY_META[form.priority]?.color || text,
                    }}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                  <ChevronDown size={14} color={muted} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                </div>
              </div>

              {/* Attachment */}
              <div style={{ flex: '2 1 200px' }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: secondary, marginBottom: 6 }}>
                  Attachment (optional)
                </label>
                <div
                  onClick={() => fileRef.current?.click()}
                  style={{
                    ...inputStyle, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                    color: file ? text : muted,
                  }}
                >
                  {file ? (
                    <>
                      {file.type.startsWith('image') ? <Image size={14} color="var(--tool-hex-4f8ff7)" /> : <FileVideo size={14} color="var(--tool-hex-a78bfa)" />}
                      <span style={{ fontSize: 13, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</span>
                      <button type="button" onClick={e => { e.stopPropagation(); setFile(null); fileRef.current.value = ''; }}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: muted, display: 'flex', padding: 0 }}>
                        <X size={13} />
                      </button>
                    </>
                  ) : (
                    <>
                      <Paperclip size={14} />
                      <span style={{ fontSize: 13 }}>mp4, png, jpg — max 20MB</span>
                    </>
                  )}
                </div>
                <input ref={fileRef} type="file" accept=".mp4,.png,.jpg,.jpeg" onChange={handleFileChange} style={{ display: 'none' }} />
                {fileError && <p style={{ fontSize: 11, color: 'var(--tool-hex-f87171)', margin: '4px 0 0' }}>{fileError}</p>}
              </div>
            </div>

            {formError && (
              <div style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: 8, padding: '8px 12px', marginBottom: 14 }}>
                <p style={{ fontSize: 12, color: 'var(--tool-hex-f87171)', margin: 0 }}>{formError}</p>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button type="button" onClick={() => { setShowForm(false); setFormError(''); setFile(null); }}
                style={{ padding: '9px 18px', borderRadius: 10, border: `1px solid ${border}`, background: 'transparent', color: secondary, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                Cancel
              </button>
              <button type="submit" disabled={submitting}
                style={{
                  padding: '9px 20px', borderRadius: 10, border: 'none', cursor: submitting ? 'not-allowed' : 'pointer',
                  background: isDark ? 'var(--tool-hex-f5f5f5)' : 'var(--tool-hex-171717)', color: isDark ? 'var(--tool-hex-171717)' : 'var(--tool-hex-fff)',
                  fontSize: 13, fontWeight: 600, opacity: submitting ? 0.7 : 1,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                {submitting && <Loader2 size={13} style={{ animation: 'spin 0.8s linear infinite' }} />}
                Submit Query
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {[
          { key: 'all', label: `All (${tickets.length})` },
          { key: 'open', label: `Open (${open})` },
          { key: 'resolved', label: `Resolved (${resolved})` },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            style={{
              padding: '6px 14px', borderRadius: 8, border: `1px solid ${filter === f.key ? (isDark ? 'var(--tool-hex-4f8ff7)' : 'var(--tool-hex-4f8ff7)') : border}`,
              background: filter === f.key ? (isDark ? 'rgba(79,143,247,0.15)' : 'rgba(79,143,247,0.08)') : 'transparent',
              color: filter === f.key ? 'var(--tool-hex-4f8ff7)' : secondary, fontSize: 12, fontWeight: 600, cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Ticket list */}
      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 48, gap: 10 }}>
          <Loader2 size={16} color={muted} style={{ animation: 'spin 0.8s linear infinite' }} />
          <span style={{ color: muted, fontSize: 13 }}>Loading tickets…</span>
        </div>
      ) : visibleTickets.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 20px' }}>
          <div style={{ width: 48, height: 48, borderRadius: 14, background: isDark ? 'var(--tool-hex-1e1e1e)' : 'var(--tool-hex-f5f5f5)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px' }}>
            <AlertCircle size={22} color={muted} />
          </div>
          <p style={{ fontSize: 14, fontWeight: 600, color: text, margin: '0 0 4px' }}>No tickets yet</p>
          <p style={{ fontSize: 13, color: muted, margin: 0 }}>
            {filter === 'all' ? 'Submit a query using the button above' : `No ${filter} tickets`}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {visibleTickets.map(ticket => (
            <TicketCard
              key={ticket.id}
              ticket={ticket}
              currentUser={currentUser}
              isDark={isDark}
              onResolve={handleResolve}
              onUnresolve={handleUnresolve}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </ToolPage>
  );
}
