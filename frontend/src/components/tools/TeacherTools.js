/**
 * All 12 Teacher Tools
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useUser } from '../../contexts/UserContext';
import { getAllClasses, getStudents, getTodayAttendance, bulkMarkAttendance } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, StatCard, DataTable, Badge, ComingSoon, FormField, ActionBtn } from './ToolPage';
import { Plus, CheckCircle, Save, Bold, Underline, List } from 'lucide-react';
import html2pdf from 'html2pdf.js';
export { FormSubmissions } from './StudentTools';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }
const tint = (color, amount) => `color-mix(in srgb, ${color} ${amount}%, transparent)`;
const btnStyle = (color) => ({ background: tint(color, 13), border: `1px solid ${tint(color, 31)}`, borderRadius: 5, padding: '3px 8px', color, fontSize: 11, cursor: 'pointer', fontWeight: 600 });

function markdownToHtml(text) {
  let html = (text == null ? '' : String(text));
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  html = html.replace(/^### (.*?)$/gm, '<h3 style="margin-top:16px;margin-bottom:8px;font-size:16px;font-weight:bold;">$1</h3>');
  html = html.replace(/^## (.*?)$/gm, '<h2 style="margin-top:20px;margin-bottom:12px;font-size:18px;font-weight:bold;">$1</h2>');
  html = html.replace(/^# (.*?)$/gm, '<h1 style="margin-top:24px;margin-bottom:16px;font-size:24px;font-weight:bold;">$1</h1>');
  html = html.replace(/\n/g, '<br/>');
  return html;
}

// 1. Class Attendance Marker
export function ClassAttendanceMarker() {
  const { currentUser } = useUser();
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => { getAllClasses(currentUser).then(r => { if (r.success && r.data.length > 0) { setClasses(r.data); setSelectedClass(r.data[0].id); } }); }, []);
  useEffect(() => { if (selectedClass) { setLoading(true); 
    fetch(`${API}/attendance/student/today/${selectedClass}?date=${date}`, { headers: h(currentUser) })
      .then(r => r.json()).then(r => { if (r.success) setRecords(r.data || []); }).finally(() => setLoading(false)); 
  } }, [selectedClass, date]);

  const handleSave = async () => {
    setSaving(true);
    await bulkMarkAttendance({ class_id: selectedClass, date, records: records.map(s => ({ student_id: s.student_id, status: s.status })) }, currentUser);
    setSaved(true); setSaving(false); setTimeout(() => setSaved(false), 3000);
  };

  const markAll = status => setRecords(prev => prev.map(s => ({ ...s, status })));

  return (
    <ToolPage title="Class Attendance" subtitle="Mark attendance for your class">
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={selectedClass} onChange={e => setSelectedClass(e.target.value)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }}>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}-{c.section}</option>)}
        </select>
        <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none' }} />
        <ActionBtn label="All Present" variant="success" onClick={() => markAll('present')} />
        <ActionBtn label="All Absent" variant="danger" onClick={() => markAll('absent')} />
      </div>
      {records.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {[['Present', records.filter(r => r.status === 'present').length, 'var(--tool-hex-34d399)'], ['Absent', records.filter(r => r.status === 'absent').length, 'var(--tool-hex-f87171)'], ['Total', records.length, 'var(--c-text)']].map(([l, v, c]) => (
            <StatCard key={l} value={v} label={l} color={c} small />
          ))}
        </div>
      )}
      <DataTable headers={['Roll', 'Student Name', 'Status', 'Quick Mark']}
        rows={records.map((s, i) => [
          s.roll_number || '-',
          s.name,
          <Badge text={s.status} color={{ present: 'green', absent: 'red', late: 'yellow', holiday: 'gray', not_marked: 'gray' }[s.status] || 'gray'} />,
          <div style={{ display: 'flex', gap: 3 }}>
            {[['P', 'present', 'var(--tool-hex-34d399)'], ['A', 'absent', 'var(--tool-hex-f87171)'], ['L', 'late', 'var(--tool-hex-fbbf24)']].map(([lbl, val, col]) => (
              <button key={lbl} onClick={() => setRecords(prev => prev.map(st => st.student_id === s.student_id ? { ...st, status: val } : st))}
                style={{ background: s.status === val ? tint(col, 13) : 'transparent', border: `1px solid ${s.status === val ? tint(col, 31) : 'var(--c-border)'}`, borderRadius: 4, padding: '3px 7px', color: s.status === val ? col : 'var(--c-faint)', fontSize: 10, cursor: 'pointer', fontWeight: 700 }}>{lbl}</button>
            ))}
          </div>
        ])}
        emptyMsg={loading ? 'Loading...' : 'No students found'}
      />
      {records.length > 0 && <button onClick={handleSave} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: 7, background: saved ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-4f8ff7)', border: 'none', borderRadius: 8, padding: '10px 20px', color: 'var(--tool-hex-fff)', fontSize: 13, fontWeight: 700, cursor: 'pointer', marginTop: 12 }}>
        {saved ? <CheckCircle size={14} /> : <Save size={14} />}{saved ? 'Saved!' : saving ? 'Saving...' : 'Save Attendance'}
      </button>}
    </ToolPage>
  );
}

// 2. Assignment Generator
export function AssignmentGenerator() {
  const { currentUser } = useUser();
  const [assignments, setAssignments] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ class_id: '', subject_id: '', title: '', description: '', due_date: '' });
  const f = k => v => setForm(p => ({ ...p, [k]: v }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    const r = await fetch(`${API}/academics/assignments`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setAssignments(r.data || []);
  };

  useEffect(() => {
    Promise.all([
      getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }),
      load(),
    ]).finally(() => setLoading(false));
  }, []);

  const loadSubjects = async (classId) => {
    const r = await fetch(`${API}/academics/subjects?class_id=${classId}`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setSubjects(r.data || []);
  };

  const openCreate = () => { setEditingId(null); setForm({ class_id: '', subject_id: '', title: '', description: '', due_date: '' }); setShowForm(true); setError(''); };
  const openEdit = (a) => { setEditingId(a.id); setForm({ class_id: a.class_id || '', subject_id: a.subject_id || '', title: a.title || '', description: a.description || '', due_date: a.due_date || '' }); if (a.class_id) loadSubjects(a.class_id); setShowForm(true); setError(''); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title || !form.class_id) { setError('Title and Class are required'); return; }
    setSaving(true); setError('');
    try {
      const url = editingId ? `${API}/academics/assignments/${editingId}` : `${API}/academics/assignments`;
      const method = editingId ? 'PATCH' : 'POST';
      const res = await fetch(url, { method, headers: h(currentUser), body: JSON.stringify(form) }).then(r => r.json());
      if (res.success) { setShowForm(false); setEditingId(null); await load(); }
      else setError(res.message || 'Failed');
    } catch (err) { setError(err.message); }
    setSaving(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this assignment?')) return;
    await fetch(`${API}/academics/assignments/${id}`, { method: 'DELETE', headers: h(currentUser) });
    await load();
  };

  return (
    <ToolPage title="Assignments" subtitle="Create & manage assignments" loading={loading}
      actions={<ActionBtn label="New Assignment" onClick={openCreate} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{editingId ? 'Edit Assignment' : 'New Assignment'}</h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Class" type="select" value={form.class_id} onChange={v => { f('class_id')(v); loadSubjects(v); }} options={classes.map(c => ({ value: c.id, label: `${c.name}-${c.section}` }))} required />
              <FormField label="Subject" type="select" value={form.subject_id} onChange={f('subject_id')} options={subjects.map(s => ({ value: s.id, label: s.name }))} />
              <FormField label="Title" value={form.title} onChange={f('title')} placeholder="Assignment title" required />
              <FormField label="Due Date" type="date" value={form.due_date} onChange={f('due_date')} />
            </div>
            <FormField label="Description / Instructions" type="textarea" value={form.description} onChange={f('description')} placeholder="Assignment instructions..." />
            {error && <p style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 12 }}>{error}</p>}
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : editingId ? 'Update' : 'Create'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ borderBottom: '1px solid var(--c-border)' }}>
            {['Title', 'Class', 'Subject', 'Due Date', 'Actions'].map(h2 => <th key={h2} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>{h2}</th>)}
          </tr></thead>
          <tbody>
            {assignments.length === 0 ? <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No assignments yet</td></tr>
              : assignments.map((a, i) => (
                <tr key={a.id} style={{ borderBottom: i < assignments.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)' }}>{a.title}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{a.class_name || 'N/A'}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{a.subject_name || 'N/A'}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{a.due_date || 'N/A'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => openEdit(a)} style={btnStyle('var(--tool-hex-4f8ff7)')}>Edit</button>
                      <button onClick={() => handleDelete(a.id)} style={btnStyle('var(--tool-hex-f87171)')}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </ToolPage>
  );
}

// 3. Question Paper Creator
export function QuestionPaperCreator() {
  const { currentUser } = useUser();
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [subjects, setSubjects] = useState([]);
  const [form, setForm] = useState({ subject_id: '', title: '', chapters: '', easy: 30, medium: 50, hard: 20, total_marks: 100 });
  const [showForm, setShowForm] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [generatedPaper, setGeneratedPaper] = useState(null);
  const [editedContent, setEditedContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [saveFeedback, setSaveFeedback] = useState('');
  const editorRef = useRef(null);
  const pendingContentRef = useRef('');
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  // When editor becomes visible, populate contenteditable with current content
  useEffect(() => {
    if (isEditing && editorRef.current) {
      editorRef.current.innerHTML = pendingContentRef.current;
      // Move cursor to end
      const range = document.createRange();
      range.selectNodeContents(editorRef.current);
      range.collapse(false);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
    }
  }, [isEditing, generatedPaper]);

  const execFormat = useCallback((cmd, value = null) => {
    editorRef.current?.focus();
    document.execCommand(cmd, false, value);
    setEditedContent(editorRef.current?.innerHTML || '');
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const [subj, pap] = await Promise.all([
          fetch(`${API}/academics/subjects`, { headers: h(currentUser) }).then(r => r.json()),
          fetch(`${API}/academics/question-papers`, { headers: h(currentUser) }).then(r => r.json())
        ]);
        if (subj.success) setSubjects(subj.data || []);
        if (pap.success) setPapers(pap.data || []);
      } catch (e) {
        console.error('Error loading data:', e);
      }
      setLoading(false);
    };
    load();
  }, []);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!form.chapters) {
      setError('Please fill in chapters');
      return;
    }
    setGenerating(true);
    setError('');
    try {
      const subj = subjects.find(s => s.id === form.subject_id);
      const res = await fetch(`${API}/academics/question-papers/generate`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({
          subject: subj?.name || form.title,
          chapters: form.chapters,
          total_marks: form.total_marks,
          easy: form.easy,
          medium: form.medium,
          hard: form.hard,
          exam_type: form.title || 'Exam'
        })
      }).then(r => r.json());
      if (res.success) {
        const htmlContent = markdownToHtml(res.data?.content || res.data?.generated_content || '');
        pendingContentRef.current = htmlContent;
        setGeneratedPaper(res.data);
        setEditedContent(htmlContent);
        setIsEditing(true);
        setShowForm(false);
        setPapers(prev => [res.data, ...prev]);
      } else {
        setError(res.message || 'Failed to generate paper');
      }
    } catch (err) {
      setError('Error: ' + (err.message || 'Unknown error'));
    }
    setGenerating(false);
  };


  const downloadPdf = () => {
    const liveContent = editorRef.current?.innerHTML || editedContent;
    // Create a visible overlay — html2canvas cannot capture off-screen/fixed elements
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:var(--tool-hex-ffffff);overflow:auto;display:flex;justify-content:center;';
    const inner = document.createElement('div');
    inner.style.cssText = 'width:794px;padding:40px 48px;font-family:Arial,sans-serif;font-size:13px;line-height:1.7;color:var(--tool-hex-111111);background:var(--tool-hex-ffffff);';
    inner.innerHTML = liveContent;
    overlay.appendChild(inner);
    document.body.appendChild(overlay);
    const opt = {
      margin: [12, 12, 12, 12],
      filename: `${(generatedPaper?.title || 'question-paper').replace(/\s+/g, '-')}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, logging: false, backgroundColor: 'white' },
      jsPDF: { orientation: 'portrait', unit: 'mm', format: 'a4' },
    };
    html2pdf().set(opt).from(inner).save().finally(() => document.body.removeChild(overlay));
  };

  const downloadWord = () => {
    const liveContent = editorRef.current?.innerHTML || editedContent;
    const wordHtml = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="UTF-8"><title>${generatedPaper?.title || 'Question Paper'}</title>
<style>body{font-family:Arial,sans-serif;font-size:12pt;line-height:1.6;margin:2cm;}h1{font-size:18pt;}h2{font-size:15pt;}h3{font-size:13pt;}p{margin:6pt 0;}strong{font-weight:bold;}</style></head>
<body>${liveContent}</body></html>`;
    const blob = new Blob(['\ufeff', wordHtml], { type: 'application/msword' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(generatedPaper?.title || 'question-paper').replace(/\s+/g, '-')}.doc`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadHtml = () => {
    const liveContent = editorRef.current?.innerHTML || editedContent;
    const htmlContent = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${generatedPaper?.title || 'Question Paper'}</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 900px; margin: 20px auto; line-height: 1.6; }
    h1, h2, h3 { color: var(--tool-hex-1a1a1a); margin-top: 20px; }
    p { margin: 8px 0; }
    strong { font-weight: bold; }
    u { text-decoration: underline; }
    ul { margin: 8px 0; padding-left: 24px; }
  </style>
</head>
<body>
  ${liveContent}
</body>
</html>`;
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(generatedPaper?.title || 'question-paper').replace(/\s+/g, '-')}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const saveEditedPaper = async () => {
    if (!generatedPaper?.id) return;
    const content = editorRef.current?.innerHTML || editedContent;
    setEditedContent(content);
    setSaveFeedback('saving');
    try {
      await fetch(`${API}/academics/question-papers/${generatedPaper.id}`, { method: 'PATCH', headers: h(currentUser), body: JSON.stringify({ title: generatedPaper.title, generated_content: content }) });
      const r = await fetch(`${API}/academics/question-papers`, { headers: h(currentUser) }).then(r => r.json());
      if (r.success) setPapers(r.data || []);
      setSaveFeedback('saved');
      setTimeout(() => setSaveFeedback(''), 2000);
    } catch {
      setSaveFeedback('error');
      setTimeout(() => setSaveFeedback(''), 2000);
    }
  };

  const toolbarBtn = (onClick, icon, title) => (
    <button title={title} onMouseDown={e => { e.preventDefault(); onClick(); }}
      style={{ background: 'none', border: '1px solid var(--c-border)', borderRadius: 5, padding: '3px 7px', color: 'var(--c-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
      {icon}
    </button>
  );

  if (generatedPaper && isEditing) {
    return (
      <ToolPage title={generatedPaper.title} subtitle="Edit and export your question paper">
        <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <ActionBtn label="← Back to List" onClick={() => { setGeneratedPaper(null); setIsEditing(false); setSaveFeedback(''); }} />
          <ActionBtn label={saveFeedback === 'saving' ? 'Saving...' : 'Save Changes'} onClick={saveEditedPaper} variant="success" disabled={saveFeedback === 'saving'} />
          {saveFeedback === 'saved' && <span style={{ fontSize: 11, color: 'var(--tool-hex-34d399)', fontWeight: 600 }}>Saved!</span>}
          {saveFeedback === 'error' && <span style={{ fontSize: 11, color: 'var(--tool-hex-f87171)', fontWeight: 600 }}>Save failed</span>}
          <ActionBtn label="Download PDF" onClick={downloadPdf} />
          <ActionBtn label="Download Word" onClick={downloadWord} />
          <ActionBtn label="Download HTML" onClick={downloadHtml} />
        </div>

        {/* Toolbar */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 8, padding: '6px 10px', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, marginRight: 6 }}>FORMAT</span>
          {toolbarBtn(() => execFormat('bold'), <Bold size={12} />, 'Bold')}
          {toolbarBtn(() => execFormat('underline'), <Underline size={12} />, 'Underline')}
          {toolbarBtn(() => execFormat('insertUnorderedList'), <List size={12} />, 'Bullet List')}
          <div style={{ width: 1, height: 18, background: 'var(--c-border)', margin: '0 4px' }} />
          {toolbarBtn(() => execFormat('formatBlock', 'h2'), <span style={{ fontSize: 11, fontWeight: 700 }}>H2</span>, 'Heading 2')}
          {toolbarBtn(() => execFormat('formatBlock', 'h3'), <span style={{ fontSize: 11, fontWeight: 700 }}>H3</span>, 'Heading 3')}
          {toolbarBtn(() => execFormat('formatBlock', 'p'), <span style={{ fontSize: 11 }}>P</span>, 'Paragraph')}
          <div style={{ width: 1, height: 18, background: 'var(--c-border)', margin: '0 4px' }} />
          {toolbarBtn(() => execFormat('undo'), <span style={{ fontSize: 11 }}>↩</span>, 'Undo')}
          {toolbarBtn(() => execFormat('redo'), <span style={{ fontSize: 11 }}>↪</span>, 'Redo')}
        </div>

        {/* Editor */}
        <div style={{ border: '1px solid var(--c-border)', borderRadius: 8, overflow: 'hidden', marginBottom: 16 }}>
          <div
            ref={editorRef}
            contentEditable
            suppressContentEditableWarning
            onInput={() => setEditedContent(editorRef.current?.innerHTML || '')}
            style={{ minHeight: 480, padding: 20, background: 'var(--tool-hex-fff)', color: 'var(--tool-hex-1a1a1a)', fontSize: 13, lineHeight: 1.7, outline: 'none', overflowY: 'auto' }}
          />
        </div>
      </ToolPage>
    );
  }

  return (
    <ToolPage title="Question Paper Creator" subtitle="Create question papers with AI assistance" loading={loading}
      actions={<ActionBtn label="Create Paper" onClick={() => setShowForm(true)} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <form onSubmit={handleGenerate}>
            <FormField label="Subject" type="select" value={form.subject_id} onChange={f('subject_id')} options={subjects.map(s => ({ value: s.id, label: s.name }))} required />
            <FormField label="Paper Title" value={form.title} onChange={f('title')} placeholder="e.g. Mid-Term Science Paper" required />
            <FormField label="Chapters (comma-separated)" value={form.chapters} onChange={f('chapters')} placeholder="e.g. Chapter 1, Chapter 2, Chapter 3" required />
            <FormField label="Total Marks" type="number" value={form.total_marks} onChange={v => f('total_marks')(+v)} />
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>DIFFICULTY MIX</label>
              <div style={{ display: 'flex', gap: 10 }}>
                {[['Easy', 'easy', 'var(--tool-hex-34d399)'], ['Medium', 'medium', 'var(--tool-hex-fbbf24)'], ['Hard', 'hard', 'var(--tool-hex-f87171)']].map(([l, k, c]) => (
                  <div key={k} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 11, color: c, fontWeight: 700, marginBottom: 4 }}>{form[k]}%</div>
                    <input type="range" min={0} max={100} value={form[k]} onChange={e => f(k)(+e.target.value)} style={{ width: 80, accentColor: c }} />
                    <div style={{ fontSize: 9, color: 'var(--c-faint)' }}>{l}</div>
                  </div>
                ))}
              </div>
            </div>
            {error && <p style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 12 }}>{error}</p>}
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={generating ? 'Generating...' : 'Generate with AI'} type="submit" disabled={generating} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} disabled={generating} />
            </div>
          </form>
        </div>
      )}
      {papers.length > 0 ? (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--c-border)' }}>
                {['Title', 'Subject', 'Created', 'Actions'].map(c => <th key={c} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {papers.map((p, i) => (
                <tr key={p.id || i} style={{ borderBottom: i < papers.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)' }}>{p.title}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{p.subject_id || 'N/A'}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{new Date(p.created_at).toLocaleDateString()}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={async () => {
                        const res = await fetch(`${API}/academics/question-papers/${p.id}`, { headers: h(currentUser) }).then(r => r.json());
                        const full = res.success ? res.data : p;
                        const rawContent = full.generated_content || '';
                        // Content may already be HTML (saved after editing) or markdown (fresh from AI)
                        const html = rawContent.trim().startsWith('<') ? rawContent : markdownToHtml(rawContent);
                        pendingContentRef.current = html;
                        setGeneratedPaper(full);
                        setEditedContent(html);
                        setIsEditing(true);
                      }} style={btnStyle('var(--tool-hex-4f8ff7)')}>Edit</button>
                      <button onClick={async () => { if (!window.confirm('Delete this question paper?')) return; await fetch(`${API}/academics/question-papers/${p.id}`, { method: 'DELETE', headers: h(currentUser) }); const r = await fetch(`${API}/academics/question-papers`, { headers: h(currentUser) }).then(r => r.json()); if (r.success) setPapers(r.data || []); }} style={btnStyle('var(--tool-hex-f87171)')}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, fontSize: 12 }}>
          No question papers yet. Create one to get started.
        </div>
      )}
    </ToolPage>
  );
}

