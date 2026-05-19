import React, { useEffect, useRef, useState } from 'react';
import { Building2, CheckCircle, Circle, Copy, RefreshCw } from 'lucide-react';
import { createSchool, fetchSchoolOnboardingStatus } from '@/lib/api';

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/;

const inputStyle = {
  width: '100%',
  padding: '8px 12px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg-card)',
  color: 'var(--text-primary)',
  fontSize: 14,
  boxSizing: 'border-box',
};

const labelStyle = { fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' };

const errorStyle = { fontSize: 12, color: 'var(--color-error, #ef4444)', marginTop: 4 };

const btnStyle = (disabled) => ({
  padding: '8px 20px',
  borderRadius: 8,
  border: 'none',
  background: disabled ? 'var(--border)' : 'var(--color-primary, #6366f1)',
  color: disabled ? 'var(--text-muted)' : '#fff',
  fontWeight: 600,
  fontSize: 14,
  cursor: disabled ? 'not-allowed' : 'pointer',
});

const STEP_LABELS = {
  profile_created: 'School profile created',
  first_staff_added: 'First staff member added',
  first_class_configured: 'First class configured',
  first_student_imported: 'First student imported',
  first_fee_record_created: 'First fee structure created',
};

function ChecklistRow({ label, done }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      {done
        ? <CheckCircle size={16} color="var(--color-success, #22c55e)" />
        : <Circle size={16} color="var(--text-muted)" />}
      <span style={{ fontSize: 14, color: done ? 'var(--text-primary)' : 'var(--text-muted)' }}>{label}</span>
    </div>
  );
}

function CopyField({ label, value }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div style={{ marginBottom: 12 }}>
      <span style={labelStyle}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <code style={{ flex: 1, padding: '6px 10px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, color: 'var(--text-primary)' }}>
          {value}
        </code>
        <button
          data-testid={`copy-${label.toLowerCase().replace(/\s/g, '-')}`}
          onClick={copy}
          style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-card)', cursor: 'pointer', color: 'var(--text-secondary)' }}
        >
          <Copy size={14} />
          {copied && <span style={{ marginLeft: 4, fontSize: 11 }}>Copied</span>}
        </button>
      </div>
    </div>
  );
}

