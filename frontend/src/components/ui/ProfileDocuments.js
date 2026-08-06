/**
 * Identity documents on a profile (owner request 11, 2026-08-06).
 *
 * Aadhaar, birth certificate, transfer certificate, appointment letter, and whatever
 * else the school keeps a copy of. These ride on the same upload endpoint everything
 * else uses, with `entity_type=profile-document`, rather than growing a store of their
 * own: the upload route is already the single place that decides who may read a stored
 * file, and three doors are harder to keep honest than one.
 *
 * UNLIKE NOTES, THESE ARE NOT PRIVATE TO THE UPLOADER. A birth certificate is a school
 * record, not a personal remark, and the owner and principal both need to reach it.
 * That difference is deliberate; do not copy the notes rule onto this panel.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, Trash2, Upload } from 'lucide-react';
import { deleteEntityFile, listEntityFiles, uploadEntityFile } from '../../lib/api';
import { inputStyle } from './primitives';

export const ENTITY_TYPE = 'profile-document';

/** The papers a school actually files. Free text is allowed for anything else. */
export const DOCUMENT_KINDS = [
  'Aadhaar card',
  'Birth certificate',
  'Transfer certificate',
  'Previous marksheet',
  'Caste or category certificate',
  'Medical record',
  'Appointment letter',
  'Qualification certificate',
  'Other',
];

const isImage = (type) => String(type || '').startsWith('image/');

export default function ProfileDocuments({ subjectId, canManage = true }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [kind, setKind] = useState(DOCUMENT_KINDS[0]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    if (!subjectId) return;
    setLoading(true);
    setError('');
    const res = await listEntityFiles(ENTITY_TYPE, subjectId);
    if (res.success) setFiles(res.data || []);
    else setError(res.detail || 'Could not load the documents on this profile');
    setLoading(false);
  }, [subjectId]);

  useEffect(() => { load(); }, [load]);

  const pick = async (event) => {
    const chosen = Array.from(event.target.files || []);
    if (!chosen.length) return;
    setUploading(true);
    setError('');
    for (const file of chosen) {
      // Sequential: a phone on a school connection uploading several scans at once is
      // how the whole set fails together.
      const res = await uploadEntityFile(file, ENTITY_TYPE, subjectId);  // eslint-disable-line no-await-in-loop
      if (!res.success) setError(res.detail || `Could not upload ${file.name}`);
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = '';
    load();
  };

  const remove = async (file) => {
    if (!window.confirm(`Delete ${file.file_name}? This cannot be undone.`)) return;
    const res = await deleteEntityFile(file.id);
    if (res.success) load();
    else setError(res.detail || 'Could not delete that document');
  };

  return (
    <div data-testid="profile-documents" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {error && <div role="alert" style={{ color: 'var(--color-danger, #fb7185)', fontSize: 12 }}>{error}</div>}

      {canManage && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            aria-label="What kind of document is this"
            data-testid="profile-document-kind"
            style={{ ...inputStyle, width: 210 }}
          >
            {DOCUMENT_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input
            ref={fileRef}
            type="file"
            accept="image/*,application/pdf"
            multiple
            onChange={pick}
            data-testid="profile-document-files"
            aria-label="Choose documents to upload"
            style={{ display: 'none' }}
          />
          <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading} style={buttonStyle}>
            <Upload size={13} aria-hidden="true" />
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>Loading documents…</div>
      ) : files.length === 0 ? (
        <div style={{ color: 'var(--c-faint)', fontSize: 12 }}>No documents have been filed here yet.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {files.map((file) => (
            <div
              key={file.id}
              data-testid={`profile-document-${file.id}`}
              style={{ display: 'flex', gap: 10, alignItems: 'center', border: '1px solid var(--c-border)', borderRadius: 8, padding: '8px 10px' }}
            >
              {isImage(file.file_type) ? (
                <img
                  src={file.file_url}
                  alt={file.file_name}
                  style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 5, flexShrink: 0 }}
                />
              ) : (
                <FileText size={20} aria-hidden="true" style={{ color: 'var(--c-faint)', flexShrink: 0 }} />
              )}
              <a
                href={file.file_url}
                target="_blank"
                rel="noreferrer"
                style={{ color: 'var(--c-text)', fontSize: 12, flex: 1, wordBreak: 'break-word' }}
              >
                {file.file_name}
              </a>
              <span style={{ color: 'var(--c-faint)', fontSize: 11, whiteSpace: 'nowrap' }}>
                {file.file_size_kb ? `${file.file_size_kb} KB` : ''}
              </span>
              {canManage && (
                <button
                  type="button"
                  onClick={() => remove(file)}
                  aria-label={`Delete ${file.file_name}`}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--c-faint)', padding: 2 }}
                >
                  <Trash2 size={13} aria-hidden="true" />
                </button>
              )}
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
  padding: '8px 12px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
};