// 4. Leave Application
export function LeaveApplication() {
  const { currentUser } = useUser();
  const [myLeaves, setMyLeaves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ leave_type: 'casual', start_date: '', end_date: '', reason: '' });
  const f = k => v => setForm(p => ({ ...p, [k]: v }));
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      // Use my-leaves endpoint instead of pending (which requires owner/admin)
      const r = await fetch(`${API}/staff/leaves/my`, { headers: h(currentUser) }).then(r => r.json());
      if (r.success) setMyLeaves(r.data || []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleApply = async (e) => {
    e.preventDefault();
    if (!form.start_date || !form.end_date || !form.reason) {
      setError('Please fill in all required fields');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const r = await fetch(`${API}/ops/leaves`, { method: 'POST', headers: h(currentUser), body: JSON.stringify(form) }).then(r => r.json());
      if (r.success) {
        setSubmitted(true);
        setForm({ leave_type: 'casual', start_date: '', end_date: '', reason: '' });
        setTimeout(() => setSubmitted(false), 3000);
        load();
      } else {
        setError(r.message || 'Failed to submit leave application');
      }
    } catch (err) {
      setError('Error submitting application: ' + (err.message || 'Unknown error'));
    }
    setSubmitting(false);
  };

  const statusColors = { pending: 'yellow', approved: 'green', rejected: 'red', cancelled: 'gray' };

  return (
    <ToolPage title="Leave Application" subtitle="Apply for leave & view history" loading={loading}>
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16, maxWidth: 520 }}>
        <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Apply for Leave</h3>
        <form onSubmit={handleApply}>
          <FormField label="Leave Type" type="select" value={form.leave_type} onChange={f('leave_type')}
            options={['casual', 'medical', 'earned', 'maternity', 'paternity', 'unpaid'].map(v => ({ value: v, label: v.charAt(0).toUpperCase() + v.slice(1) }))} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <FormField label="Start Date" type="date" value={form.start_date} onChange={f('start_date')} required />
            <FormField label="End Date" type="date" value={form.end_date} onChange={f('end_date')} required />
          </div>
          <FormField label="Reason" type="textarea" value={form.reason} onChange={f('reason')} placeholder="Reason for leave..." required />
          <ActionBtn label={submitted ? 'Submitted!' : submitting ? 'Submitting...' : 'Submit Application'} disabled={submitting} type="submit" />
          {submitted && <p style={{ color: 'var(--tool-hex-34d399)', fontSize: 12, marginTop: 8 }}>Leave application submitted successfully!</p>}
          {error && <p style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginTop: 8 }}>{error}</p>}
        </form>
      </div>
      <DataTable title="My Leave History" headers={['Type', 'Start Date', 'End Date', 'Status', 'Reason']}
        rows={myLeaves.map(l => [
          l.leave_type ? (l.leave_type.charAt(0).toUpperCase() + l.leave_type.slice(1)) : 'N/A',
          l.start_date || 'N/A',
          l.end_date || 'N/A',
          <Badge text={l.status || 'N/A'} color={statusColors[l.status] || 'gray'} />,
          l.reason ? l.reason.slice(0, 30) + (l.reason.length > 30 ? '...' : '') : 'N/A'
        ])}
        emptyMsg="No leave requests submitted yet"
      />
    </ToolPage>
  );
}

