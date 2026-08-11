/**
 * Notes and remarks on one person's profile (owner request 4, 2026-08-06).
 *
 * PRIVATE TO EACH AUTHOR. The owner and the principal may both keep notes about the
 * same child and neither can read the other's. That is decision 3 of that night and
 * it is deliberate: Abhimanyu was told in plain words that the two of them cannot use
 * this to talk to each other, and chose it anyway.
 *
 * The panel says so on the screen, every time. A private box that does not look
 * private is how somebody writes something for a colleague to read, and nobody ever
 * reads it.
 *
 * Used on the student profile and the staff profile - the same component, because
 * the rule and the wording have to be the same in both places.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Image as ImageIcon, Lock, Trash2 } from 'lucide-react';
import {
  addProfileNote,
  deleteProfileNote,
  getProfileNotes,
  uploadEntityFile,
} from '../../lib/api';
import { inputStyle } from './primitives';

const MAX_ATTACHMENTS = 10;

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function ProfileNotes({ subjectType, subjectId, subjectName, canWrite = true }) {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    if (!subjectId) return;
    setLoading(true);
    setError('');
    const res = await getProfileNotes(subjectType, subjectId);
    if (res.success) setNotes(res.data || []);
    else setError(res.detail || 'Could not load your notes');
    setLoading(false);
  }, [subjectType, subjectId]);

  useEffect(() => { load(); }, [load]);

  const pickFiles = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    if (attachments.length + files.length > MAX_ATTACHMENTS) {
      setError(`A note can carry up to ${MAX_ATTACHMENTS} pictures.`);
      return;
    }
    setUploading(true);
    setError('');
    const added = [];
    for (const file of files) {
      // Sequential on purpose: a phone on a school connection uploading eight photos
      // at once is how the whole set fails together.
      const res = await uploadEntityFile(file, 'profile-note', subjectId);   // eslint-disable-line no-await-in-loop
      if (res.success) {
        added.push({
          file_id: res.data.id,
          file_url: res.data.file_url,
          file_name: res.data.file_name,
          file_type: res.data.file_type,
        });
      } else {
        setError(res.detail || `Could not attach ${file.name}`);
      }
    }
    setAttachments((prev) => [...prev, ...added]);
    setUploading(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const save = async () => {
    if (!draft.trim()) return;
    setSaving(true);
    const res = await addProfileNote(subjectType, subjectId, draft.trim(), attachments);
    setSaving(false);
    if (res.success) {
      setDraft('');
      setAttachments([]);
      load();
    } else {
      setError(res.detail || 'Could not save that note');
    }
  };

  const remove = async (note) => {
    if (!window.confirm('Delete this note? It cannot be brought back.')) return;
    const res = await deleteProfileNote(note.id);
    if (res.success) load();
    else setError(res.detail || 'Could not delete that note');
  };

  return (
    <div data-testid="profile-notes" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: 'var(--c-faint)', fontSize: 11 }}>
        <Lock size={12} aria-hidden="true" />
        <span>
          Only you can see these notes. Nobody else at the school can read them, not
          even the {subjectType === 'staff' ? 'owner or the principal' : 'other head of school'}.
        </span>
      </div>

      {error && (
        <div role="alert" style={{ color: 'var(--color-danger, #fb7185)', fontSize: 12 }}>{error}</div>
      )}

      {canWrite && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          <label htmlFor="profile-note-draft" style={{ color: 'var(--c-muted)', fontSize: 12 }}>
            Add a note{subjectName ? ` about ${subjectName}` : ''}
          </label>
          <textarea
            id="profile-note-draft"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            data-testid="profile-note-draft"
            placeholder="What happened, what was agreed, what to watch for…"
            style={{ ...inputStyle, width: '100%', resize: 'vertical' }}
          />

          {attachments.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {attachments.map((a) => (
                <span key={a.file_id} style={{ fontSize: 11, color: 'var(--c-faint)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '3px 8px' }}>
                  {a.file_name}
                </span>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              onChange={pickFiles}
              data-testid="profile-note-files"
              aria-label="Attach pictures to this note"
              style={{ display: 'none' }}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              style={buttonStyle}
            >
              <ImageIcon size={13} aria-hidden="true" />
              {uploading ? 'Attaching…' : 'Attach a picture'}
            </button>
            <button
              type="button"
              onClick={save}
              disabled={!draft.trim() || saving || uploading}
              data-testid="profile-note-save"
              style={{ ...buttonStyle, opacity: !draft.trim() || saving || uploading ? 0.5 : 1 }}
            >
              {saving ? 'Saving…' : 'Save note'}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>Loading your notes…</div>
      ) : notes.length === 0 ? (
        <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>You have not written any notes here yet.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {notes.map((note) => (
            <div key={note.id} data-testid={`profile-note-${note.id}`} style={{ border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                <div style={{ color: 'var(--c-text)', fontSize: 13, whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>
                  {note.body}
                </div>
                {canWrite && (
                  <button
                    type="button"
                    onClick={() => remove(note)}
                    aria-label="Delete this note"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--c-faint)', padding: 2 }}
                  >
                    <Trash2 size={13} aria-hidden="true" />
                  </button>
                )}
              </div>
              {(note.attachments || []).length > 0 && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                  {note.attachments.map((a) => (
                    <a key={a.file_id} href={a.file_url || '#'} target="_blank" rel="noreferrer">
                      <img
                        src={a.file_url}
                        alt={a.file_name || 'Attached picture'}
                        style={{ width: 76, height: 76, objectFit: 'cover', borderRadius: 6, border: '1px solid var(--c-border)' }}
                      />
                    </a>
                  ))}
                </div>
              )}
              <div style={{ color: 'var(--c-faint)', fontSize: 11, marginTop: 7 }}>
                {formatDate(note.created_at)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const buttonStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: 'transparent', color: 'var(--c-text)',
  border: '1px solid var(--c-border)', borderRadius: 8,
  padding: '7px 12px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
};
