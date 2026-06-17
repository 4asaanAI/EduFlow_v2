import React, { useEffect, useState } from 'react';
import { Save, CheckCircle } from 'lucide-react';
import { ToolPage, FormField, ActionBtn, ErrorCard, LoadingCard } from './ToolPage';
import { getSchoolSettings, updateSchoolSettings, getAcademicYear, updateAcademicYear } from '@/lib/api';

const EMPTY = {
  school_name: '', board: '', established: '', principal: '',
  city: '', state: '', address: '',
  phone: '', email: '', website: '', logo_url: '',
  attendance_threshold: '',
};

const EMPTY_AI = {
  grading_system: '', fee_structure: '', class_naming: '', communication_tone: '',
};

function Section({ title, children }) {
  return (
    <div style={{
      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
      borderRadius: 14, padding: '18px 20px', marginBottom: 16,
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 14 }}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0 18px' }}>
        {children}
      </div>
    </div>
  );
}

export default function SchoolSettings() {
  const [form, setForm] = useState(EMPTY);
  const [ai, setAi] = useState(EMPTY_AI);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [academicYear, setAcademicYear] = useState('');
  const [ayError, setAyError] = useState('');
  const [aySaving, setAySaving] = useState(false);
  const [aySaved, setAySaved] = useState(false);

  const set = (key) => (val) => { setForm((f) => ({ ...f, [key]: val })); setSaved(false); };
  const setAiField = (key) => (val) => { setAi((a) => ({ ...a, [key]: val })); setSaved(false); };

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, ayRes] = await Promise.all([getSchoolSettings(), getAcademicYear()]);
      if (res.success && res.data) {
        const d = res.data;
        setForm({
          school_name: d.school_name || '', board: d.board || '', established: d.established || '',
          principal: d.principal || '', city: d.city || '', state: d.state || '', address: d.address || '',
          phone: d.phone || '', email: d.email || '', website: d.website || '', logo_url: d.logo_url || '',
          attendance_threshold: d.attendance_threshold != null ? String(d.attendance_threshold) : '',
        });
        setAi({
          grading_system: d.ai_context?.grading_system || '',
          fee_structure: d.ai_context?.fee_structure || '',
          class_naming: d.ai_context?.class_naming || '',
          communication_tone: d.ai_context?.communication_tone || '',
        });
      } else {
        setError(res.detail || 'Unable to load school settings');
      }
      if (ayRes.success && ayRes.data) {
        setAcademicYear(ayRes.data.name || ayRes.data.year || '');
      }
    } catch {
      setError('Network error — please try again');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAcademicYear = async () => {
    setAyError('');
    if (!academicYear.trim()) { setAyError('Academic year cannot be empty'); return; }
    setAySaving(true);
    try {
      const res = await updateAcademicYear(academicYear.trim());
      if (res.success) {
        setAySaved(true);
        setTimeout(() => setAySaved(false), 3000);
        window.dispatchEvent(new CustomEvent('academic-year-updated'));
      } else {
        setAyError(res.detail || 'Failed to save');
      }
    } catch {
      setAyError('Network error');
    } finally {
      setAySaving(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload = { ...form, ai_context: { ...ai } };
      if (payload.attendance_threshold === '') {
        delete payload.attendance_threshold;
      } else {
        const n = Number(payload.attendance_threshold);
        if (Number.isNaN(n) || n < 0 || n > 100) {
          setError('Attendance threshold must be a number between 0 and 100');
          setSaving(false);
          return;
        }
        payload.attendance_threshold = n;
      }
      const res = await updateSchoolSettings(payload);
      if (res.success) {
        setSaved(true);
        window.dispatchEvent(new CustomEvent('school-settings-updated'));
      } else {
        setError(res.detail || 'Failed to save settings');
      }
    } catch {
      setError('Network error — please try again');
    } finally {
      setSaving(false);
    }
  };

  const actions = (
    <ActionBtn label={saving ? 'Saving…' : 'Save Changes'} icon={<Save size={13} />} onClick={handleSave} disabled={saving || loading} />
  );

  return (
    <ToolPage title="School Settings" subtitle="School identity & profile — visible to all roles" onRefresh={load} loading={loading} actions={actions}>
      {error && <ErrorCard message={error} onRetry={load} />}
      {saved && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', marginBottom: 16,
          background: 'color-mix(in srgb, var(--color-success, #22c55e) 10%, transparent)',
          border: '1px solid color-mix(in srgb, var(--color-success, #22c55e) 35%, transparent)',
          borderRadius: 10, color: 'var(--color-success, #22c55e)', fontSize: 13, fontWeight: 600 }}>
          <CheckCircle size={15} /> Settings saved — changes are live across the platform.
        </div>
      )}

      {loading ? <LoadingCard message="Loading school settings…" /> : (
        <>
          <Section title="Identity">
            <FormField label="School Name" value={form.school_name} onChange={set('school_name')} placeholder="The Aaryans CBSE School" required />
            <FormField label="Board" value={form.board} onChange={set('board')} placeholder="CBSE" />
            <FormField label="Established (Year)" value={form.established} onChange={set('established')} placeholder="2005" />
            <FormField label="Principal" value={form.principal} onChange={set('principal')} placeholder="Dr. Anand Sharma" />
          </Section>

          <Section title="Location">
            <FormField label="City" value={form.city} onChange={set('city')} placeholder="Lucknow" />
            <FormField label="State" value={form.state} onChange={set('state')} placeholder="Uttar Pradesh" />
            <FormField label="Address" type="textarea" value={form.address} onChange={set('address')} placeholder="Sector 12, Jankipuram, Lucknow, UP 226021" />
          </Section>

          <Section title="Contact">
            <FormField label="Phone" value={form.phone} onChange={set('phone')} placeholder="0522-4567890" />
            <FormField label="Email" type="email" value={form.email} onChange={set('email')} placeholder="info@school.edu.in" />
            <FormField label="Website" value={form.website} onChange={set('website')} placeholder="www.school.edu.in" />
            <FormField label="Logo URL" value={form.logo_url} onChange={set('logo_url')} placeholder="https://…" />
          </Section>

          <Section title="Configuration">
            <FormField label="Attendance Threshold (%)" type="number" value={form.attendance_threshold} onChange={set('attendance_threshold')} placeholder="75" />
          </Section>

          <Section title="AI Assistant Context">
            <FormField label="Grading System" value={ai.grading_system} onChange={setAiField('grading_system')} placeholder="CGPA (10 point scale)" />
            <FormField label="Fee Structure" value={ai.fee_structure} onChange={setAiField('fee_structure')} placeholder="Monthly tuition + quarterly exam fee" />
            <FormField label="Class Naming" value={ai.class_naming} onChange={setAiField('class_naming')} placeholder="Class 9, 10, 11, 12" />
            <FormField label="Communication Tone" value={ai.communication_tone} onChange={setAiField('communication_tone')} placeholder="Professional Hindi + English" />
          </Section>
        </>
      )}

      {/* Academic Year — separate save, always visible */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 14, padding: '18px 20px', marginBottom: 16,
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 14 }}>Academic Year</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 180 }}>
            <FormField
              label="Current Academic Year"
              value={academicYear}
              onChange={v => { setAcademicYear(v); setAyError(''); setAySaved(false); }}
              placeholder="2025-26"
            />
          </div>
          <div style={{ paddingBottom: 2 }}>
            <ActionBtn
              label={aySaving ? 'Saving…' : aySaved ? 'Saved!' : 'Update Year'}
              icon={aySaved ? <CheckCircle size={13} /> : <Save size={13} />}
              onClick={handleSaveAcademicYear}
              disabled={aySaving}
            />
          </div>
        </div>
        {ayError && <div style={{ fontSize: 12, color: '#f87171', marginTop: 6 }}>{ayError}</div>}
        <div style={{ fontSize: 11, color: 'var(--color-text-secondary, #888)', marginTop: 8 }}>
          Updates everywhere — header bar, profile, and settings About section.
        </div>
      </div>
    </ToolPage>
  );
}