export default function SchoolOnboarding() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ school_name: '', school_id: '', plan_tier: 'starter', owner_email: '' });
  const [errors, setErrors] = useState({});
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [credentials, setCredentials] = useState(null);
  const [checklist, setChecklist] = useState(null);
  const [checklistLoading, setChecklistLoading] = useState(false);
  const intervalRef = useRef(null);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const validateStep1 = () => {
    const e = {};
    if (!form.school_name.trim()) e.school_name = 'School name is required';
    if (!SLUG_RE.test(form.school_id)) e.school_id = 'Must be 3–50 chars: lowercase letters, numbers, hyphens only';
    if (!form.plan_tier) e.plan_tier = 'Select a plan';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const validateStep2 = () => {
    const e = {};
    if (!form.owner_email.trim() || !form.owner_email.includes('@')) e.owner_email = 'Valid email required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleNext = () => {
    if (step === 1 && validateStep1()) setStep(2);
    if (step === 2 && validateStep2()) setStep(3);
  };

  const handleCreate = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      const res = await createSchool({
        school_name: form.school_name.trim(),
        school_id: form.school_id.trim(),
        plan_tier: form.plan_tier,
        owner_email: form.owner_email.trim(),
      });
      if (res.success) {
        setCredentials(res.data);
        setStep(4);
        pollChecklist(res.data.school_id);
      } else {
        setCreateError(res.detail || 'Failed to create school');
      }
    } catch {
      setCreateError('Network error — please try again');
    } finally {
      setCreating(false);
    }
  };

  const pollChecklist = (schoolId) => {
    let mounted = true;
    const load = async () => {
      if (!mounted) return;
      if (mounted) setChecklistLoading(true);
      try {
        const res = await fetchSchoolOnboardingStatus(schoolId);
        if (!mounted) return;
        if (res.success) {
          setChecklist(res.data);
          if (res.data.completed) clearInterval(intervalRef.current);
        }
      } catch {
        // fail silently — will retry on next interval
      } finally {
        if (mounted) setChecklistLoading(false);
      }
    };
    load();
    intervalRef.current = setInterval(load, 30000);
    return () => { mounted = false; };
  };

  useEffect(() => () => clearInterval(intervalRef.current), []);

  const containerStyle = {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '28px 32px',
    maxWidth: 560,
  };

  return (
    <div style={{ padding: '24px 32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <Building2 size={22} color="var(--color-primary, #6366f1)" />
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>New School Onboarding</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Set up a new school without manual database access</div>
        </div>
      </div>

      {/* Step indicator */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
        {[1, 2, 3].map((s) => (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: step >= s ? 'var(--color-primary, #6366f1)' : 'var(--border)',
              color: step >= s ? '#fff' : 'var(--text-muted)', fontSize: 12, fontWeight: 700,
            }}>{s}</div>
            <span style={{ fontSize: 12, color: step >= s ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              {s === 1 ? 'School Details' : s === 2 ? 'Owner Account' : 'Review'}
            </span>
            {s < 3 && <div style={{ width: 24, height: 1, background: 'var(--border)' }} />}
          </div>
        ))}
      </div>

      {/* Step 1: School Details */}
      {step === 1 && (
        <div style={containerStyle}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 20 }}>School Details</div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>School Name</label>
            <input
              data-testid="input-school-name"
              style={inputStyle}
              value={form.school_name}
              onChange={(e) => set('school_name', e.target.value)}
              placeholder="The Aaryans CBSE School"
            />
            {errors.school_name && <div style={errorStyle}>{errors.school_name}</div>}
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>School ID (slug)</label>
            <input
              data-testid="input-school-id"
              style={inputStyle}
              value={form.school_id}
              onChange={(e) => set('school_id', e.target.value.toLowerCase())}
              placeholder="aaryans-joya"
            />
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              Lowercase letters, numbers, hyphens. 3–50 chars. Cannot be changed later.
            </div>
            {errors.school_id && <div style={errorStyle}>{errors.school_id}</div>}
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>Plan Tier</label>
            <select
              data-testid="select-plan-tier"
              style={inputStyle}
              value={form.plan_tier}
              onChange={(e) => set('plan_tier', e.target.value)}
            >
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
            </select>
            {errors.plan_tier && <div style={errorStyle}>{errors.plan_tier}</div>}
          </div>
          <button data-testid="btn-next-step1" style={btnStyle(false)} onClick={handleNext}>Next →</button>
        </div>
      )}

      {/* Step 2: Owner Account */}
      {step === 2 && (
        <div style={containerStyle}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 20 }}>Owner Account</div>
          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>Owner Email</label>
            <input
              data-testid="input-owner-email"
              style={inputStyle}
              type="email"
              value={form.owner_email}
              onChange={(e) => set('owner_email', e.target.value)}
              placeholder="owner@school.edu"
            />
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              A temporary password will be generated and emailed to this address.
            </div>
            {errors.owner_email && <div style={errorStyle}>{errors.owner_email}</div>}
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button style={{ ...btnStyle(false), background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border)' }} onClick={() => setStep(1)}>← Back</button>
            <button data-testid="btn-next-step2" style={btnStyle(false)} onClick={handleNext}>Next →</button>
          </div>
        </div>
      )}

      {/* Step 3: Review & Create */}
      {step === 3 && (
        <div style={containerStyle}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 20 }}>Review & Create</div>
          <div style={{ background: 'var(--bg-surface, var(--bg-card))', border: '1px solid var(--border)', borderRadius: 8, padding: '16px 20px', marginBottom: 20, fontSize: 14, lineHeight: 2 }}>
            <div><strong>School Name:</strong> {form.school_name}</div>
            <div><strong>School ID:</strong> {form.school_id}</div>
            <div><strong>Plan:</strong> {form.plan_tier}</div>
            <div><strong>Owner Email:</strong> {form.owner_email}</div>
          </div>
          {createError && (
            <div style={{ ...errorStyle, marginBottom: 16, padding: '10px 14px', background: 'color-mix(in srgb, var(--color-error, #ef4444) 10%, transparent)', border: '1px solid var(--color-error, #ef4444)', borderRadius: 8 }}>
              {createError}
            </div>
          )}
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            ⚠️ School creation is irreversible. Confirm before proceeding.
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button style={{ ...btnStyle(false), background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border)' }} onClick={() => setStep(2)}>← Back</button>
            <button
              data-testid="btn-create-school"
              style={btnStyle(creating)}
              disabled={creating}
              onClick={handleCreate}
            >
              {creating ? 'Creating…' : 'Create School'}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Created — credentials + checklist */}
      {step === 4 && credentials && (
        <div>
          <div style={{ ...containerStyle, marginBottom: 20 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-success, #22c55e)', marginBottom: 4 }}>
              ✅ School Created Successfully
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
              Save these credentials — the temporary password is shown once only.
            </div>
            <CopyField label="Username" value={credentials.owner_username} />
            <CopyField label="Temporary Password" value={credentials.temporary_password} />
            <CopyField label="School ID" value={credentials.school_id} />
          </div>

          <div style={containerStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>Onboarding Checklist</div>
              {checklistLoading && <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite', color: 'var(--text-muted)' }} />}
              {checklist?.completed && (
                <span style={{ marginLeft: 'auto', fontSize: 12, background: 'color-mix(in srgb, var(--color-success, #22c55e) 15%, transparent)', color: 'var(--color-success, #22c55e)', padding: '2px 10px', borderRadius: 12, fontWeight: 600 }}>
                  Complete
                </span>
              )}
            </div>
            {checklist ? (
              Object.entries(STEP_LABELS).map(([key, label]) => (
                <ChecklistRow key={key} label={label} done={checklist.steps[key]} />
              ))
            ) : (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '12px 0' }}>Loading checklist…</div>
            )}
            {checklist && !checklist.completed && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
                Polling every 30 seconds. Checklist auto-completes once all steps are done.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
