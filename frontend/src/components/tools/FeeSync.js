import React, { useState } from 'react';
import { AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import { getFeeSyncJob, resolveFeeSyncConflict, triggerFeeSync } from '../../lib/api';

export default function FeeSync() {
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function trigger() {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const res = await triggerFeeSync();
      if (!res.success) throw new Error(res.detail || 'Fee sync could not start');
      setJob(res.data);
      setNotice('Fee sync completed. Review conflicts before marking it done.');
    } catch (err) {
      setError(err.message || 'Fee sync could not start. Check FEE_API_BASE_URL and FEE_API_KEY.');
    } finally {
      setLoading(false);
    }
  }

  async function refresh() {
    if (!job?.sync_job_id && !job?.id) return;
    const id = job.sync_job_id || job.id;
    setLoading(true);
    setError('');
    try {
      const res = await getFeeSyncJob(id);
      if (!res.success) throw new Error(res.detail || 'Unable to load sync job');
      setJob(res.data);
    } catch (err) {
      setError(err.message || 'Unable to load sync job.');
    } finally {
      setLoading(false);
    }
  }

  async function resolve(conflictId, decision) {
    const id = job.sync_job_id || job.id;
    setLoading(true);
    setError('');
    try {
      const res = await resolveFeeSyncConflict(id, { conflict_id: conflictId, decision });
      if (!res.success) throw new Error(res.detail || 'Unable to resolve conflict');
      setJob(res.data);
      setNotice('Conflict resolved.');
    } catch (err) {
      setError(err.message || 'Unable to resolve conflict. Owner access is required.');
    } finally {
      setLoading(false);
    }
  }

  const conflicts = job?.conflicts || [];

  return (
    <div data-testid="fee-sync-tool" style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 18, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: 0, color: 'var(--c-text)', fontSize: 22, fontWeight: 650 }}>Fee software sync</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--c-faint)', fontSize: 12 }}>Manual sync, conflict review, and owner resolution</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={refresh} disabled={loading || !job} style={buttonStyle('var(--c-bg)', 'var(--c-text)')}><RefreshCw size={15} />Refresh</button>
          <button onClick={trigger} disabled={loading} style={buttonStyle('var(--tool-hex-4f8ff7)', 'var(--tool-hex-fff)')}>{loading ? 'Working...' : 'Trigger sync'}</button>
        </div>
      </div>

      {error && <div role="alert" style={alertStyle('var(--tool-hex-f87171)')}><AlertTriangle size={16} />{error}</div>}
      {notice && <div style={alertStyle('var(--tool-hex-34d399)')}><CheckCircle size={16} />{notice}</div>}

      <section style={panelStyle}>
        {!job ? (
          <div style={emptyStyle}>No sync job has been triggered in this session.</div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10, marginBottom: 14 }}>
              {[
                ['Status', job.status],
                ['Synced', job.synced_count || 0],
                ['Conflicts', job.conflict_count || 0],
              ].map(([label, value]) => (
                <div key={label} style={{ background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 12 }}>
                  <div style={{ color: 'var(--c-text)', fontWeight: 750, fontSize: 18 }}>{value}</div>
                  <div style={{ color: 'var(--c-faint)', fontSize: 10, textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
                </div>
              ))}
            </div>
            {conflicts.length === 0 ? (
              <div style={emptyStyle}>No unresolved conflicts.</div>
            ) : conflicts.map(conflict => (
              <div key={conflict.id} style={{ borderTop: '1px solid var(--c-border)', padding: '12px 0' }}>
                <div style={{ color: 'var(--c-text)', fontWeight: 700, fontSize: 13 }}>{conflict.student_id} / {conflict.period} / {conflict.fee_head}</div>
                <div style={{ color: 'var(--c-faint)', fontSize: 12, marginTop: 4 }}>Ours: Rs {conflict.ours?.amount} | Theirs: Rs {conflict.theirs?.amount}</div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button onClick={() => resolve(conflict.id, 'keep_ours')} disabled={loading || conflict.status === 'resolved'} style={buttonStyle('var(--c-bg)', 'var(--c-text)')}>Keep ours</button>
                  <button onClick={() => resolve(conflict.id, 'use_theirs')} disabled={loading || conflict.status === 'resolved'} style={buttonStyle('var(--tool-hex-6366f1)', 'var(--tool-hex-fff)')}>Use theirs</button>
                </div>
              </div>
            ))}
          </>
        )}
      </section>
    </div>
  );
}

const panelStyle = { background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: 14 };
const emptyStyle = { padding: 28, color: 'var(--c-faint)', textAlign: 'center', fontSize: 13 };
const buttonStyle = (background, color) => ({ minHeight: 44, display: 'inline-flex', alignItems: 'center', gap: 8, background, color, border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 14px', fontWeight: 700, cursor: 'pointer' });
const alertStyle = color => ({ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: 12, border: `1px solid color-mix(in srgb, ${color} 33%, transparent)`, borderRadius: 8, background: `color-mix(in srgb, ${color} 7%, transparent)`, color, fontSize: 13 });