// 7. Lesson Plan Generator
export function LessonPlanGenerator() {
  const { currentUser } = useUser();
  const [subjects, setSubjects] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ class_id: '', subject_id: '', chapter: '', content: '' });
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [classes, setClasses] = useState([]);
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const load = async () => {
    const r = await fetch(`${API}/academics/lesson-plans`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setPlans(r.data || []);
  };

  useEffect(() => {
    Promise.all([
      getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }),
      fetch(`${API}/academics/subjects`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setSubjects(r.data || []); }),
      load(),
    ]).finally(() => setLoading(false));
  }, []);

  const openCreate = () => { setEditingId(null); setForm({ class_id: '', subject_id: '', chapter: '', content: '' }); setShowForm(true); };
  const openEdit = (p) => { setEditingId(p.id); setForm({ class_id: p.class_id || '', subject_id: p.subject_id || '', chapter: p.chapter || '', content: typeof p.content === 'object' ? (p.content.description || '') : (p.content || '') }); setShowForm(true); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.chapter) return;
    setSaving(true);
    try {
      const body = { ...form, content: { description: form.content, topics: [], objectives: [] } };
      const url = editingId ? `${API}/academics/lesson-plans/${editingId}` : `${API}/academics/lesson-plans`;
      const method = editingId ? 'PATCH' : 'POST';
      const r = await fetch(url, { method, headers: h(currentUser), body: JSON.stringify(body) }).then(r => r.json());
      if (r.success) { setShowForm(false); setEditingId(null); setForm({ class_id: '', subject_id: '', chapter: '', content: '' }); await load(); }
    } catch {}
    setSaving(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this lesson plan?')) return;
    await fetch(`${API}/academics/lesson-plans/${id}`, { method: 'DELETE', headers: h(currentUser) });
    await load();
  };

  return (
    <ToolPage title="Lesson Plans" subtitle="Create & manage lesson plans" loading={loading}
      actions={<ActionBtn label="New Plan" onClick={openCreate} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{editingId ? 'Edit Plan' : 'New Lesson Plan'}</h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Class" type="select" value={form.class_id} onChange={f('class_id')} options={classes.map(c => ({ value: c.id, label: `${c.name}-${c.section}` }))} />
              <FormField label="Subject" type="select" value={form.subject_id} onChange={f('subject_id')} options={subjects.map(s => ({ value: s.id, label: s.name }))} />
              <FormField label="Chapter / Topic" value={form.chapter} onChange={f('chapter')} placeholder="Chapter name/topic" required />
            </div>
            <FormField label="Lesson Notes / Content" type="textarea" value={form.content} onChange={f('content')} placeholder="Lesson plan details, objectives, activities..." />
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : editingId ? 'Update' : 'Save Plan'} disabled={saving} type="submit" />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ borderBottom: '1px solid var(--c-border)' }}>
            {['Chapter', 'Subject', 'Class', 'Created', 'Actions'].map(c => <th key={c} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>{c}</th>)}
          </tr></thead>
          <tbody>
            {plans.length === 0 ? <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No lesson plans yet</td></tr>
              : plans.map((p, i) => {
                const subj = subjects.find(s => s.id === p.subject_id);
                const cls = classes.find(c => c.id === p.class_id);
                return (
                  <tr key={p.id} style={{ borderBottom: i < plans.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)' }}>{p.chapter}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{subj?.name || 'N/A'}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{cls ? `${cls.name}-${cls.section}` : 'N/A'}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{p.created_at?.slice(0, 10) || 'N/A'}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => openEdit(p)} style={btnStyle('var(--tool-hex-4f8ff7)')}>Edit</button>
                        <button onClick={() => handleDelete(p.id)} style={btnStyle('var(--tool-hex-f87171)')}>Delete</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </ToolPage>
  );
}

// 8-12: Remaining Teacher Tools
export function WorksheetCreator() {
  const { currentUser } = useUser();
  const [worksheets, setWorksheets] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ subject_id: '', topic: '', type: 'practice', content: '' });
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const load = async () => {
    const r = await fetch(`${API}/academics/worksheets`, { headers: h(currentUser) }).then(r => r.json()).catch(() => ({ success: false }));
    if (r.success) setWorksheets(r.data || []);
  };

  useEffect(() => {
    Promise.all([
      fetch(`${API}/academics/subjects`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setSubjects(r.data || []); }),
      load(),
    ]).finally(() => setLoading(false));
  }, []);

  const openCreate = () => { setEditingId(null); setForm({ subject_id: '', topic: '', type: 'practice', content: '' }); setShowForm(true); };
  const openEdit = (w) => { setEditingId(w.id); setForm({ subject_id: w.subject_id || '', topic: w.topic || '', type: w.type || 'practice', content: w.content || '' }); setShowForm(true); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const url = editingId ? `${API}/academics/worksheets/${editingId}` : `${API}/academics/worksheets`;
    const method = editingId ? 'PATCH' : 'POST';
    await fetch(url, { method, headers: h(currentUser), body: JSON.stringify(form) }).catch(() => {});
    setShowForm(false); setEditingId(null);
    await load();
    setSaving(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this worksheet?')) return;
    await fetch(`${API}/academics/worksheets/${id}`, { method: 'DELETE', headers: h(currentUser) });
    await load();
  };

  return (
    <ToolPage title="Worksheets" subtitle="Create & manage practice sheets" loading={loading}
      actions={<ActionBtn label="New Worksheet" onClick={openCreate} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{editingId ? 'Edit Worksheet' : 'New Worksheet'}</h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label="Subject" type="select" value={form.subject_id} onChange={f('subject_id')} options={subjects.map(s => ({ value: s.id, label: s.name }))} />
              <FormField label="Type" type="select" value={form.type} onChange={f('type')} options={['practice', 'revision', 'homework'].map(v => ({ value: v, label: v }))} />
              <FormField label="Topic" value={form.topic} onChange={f('topic')} placeholder="Chapter/topic name" required />
            </div>
            <FormField label="Content / Questions" type="textarea" value={form.content} onChange={f('content')} placeholder="Write questions or worksheet content..." />
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : editingId ? 'Update' : 'Save'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ borderBottom: '1px solid var(--c-border)' }}>
            {['Topic', 'Subject', 'Type', 'Created', 'Actions'].map(c => <th key={c} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>{c}</th>)}
          </tr></thead>
          <tbody>
            {worksheets.length === 0 ? <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No worksheets yet</td></tr>
              : worksheets.map((w, i) => (
                <tr key={w.id} style={{ borderBottom: i < worksheets.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)' }}>{w.topic}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{subjects.find(s => s.id === w.subject_id)?.name || 'N/A'}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{w.type}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{w.created_at?.slice(0, 10)}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => openEdit(w)} style={btnStyle('var(--tool-hex-4f8ff7)')}>Edit</button>
                      <button onClick={() => handleDelete(w.id)} style={btnStyle('var(--tool-hex-f87171)')}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </ToolPage>
  );
}

export function SubstitutionViewer() {
  const { currentUser } = useUser();
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch timetable changes / substitutions
    fetch(`${API}/academics/substitutions?user_id=${currentUser.id}`, { headers: h(currentUser) })
      .then(r => r.json()).then(r => { if (r.success) setSubs(r.data || []); })
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <ToolPage title="Substitution Viewer" subtitle="View your schedule changes" loading={loading}>
      {subs.length === 0 ? (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, fontSize: 13 }}>
          No substitution assignments for today. Check back later.
        </div>
      ) : (
        <DataTable headers={['Date', 'Period', 'Original Teacher', 'Class', 'Subject']}
          rows={subs.map(s => [s.date, s.period_number, s.original_teacher, s.class_name, s.subject_name])}
        />
      )}
    </ToolPage>
  );
}
export function ClassPerformanceAnalytics() {
  const { currentUser } = useUser();
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);

  useEffect(() => {
    getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }).finally(() => setLoading(false));
  }, []);

  const handleClassChange = async (classId) => {
    setSelectedClass(classId);
    setStudents([]);
    setResults([]);
    if (!classId) return;
    setLoadingResults(true);
    try {
      const [stuRes, resRes] = await Promise.all([
        fetch(`${API}/students?class_id=${classId}`, { headers: h(currentUser) }).then(r => r.json()),
        fetch(`${API}/academics/results?class_id=${classId}`, { headers: h(currentUser) }).then(r => r.json()),
      ]);
      if (stuRes.success) setStudents(stuRes.data || []);
      if (resRes.success) setResults(resRes.data || []);
    } catch {}
    setLoadingResults(false);
  };

  const selectedCls = classes.find(c => c.id === selectedClass);
  const avgMarks = results.length > 0 ? Math.round(results.reduce((s, r) => s + (r.marks_obtained || 0), 0) / results.length) : 0;

  return (
    <ToolPage title="Student Performance" subtitle="View performance by class" loading={loading}>
      <div style={{ marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <select value={selectedClass} onChange={e => handleClassChange(e.target.value)}
          style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '8px 12px', color: 'var(--c-text)', fontSize: 12, outline: 'none', minWidth: 160 }}>
          <option value="">Select Class & Section</option>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name} - {c.section}</option>)}
        </select>
        {selectedCls && <span style={{ fontSize: 12, color: 'var(--c-faint)' }}>{students.length} students enrolled</span>}
      </div>
      {!selectedClass ? (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, fontSize: 13 }}>
          Select a class to view student performance
        </div>
      ) : loadingResults ? (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', fontSize: 13 }}>Loading...</div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18 }}>
            <StatCard value={students.length} label="STUDENTS" color="var(--tool-hex-4f8ff7)" />
            <StatCard value={results.length} label="RESULT ENTRIES" color="var(--tool-hex-a78bfa)" />
            <StatCard value={results.length ? `${avgMarks}/100` : 'N/A'} label="AVG MARKS" color="var(--tool-hex-34d399)" />
            <StatCard value={results.filter(r => r.marks_obtained >= 80).length} label="ABOVE 80%" color="var(--tool-hex-fbbf24)" />
          </div>
          {results.length > 0 ? (
            <DataTable headers={['Student', 'Subject', 'Marks', 'Grade']}
              rows={results.map(r => [r.student_name, r.subject_name, `${r.marks_obtained}/${r.max_marks}`, <Badge text={r.grade || 'N/A'} color={r.grade?.startsWith('A') ? 'green' : 'blue'} />])}
            />
          ) : (
            <DataTable headers={['Student', 'Roll No', 'Status']}
              rows={students.map(s => [s.name, s.roll_number || 'N/A', <Badge text="No Results" color="gray" />])}
              emptyMsg="No students in this class"
            />
          )}
        </>
      )}
    </ToolPage>
  );
}
export function PtmNotes() {
  const { currentUser } = useUser();
  const [notes, setNotes] = useState([]);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [filteredStudents, setFilteredStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ class_id: '', student_id: '', notes: '' });
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));

  const load = async () => {
    const r = await fetch(`${API}/academics/ptm-notes`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setNotes(r.data || []);
  };

  useEffect(() => {
    Promise.all([
      getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }),
      getStudents(currentUser).then(r => { if (r.success) setStudents(r.data || []); }),
      load(),
    ]).finally(() => setLoading(false));
  }, []);

  const handleClassChange = (classId) => {
    setForm(p => ({ ...p, class_id: classId, student_id: '' }));
    setFilteredStudents(students.filter(s => s.class_id === classId));
  };

  const openCreate = () => { setEditingId(null); setForm({ class_id: '', student_id: '', notes: '' }); setFilteredStudents([]); setShowForm(true); };
  const openEdit = (n) => {
    setEditingId(n.id);
    const stuClass = students.find(s => s.id === n.student_id);
    const classId = stuClass?.class_id || '';
    setFilteredStudents(students.filter(s => s.class_id === classId));
    setForm({ class_id: classId, student_id: n.student_id || '', notes: n.notes || '' });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const url = editingId ? `${API}/academics/ptm-notes/${editingId}` : `${API}/academics/ptm-notes`;
    const method = editingId ? 'PATCH' : 'POST';
    await fetch(url, { method, headers: h(currentUser), body: JSON.stringify({ student_id: form.student_id, notes: form.notes }) });
    setShowForm(false); setEditingId(null); setForm({ class_id: '', student_id: '', notes: '' }); setFilteredStudents([]);
    await load();
    setSaving(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this PTM note?')) return;
    await fetch(`${API}/academics/ptm-notes/${id}`, { method: 'DELETE', headers: h(currentUser) });
    await load();
  };

  return (
    <ToolPage title="PTM Notes" subtitle="Record parent-teacher meeting notes" loading={loading}
      actions={<ActionBtn label="New Note" onClick={openCreate} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16, maxWidth: 520 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{editingId ? 'Edit PTM Note' : 'New PTM Note'}</h3>
          <form onSubmit={handleSubmit}>
            <FormField label="Class & Section" type="select" value={form.class_id} onChange={handleClassChange}
              options={classes.map(c => ({ value: c.id, label: `${c.name} - ${c.section}` }))} required />
            <FormField label="Student" type="select" value={form.student_id} onChange={f('student_id')}
              options={filteredStudents.map(s => ({ value: s.id, label: s.name }))} required />
            <FormField label="PTM Notes" type="textarea" value={form.notes} onChange={f('notes')} placeholder="Notes from the parent-teacher meeting..." required />
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : editingId ? 'Update' : 'Save Notes'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ borderBottom: '1px solid var(--c-border)' }}>
            {['Student', 'Notes', 'Date', 'Actions'].map(c => <th key={c} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>{c}</th>)}
          </tr></thead>
          <tbody>
            {notes.length === 0 ? <tr><td colSpan={4} style={{ padding: 20, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No PTM notes yet</td></tr>
              : notes.map((n, i) => (
                <tr key={n.id} style={{ borderBottom: i < notes.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)' }}>{n.student_name}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{(n.notes?.slice(0, 60) || '') + (n.notes?.length > 60 ? '...' : '')}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{n.created_at?.slice(0, 10)}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => openEdit(n)} style={btnStyle('var(--tool-hex-4f8ff7)')}>Edit</button>
                      <button onClick={() => handleDelete(n.id)} style={btnStyle('var(--tool-hex-f87171)')}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </ToolPage>
  );
}
export function CurriculumTracker() {
  const { currentUser } = useUser();
  const [progress, setProgress] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ class_id: '', subject_id: '', topic: '', status: 'not_started' });
  const [saving, setSaving] = useState(false);
  const f = k => v => setForm(p => ({ ...p, [k]: v }));
  const statusColors = { not_started: 'gray', in_progress: 'yellow', completed: 'green', revised: 'blue' };

  const load = async () => {
    const r = await fetch(`${API}/academics/curriculum`, { headers: h(currentUser) }).then(r => r.json());
    if (r.success) setProgress(r.data || []);
  };

  useEffect(() => {
    Promise.all([
      getAllClasses(currentUser).then(r => { if (r.success) setClasses(r.data || []); }),
      fetch(`${API}/academics/subjects`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setSubjects(r.data || []); }),
      load(),
    ]).finally(() => setLoading(false));
  }, []);

  const openCreate = () => { setEditingId(null); setForm({ class_id: '', subject_id: '', topic: '', status: 'not_started' }); setShowForm(true); };
  const openEdit = (p) => { setEditingId(p.id); setForm({ class_id: p.class_id || '', subject_id: p.subject_id || '', topic: p.topic || '', status: p.status || 'not_started' }); setShowForm(true); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.topic) return;
    setSaving(true);
    const url = editingId ? `${API}/academics/curriculum/${editingId}` : `${API}/academics/curriculum`;
    const method = editingId ? 'PATCH' : 'POST';
    await fetch(url, { method, headers: h(currentUser), body: JSON.stringify(form) });
    setShowForm(false); setEditingId(null); setForm({ class_id: '', subject_id: '', topic: '', status: 'not_started' });
    await load();
    setSaving(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this curriculum entry?')) return;
    await fetch(`${API}/academics/curriculum/${id}`, { method: 'DELETE', headers: h(currentUser) });
    await load();
  };

  return (
    <ToolPage title="Curriculum Tracker" subtitle="Track & manage syllabus coverage" loading={loading}
      actions={<ActionBtn label="Add Topic" onClick={openCreate} icon={<Plus size={11} />} />}>
      {showForm && (
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 14 }}>{editingId ? 'Edit Entry' : 'Add Topic'}</h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10 }}>
              <FormField label="Class" type="select" value={form.class_id} onChange={f('class_id')} options={classes.map(c => ({ value: c.id, label: `${c.name}-${c.section}` }))} />
              <FormField label="Subject" type="select" value={form.subject_id} onChange={f('subject_id')} options={subjects.map(s => ({ value: s.id, label: s.name }))} />
              <FormField label="Topic" value={form.topic} onChange={f('topic')} placeholder="Chapter/topic" required />
              <FormField label="Status" type="select" value={form.status} onChange={f('status')} options={['not_started', 'in_progress', 'completed', 'revised'].map(v => ({ value: v, label: v.replace('_', ' ') }))} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <ActionBtn label={saving ? 'Saving...' : editingId ? 'Update' : 'Add'} type="submit" disabled={saving} />
              <ActionBtn label="Cancel" variant="secondary" onClick={() => setShowForm(false)} />
            </div>
          </form>
        </div>
      )}
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ borderBottom: '1px solid var(--c-border)' }}>
            {['Topic', 'Class', 'Subject', 'Status', 'Updated', 'Actions'].map(c => <th key={c} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase' }}>{c}</th>)}
          </tr></thead>
          <tbody>
            {progress.length === 0 ? <tr><td colSpan={6} style={{ padding: 20, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No curriculum entries yet</td></tr>
              : progress.map((p, i) => {
                const cls = classes.find(c => c.id === p.class_id);
                const subj = subjects.find(s => s.id === p.subject_id);
                return (
                  <tr key={p.id} style={{ borderBottom: i < progress.length - 1 ? '1px solid var(--c-border)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)' }}>{p.topic}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{cls ? `${cls.name}-${cls.section}` : 'N/A'}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{subj?.name || 'N/A'}</td>
                    <td style={{ padding: '10px 14px' }}><Badge text={p.status?.replace('_', ' ')} color={statusColors[p.status] || 'gray'} /></td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{p.updated_at?.slice(0, 10)}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => openEdit(p)} style={btnStyle('var(--tool-hex-4f8ff7)')}>Edit</button>
                        <button onClick={() => handleDelete(p.id)} style={btnStyle('var(--tool-hex-f87171)')}>Delete</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </ToolPage>
  );
}
