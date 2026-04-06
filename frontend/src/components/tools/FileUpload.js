/**
 * Reusable FileUpload component with drag-drop, preview, and delete
 */
import React, { useState, useRef } from 'react';
import { Upload, X, FileText, Image, Download } from 'lucide-react';
import { useUser } from '../../contexts/UserContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ALLOWED_BY_ROLE = {
  owner: ['pdf', 'docx', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'heic', 'mp4'],
  admin: ['pdf', 'docx', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'heic'],
  teacher: ['pdf', 'docx', 'xlsx', 'png', 'jpg', 'jpeg'],
  student: ['pdf', 'png', 'jpg', 'jpeg', 'heic'],
};

function getFileIcon(name) {
  const ext = name?.split('.').pop()?.toLowerCase();
  if (['png', 'jpg', 'jpeg', 'heic'].includes(ext)) return <Image size={14} color="#10B981" />;
  return <FileText size={14} color="#3B82F6" />;
}

export default function FileUpload({ entityType = 'general', entityId = '', onUploaded, isDark = true, compact = false }) {
  const { currentUser } = useUser();
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const allowed = ALLOWED_BY_ROLE[currentUser.role] || [];
  const bg = isDark ? '#161622' : '#F8F9FC';
  const border = isDark ? '#222230' : '#E2E8F0';
  const text = isDark ? '#94A3B8' : '#64748B';

  const uploadFile = async (file) => {
    setError('');
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!allowed.includes(ext)) {
      setError(`File type .${ext} not allowed. Allowed: ${allowed.join(', ')}`);
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('File too large (max 50MB)');
      return;
    }
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('entity_type', entityType);
    formData.append('entity_id', entityId);
    try {
      const res = await fetch(`${API}/uploads`, {
        method: 'POST',
        headers: { 'X-User-Role': currentUser.role, 'X-User-Id': currentUser.id, 'X-User-Name': currentUser.name },
        body: formData,
      }).then(r => r.json());
      if (res.success) {
        setFiles(prev => [...prev, res.data]);
        if (onUploaded) onUploaded(res.data);
      } else {
        setError(res.detail || 'Upload failed');
      }
    } catch { setError('Network error'); }
    setUploading(false);
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    dropped.forEach(uploadFile);
  };

  const handleDelete = async (fileId) => {
    await fetch(`${API}/uploads/${fileId}`, { method: 'DELETE', headers: { 'X-User-Role': currentUser.role, 'X-User-Id': currentUser.id } });
    setFiles(prev => prev.filter(f => f.id !== fileId));
  };

  if (compact) {
    return (
      <div>
        <button onClick={() => inputRef.current?.click()} disabled={uploading}
          style={{ display: 'flex', alignItems: 'center', gap: 6, background: isDark ? '#161622' : '#F1F5F9', border: `1px solid ${border}`, borderRadius: 7, padding: '6px 12px', color: text, fontSize: 12, cursor: 'pointer' }}>
          <Upload size={12} />
          {uploading ? 'Uploading...' : 'Attach File'}
        </button>
        <input ref={inputRef} type="file" style={{ display: 'none' }} accept={allowed.map(e => `.${e}`).join(',')} onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0])} />
        {error && <p style={{ fontSize: 11, color: '#EF4444', marginTop: 4 }}>{error}</p>}
        {files.map(f => (
          <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
            {getFileIcon(f.file_name)}
            <a href={`${process.env.REACT_APP_BACKEND_URL}${f.file_url}`} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#60A5FA', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.file_name}</a>
            <span style={{ fontSize: 10, color: text }}>{f.file_size_kb}KB</span>
            <button onClick={() => handleDelete(f.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444' }}><X size={10} /></button>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{ border: `2px dashed ${dragging ? '#3B82F6' : border}`, borderRadius: 10, padding: '24px 20px', textAlign: 'center', cursor: 'pointer', background: dragging ? 'rgba(59,130,246,0.05)' : bg, transition: 'all 0.15s' }}>
        <Upload size={24} color={dragging ? '#3B82F6' : text} style={{ margin: '0 auto 8px' }} />
        <p style={{ fontSize: 13, color: text, marginBottom: 4 }}>{uploading ? 'Uploading...' : 'Drop files here or click to upload'}</p>
        <p style={{ fontSize: 11, color: isDark ? '#475569' : '#94A3B8' }}>Allowed: {allowed.join(', ')} · Max 50MB</p>
      </div>
      <input ref={inputRef} type="file" style={{ display: 'none' }} multiple accept={allowed.map(e => `.${e}`).join(',')}
        onChange={e => Array.from(e.target.files || []).forEach(uploadFile)} />
      {error && <p style={{ fontSize: 11, color: '#EF4444', marginTop: 8 }}>{error}</p>}
      {files.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {files.map(f => (
            <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: bg, border: `1px solid ${border}`, borderRadius: 8 }}>
              {getFileIcon(f.file_name)}
              <span style={{ flex: 1, fontSize: 12, color: isDark ? '#E2E8F0' : '#0F172A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.file_name}</span>
              <span style={{ fontSize: 10, color: text }}>{f.file_size_kb}KB</span>
              <a href={`${process.env.REACT_APP_BACKEND_URL}${f.file_url}`} target="_blank" rel="noreferrer" style={{ color: '#3B82F6' }}><Download size={12} /></a>
              <button onClick={() => handleDelete(f.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444' }}><X size={12} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
