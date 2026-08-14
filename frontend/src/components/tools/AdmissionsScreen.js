import React, { useState } from 'react';
import { useUser } from '../../contexts/UserContext';
import { ToolPage } from './ToolPage';
import { EnquiriesPanel } from './AdminTools';
import { AdmissionsPipelinePanel } from './CommercialOperations';
import AdmissionsWorkflow from './AdmissionsWorkflow';
import AdmissionTests from './AdmissionTests';

/**
 * A4: one admissions screen.
 *
 * Three screens described the same funnel. "Admission Funnel" showed the owner a
 * read-only count of enquiries. "Enquiry Register" ran the pipeline and had the
 * applications bolted onto the bottom of it. "Legal Entities & Admissions" held the
 * same enquiries again as CRM leads, with values against them. A person looking for one
 * family had three places to look and no way of knowing which was the real one.
 *
 * GROUPING NEVER GRANTS. This screen picks a tab; it does not decide who may open it.
 * Who reaches the screen at all is `backend/services/profile_matrix.py`, where the two
 * old entries were replaced by this one, so anybody who had either has exactly this and
 * anybody who had neither still has neither. The pipeline tab keeps its own gate, the
 * same one it has always had, so the management head does not gain it by the tabs
 * existing.
 *
 * NOTHING IS DROPPED. Everything the three screens did is on a tab here. The owner's
 * read-only funnel counts are the header of the enquiries tab, which is the same
 * figures with the ability to act on them.
 *
 * The Tests tab was deliberately ABSENT until 2026-08-15, and there was a test asserting
 * its absence, because a tab opening onto nothing is exactly the fault this work removes:
 * a button that looks like a feature. B1 built the thing, so the tab is real now and that
 * test was flipped to assert it works rather than deleted.
 */
export function Admissions() {
  const { currentUser } = useUser();
  const maySeePipeline = currentUser?.role === 'owner'
    || ['principal', 'admission', 'receptionist'].includes(currentUser?.sub_category);

  const [tab, setTab] = useState('enquiries');
  const [error, setError] = useState('');
  // Starting an application from an enquiry row has to reach the applications tab, which
  // may not be mounted at the time. Bumping this makes it reload when it next opens.
  const [applicationsKey, setApplicationsKey] = useState(0);

  const availableTabs = [
    ['enquiries', 'Enquiries'],
    ['applications', 'Applications'],
    // B1. Everybody who reaches this screen reaches Tests, because the routes behind it
    // carry the same gate the assessment route has always had. Grouping still grants
    // nothing: a desk that could record one child's score can now record the same scores
    // from a list.
    ['tests', 'Tests'],
    ...(maySeePipeline ? [['pipeline', 'Pipeline value']] : []),
  ];

  return (
    <ToolPage title="Admissions" subtitle="Enquiries, applications and pipeline value, in one place">
      {error && <div role="alert" style={errorStyle}>{error}</div>}
      <div role="tablist" aria-label="Admissions sections" style={tabs}>
        {availableTabs.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={tab === value}
            onClick={() => setTab(value)}
            style={{ ...tabButton, ...(tab === value ? activeTab : {}) }}>{label}</button>
        ))}
      </div>
      {tab === 'enquiries' && (
        <EnquiriesPanel onStarted={() => setApplicationsKey(key => key + 1)} />
      )}
      {tab === 'applications' && <AdmissionsWorkflow reloadKey={applicationsKey} />}
      {tab === 'tests' && <AdmissionTests />}
      {tab === 'pipeline' && maySeePipeline && <AdmissionsPipelinePanel setError={setError} />}
    </ToolPage>
  );
}

export default Admissions;

const tabs = { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 };
const tabButton = { border: '1px solid var(--color-border)', borderRadius: 8, padding: '9px 13px', background: 'var(--color-surface-raised)', color: 'var(--color-text-secondary)', cursor: 'pointer', fontWeight: 600, minHeight: 40 };
const activeTab = { background: 'var(--accent-primary)', color: '#fff', border: '1px solid var(--accent-primary)' };
const errorStyle = { padding: 12, marginBottom: 12, borderRadius: 8, background: 'rgba(248,113,113,.12)', color: 'var(--tool-hex-f87171)' };
