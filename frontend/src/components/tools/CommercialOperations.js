import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useUser } from '../../contexts/UserContext';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ActionBtn, Badge, DataTable, FormField, StatCard, ToolPage } from './ToolPage';
import SearchableSelect from '../ui/SearchableSelect';

async function request(path, options = {}) {
  const response = await apiFetch(`${API}${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Commercial operation failed');
  return body;
}

const money = paise => `₹${(Number(paise || 0) / 100).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
// A2: the stages a person may choose. "enrolled" is deliberately absent everywhere a
// stage is picked. An enquiry becomes enrolled only when its admission application
// creates the child's record.
const PICKABLE_LEAD_STAGES = ['new', 'contacted', 'visit_scheduled', 'visited', 'documents_submitted', 'fee_paid', 'lost'];
const uniqueKey = prefix => `${prefix}-${typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`}`;

export default function CommercialOperations() {
  const { currentUser } = useUser();
  const subRole = currentUser?.sub_category;
  // A4: the CRM tab moved to the Admissions screen, where the enquiries and the
  // applications already are. Three screens described the admissions funnel and this
  // was the third. The overview below still counts the leads, because the money view of
  // a legal entity is what this screen is for.
  const canSummary = currentUser?.role === 'owner' || ['principal', 'accountant'].includes(subRole);
  // Campus retail was removed on 2026-08-14: The Aaryans runs no shop, and the canteen
  // is an outside vendor renting space rather than a school counter.
  const requestSeq = useRef(0);
  const [tab, setTab] = useState(canSummary ? 'overview' : 'entities');
  const [entities, setEntities] = useState([]);
  const [entityId, setEntityId] = useState('');
  const [summary, setSummary] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadEntities = useCallback(async () => {
    const body = await request('/commercial/entities');
    setEntities(body.data || []);
    const operating = (body.data || []).filter(item => !item.is_group && item.is_active !== false);
    setEntityId(value => operating.some(item => item.id === value)
      ? value : operating.find(item => item.is_default)?.id || operating[0]?.id || '');
  }, []);

  const loadDomain = useCallback(async () => {
    if (!entityId) { setLoading(false); return; }
    const sequence = ++requestSeq.current;
    setLoading(true); setError('');
    const query = `entity_id=${encodeURIComponent(entityId)}`;
    try {
      const tasks = [
        ...(canSummary ? [['summary', request(`/commercial/summary?${query}`)]] : []),
        // The lead COUNT still belongs on the entity overview, which is the money view
        // of that entity. Working the leads themselves is on the Admissions screen.
        ...(canSummary ? [['leads', request(`/commercial/crm/leads?${query}`)]] : []),
      ];
      const results = await Promise.allSettled(tasks.map(([, promise]) => promise));
      if (sequence !== requestSeq.current) return;
      const failures = [];
      results.forEach((result, index) => {
        const key = tasks[index][0];
        if (result.status === 'rejected') { failures.push(result.reason?.message || `${key} could not load`); return; }
        const data = result.value.data;
        if (key === 'summary') setSummary(data);
        if (key === 'leads') setLeads(data || []);
      });
      if (failures.length) setError(failures.join(' '));
    } catch (err) { setError(err.message); }
    finally { if (sequence === requestSeq.current) setLoading(false); }
  }, [canSummary, entityId]);

  useEffect(() => { loadEntities().catch(err => { setError(err.message); setLoading(false); }); }, [loadEntities]);
  useEffect(() => { loadDomain(); }, [loadDomain]);

  const refresh = async () => { await loadEntities(); await loadDomain(); };
  const selected = entities.find(item => item.id === entityId);
  const total = summary?.totals || {};
  const operatingEntities = entities.filter(item => !item.is_group && item.is_active !== false);
  const availableTabs = [...(canSummary ? ['overview'] : []), 'entities'];

  return <ToolPage title="Legal Entities" subtitle="The trust's legal entities, and what each is carrying" loading={loading} onRefresh={refresh}>
    {error && <div role="alert" style={errorStyle}>{error}</div>}
    <div style={toolbar}>
      <label style={{ minWidth: 210, flex: '1 1 240px' }}>
        <span style={labelStyle}>Operating legal entity</span>
        <SearchableSelect aria-label="Operating legal entity" value={entityId} onChange={event => setEntityId(event.target.value)} style={inputStyle}>
          {operatingEntities.map(item => <option key={item.id} value={item.id}>{item.name}{item.is_default ? ' (default)' : ''}</option>)}
        </SearchableSelect>
      </label>
      <div role="tablist" aria-label="Commercial operation sections" style={tabs}>
        {availableTabs.map(value => <button key={value} role="tab" aria-selected={tab === value}
          onClick={() => setTab(value)} style={{ ...tabButton, ...(tab === value ? activeTab : {}) }}>{value[0].toUpperCase() + value.slice(1)}</button>)}
      </div>
    </div>
    {tab === 'overview' && canSummary && <Overview entity={selected} total={total} leads={leads} />}
    {tab === 'entities' && <EntitiesPanel currentUser={currentUser} entities={entities} onChanged={refresh} setError={setError} />}
  </ToolPage>;
}

function Overview({ entity, total, leads }) {
  return <>
    <div style={stats}>
      <StatCard value={entity?.name || 'Not configured'} label="OPERATING ENTITY" color="var(--tool-hex-4f8ff7)" />
      <StatCard value={money(total.weighted_pipeline_paise)} label="WEIGHTED PIPELINE" color="var(--tool-hex-a78bfa)" />
      <StatCard value={leads.length} label="CRM LEADS" color="var(--tool-hex-fbbf24)" />
    </div>
    <p style={note}>Legacy records without a legal-entity field remain readable through the configured default. EduFlow does not rewrite them.</p>
  </>;
}

/**
 * A4: the admissions half of Legal Entities, now living on the Admissions screen.
 *
 * It stays in this file because every helper it needs is here. What moved is where it
 * is SHOWN, not who may see it: the gate below is character for character the `canCrm`
 * this screen has always used, so grouping grants nobody anything. The management head
 * is not on that list and was never on it, and does not gain the pipeline by the
 * Admissions screen existing.
 *
 * `receptionist` is on the list and is dormant. `admission` is on it too and is NOT a
 * sub-category the platform recognises at all, so it can never be true. Both are left
 * exactly as they were: A4 moves a panel, it does not redraw a permission.
 */
export function AdmissionsPipelinePanel({ setError }) {
  const { currentUser } = useUser();
  const maySee = currentUser?.role === 'owner'
    || ['principal', 'admission', 'receptionist'].includes(currentUser?.sub_category);
  const [entities, setEntities] = useState([]);
  const [entityId, setEntityId] = useState('');
  const [leads, setLeads] = useState([]);
  const [opportunities, setOpportunities] = useState([]);

  const loadEntities = useCallback(async () => {
    const body = await request('/commercial/entities');
    setEntities(body.data || []);
    const operating = (body.data || []).filter(item => !item.is_group && item.is_active !== false);
    setEntityId(value => operating.some(item => item.id === value)
      ? value : operating.find(item => item.is_default)?.id || operating[0]?.id || '');
  }, []);

  const loadDomain = useCallback(async () => {
    if (!entityId) return;
    const query = `entity_id=${encodeURIComponent(entityId)}`;
    try {
      const [leadBody, opportunityBody] = await Promise.all([
        request(`/commercial/crm/leads?${query}`),
        request(`/commercial/crm/opportunities?${query}`),
      ]);
      setLeads(leadBody.data || []);
      setOpportunities(opportunityBody.data || []);
    } catch (err) { setError(err.message); }
  }, [entityId, setError]);

  useEffect(() => {
    if (maySee) loadEntities().catch(err => setError(err.message));
  }, [maySee, loadEntities, setError]);
  useEffect(() => { if (maySee) loadDomain(); }, [maySee, loadDomain]);

  if (!maySee) return null;
  const operatingEntities = entities.filter(item => !item.is_group && item.is_active !== false);
  return <>
    <label style={{ minWidth: 210, display: 'block', marginBottom: 14 }}>
      <span style={labelStyle}>Operating legal entity</span>
      <SearchableSelect aria-label="Operating legal entity" value={entityId} onChange={event => setEntityId(event.target.value)} style={inputStyle}>
        {operatingEntities.map(item => <option key={item.id} value={item.id}>{item.name}{item.is_default ? ' (default)' : ''}</option>)}
      </SearchableSelect>
    </label>
    <CrmPanel entityId={entityId} leads={leads} opportunities={opportunities}
      onChanged={loadDomain} setError={setError} />
  </>;
}

function CrmPanel({ entityId, leads, opportunities, onChanged, setError }) {
  // A3: mother and father sit alongside `parent_name` here too. This screen and the
  // Enquiry Register write the same record through the same service, so one of them
  // collecting both parents and the other not would put the gap back in a new place.
  const emptyLead = { student_name: '', parent_name: '', mother_name: '', father_name: '', phone: '', email: '', class_applying: '', source: 'walk_in', next_follow_up: '', estimated_value: '', probability: 0 };
  const [form, setForm] = useState(emptyLead);
  const [selectedLeadId, setSelectedLeadId] = useState('');
  const [activities, setActivities] = useState([]);
  const [activity, setActivity] = useState({ activity_type: 'note', subject: '', notes: '', next_follow_up: '' });
  const [opportunity, setOpportunity] = useState({ title: '', amount: '', probability: 10, expected_close_date: '' });
  const selectedLead = leads.find(row => row.id === selectedLeadId);
  useEffect(() => {
    if (!selectedLeadId) { setActivities([]); return; }
    request(`/commercial/crm/leads/${selectedLeadId}/activities`)
      .then(body => setActivities(body.data || [])).catch(err => setError(err.message));
  }, [selectedLeadId, setError]);
  async function submit(event) {
    event.preventDefault(); setError('');
    try {
      await request('/commercial/crm/leads', { method: 'POST', body: JSON.stringify({ ...form, entity_id: entityId, estimated_value: Number(form.estimated_value || 0), probability: Number(form.probability || 0) }) });
      setForm(emptyLead);
      await onChanged();
    } catch (err) { setError(err.message); }
  }
  async function changeStatus(lead, status) {
    const lost_reason = status === 'lost' ? window.prompt('Why was this lead lost?') : undefined;
    if (status === 'lost' && !lost_reason) return;
    try {
      await request(`/commercial/crm/leads/${lead.id}`, { method: 'PATCH', body: JSON.stringify({ status, lost_reason }) });
      await onChanged();
    } catch (err) { setError(err.message); }
  }
  async function addActivity(event) {
    event.preventDefault();
    try {
      await request(`/commercial/crm/leads/${selectedLeadId}/activities`, { method: 'POST', body: JSON.stringify(activity) });
      setActivity({ activity_type: 'note', subject: '', notes: '', next_follow_up: '' });
      const body = await request(`/commercial/crm/leads/${selectedLeadId}/activities`);
      setActivities(body.data || []); await onChanged();
    } catch (err) { setError(err.message); }
  }
  async function addOpportunity(event) {
    event.preventDefault();
    try {
      await request(`/commercial/crm/leads/${selectedLeadId}/opportunities`, { method: 'POST', body: JSON.stringify({ ...opportunity, entity_id: entityId, amount: Number(opportunity.amount || 0), probability: Number(opportunity.probability || 0) }) });
      setOpportunity({ title: '', amount: '', probability: 10, expected_close_date: '' }); await onChanged();
    } catch (err) { setError(err.message); }
  }
  return <>
    <form onSubmit={submit} className="responsive-form-grid" style={formPanel} data-testid="crm-lead-form">
      <FormField label="Student name" value={form.student_name} onChange={value => setForm(row => ({ ...row, student_name: value }))} required />
      <FormField label="Parent / guardian" value={form.parent_name} onChange={value => setForm(row => ({ ...row, parent_name: value }))} />
      <FormField label="Mother's name" value={form.mother_name} onChange={value => setForm(row => ({ ...row, mother_name: value }))} />
      <FormField label="Father's name" value={form.father_name} onChange={value => setForm(row => ({ ...row, father_name: value }))} />
      <FormField label="Phone" value={form.phone} onChange={value => setForm(row => ({ ...row, phone: value }))} />
      <FormField label="Email" type="email" value={form.email} onChange={value => setForm(row => ({ ...row, email: value }))} />
      <FormField label="Class applying" value={form.class_applying} onChange={value => setForm(row => ({ ...row, class_applying: value }))} />
      <FormField label="Source" type="select" value={form.source} onChange={value => setForm(row => ({ ...row, source: value }))}
        options={['walk_in', 'website', 'school_event', 'referral', 'campaign'].map(value => ({ value, label: value.replace('_', ' ') }))} />
      <FormField label="Next follow-up" type="date" value={form.next_follow_up} onChange={value => setForm(row => ({ ...row, next_follow_up: value }))} />
      <FormField label="Estimated value (₹)" type="number" value={form.estimated_value} onChange={value => setForm(row => ({ ...row, estimated_value: value }))} />
      <FormField label="Probability %" type="number" value={form.probability} onChange={value => setForm(row => ({ ...row, probability: value }))} />
      <div style={{ alignSelf: 'end' }}><ActionBtn label="Add lead" type="submit" /></div>
    </form>
    <DataTable headers={['Student', 'Contact', 'Class', 'Age', 'Value', 'Follow-up', 'Stage', 'Open']}
      rows={leads.map(lead => [lead.student_name, lead.phone || lead.email || '-', lead.class_applying || '-',
        `${Math.max(0, Math.floor((Date.now() - new Date(lead.created_at || Date.now()).getTime()) / 86400000))}d`, money(lead.estimated_value_paise), lead.next_follow_up || '-',
        <select aria-label={`Change stage for ${lead.student_name}`} value={lead.status || 'new'} onChange={event => changeStatus(lead, event.target.value)} style={smallSelect}>
          {/* A2: "enrolled" is not on this list. A lead already enrolled still shows it,
              greyed out, because hiding the stage a lead is actually in would be a
              different lie from the one we are fixing. */}
          {PICKABLE_LEAD_STAGES.map(value => <option key={value}>{value}</option>)}
          {!PICKABLE_LEAD_STAGES.includes(lead.status || 'new')
            && <option key={lead.status} disabled>{lead.status}</option>}
        </select>, <button type="button" style={linkButton} onClick={() => setSelectedLeadId(lead.id)}>Activity & opportunity</button>])} emptyMsg="No CRM leads for this entity" />
    {selectedLead && <div className="responsive-form-grid" style={twoPanels} data-testid="crm-detail-workspace">
      <form onSubmit={addActivity} style={formPanel}>
        <h3 style={heading}>Activity · {selectedLead.student_name}</h3>
        <FormField label="Type" type="select" value={activity.activity_type} onChange={value => setActivity(row => ({ ...row, activity_type: value }))} options={['note', 'call', 'email', 'meeting', 'visit', 'follow_up'].map(value => ({ value, label: value }))} />
        <FormField label="Subject" value={activity.subject} onChange={value => setActivity(row => ({ ...row, subject: value }))} required />
        <FormField label="Notes" value={activity.notes} onChange={value => setActivity(row => ({ ...row, notes: value }))} />
        <FormField label="Next follow-up" type="date" value={activity.next_follow_up} onChange={value => setActivity(row => ({ ...row, next_follow_up: value }))} />
        <ActionBtn label="Add activity" type="submit" />
        <div style={note}>{activities.slice(0, 5).map(row => <div key={row.id}>{row.activity_type}: {row.subject}</div>)}</div>
      </form>
      <form onSubmit={addOpportunity} style={formPanel}>
        <h3 style={heading}>Opportunity & conversion</h3>
        <FormField label="Opportunity title" value={opportunity.title} onChange={value => setOpportunity(row => ({ ...row, title: value }))} required />
        <FormField label="Amount (₹)" type="number" value={opportunity.amount} onChange={value => setOpportunity(row => ({ ...row, amount: value }))} required />
        <FormField label="Probability %" type="number" value={opportunity.probability} onChange={value => setOpportunity(row => ({ ...row, probability: value }))} />
        <FormField label="Expected close" type="date" value={opportunity.expected_close_date} onChange={value => setOpportunity(row => ({ ...row, expected_close_date: value }))} />
        {/* A2: the "Application ID" and "Student ID" boxes that stood here are gone.
            They were never sent with the opportunity; their only use was the hand-made
            enrolment this item removes, so they had become two boxes a person could
            type into that did nothing at all. */}
        <ActionBtn label="Add opportunity" type="submit" />
      </form>
    </div>}
    <DataTable headers={['Opportunity', 'Lead', 'Stage', 'Amount', 'Probability', 'Expected close']}
      rows={opportunities.map(row => [row.title, leads.find(lead => lead.id === row.enquiry_id)?.student_name || row.enquiry_id, row.stage, money(row.amount_paise), `${row.probability || 0}%`, row.expected_close_date || '-'])} emptyMsg="No CRM opportunities" />
  </>;
}

function EntitiesPanel({ currentUser, entities, onChanged, setError }) {
  const [form, setForm] = useState({ name: '', code: '', entity_type: 'school', parent_entity_id: '', currency: 'INR' });
  const groups = useMemo(() => entities.filter(item => item.is_group), [entities]);
  async function submit(event) {
    event.preventDefault();
    try { await request('/commercial/entities', { method: 'POST', body: JSON.stringify(form) }); setForm({ name: '', code: '', entity_type: 'school', parent_entity_id: '', currency: 'INR' }); await onChanged(); }
    catch (err) { setError(err.message); }
  }
  async function makeDefault(id) {
    try { await request(`/commercial/entities/${id}/default`, { method: 'PATCH', body: '{}' }); await onChanged(); }
    catch (err) { setError(err.message); }
  }
  return <>
    {currentUser?.role === 'owner' && <form onSubmit={submit} className="responsive-form-grid" style={formPanel}>
      <FormField label="Legal name" value={form.name} onChange={value => setForm(row => ({ ...row, name: value }))} required />
      <FormField label="Code" value={form.code} onChange={value => setForm(row => ({ ...row, code: value.toUpperCase() }))} required />
      <FormField label="Type" type="select" value={form.entity_type} onChange={value => setForm(row => ({ ...row, entity_type: value }))} options={['school', 'trust', 'company', 'group'].map(value => ({ value, label: value }))} />
      <FormField label="Parent group" type="select" value={form.parent_entity_id} onChange={value => setForm(row => ({ ...row, parent_entity_id: value }))} options={[{ value: '', label: 'None' }, ...groups.map(item => ({ value: item.id, label: item.name }))]} />
      <div style={{ alignSelf: 'end' }}><ActionBtn label="Add entity" type="submit" /></div>
    </form>}
    <DataTable headers={['Name', 'Code', 'Type', 'Parent', 'Currency', 'Status', 'Default']}
      rows={entities.map(row => [row.name, row.code, row.entity_type, entities.find(item => item.id === row.parent_entity_id)?.name || '-', row.currency,
        <Badge text={row.is_group ? 'consolidation only' : row.is_active ? 'active' : 'inactive'} color={row.is_group ? 'blue' : 'green'} />,
        row.is_default ? <Badge text="default" color="green" /> : (!row.is_group && currentUser?.role === 'owner' ? <button type="button" style={linkButton} onClick={() => makeDefault(row.id)}>Make default</button> : '-')])} emptyMsg="No legal entities configured" />
  </>;
}

const toolbar = { display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'end', justifyContent: 'space-between', marginBottom: 18 };
const tabs = { display: 'flex', gap: 6, flexWrap: 'wrap' };
const tabButton = { border: '1px solid var(--color-border)', borderRadius: 8, padding: '9px 13px', background: 'var(--color-surface-raised)', color: 'var(--color-text-secondary)', cursor: 'pointer', fontWeight: 600 };
const activeTab = { background: 'var(--accent-primary)', color: '#fff', border: '1px solid var(--accent-primary)' };
const labelStyle = { display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--color-text-secondary)', marginBottom: 5, textTransform: 'uppercase' };
const inputStyle = { width: '100%', minHeight: 40, padding: '8px 10px', border: '1px solid var(--color-border)', borderRadius: 8, background: 'var(--color-surface-raised)', color: 'var(--color-text-primary)' };
const smallSelect = { ...inputStyle, minWidth: 125, minHeight: 34, padding: '5px 7px' };
const stats = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(160px, 100%), 1fr))', gap: 10 };
const formPanel = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(170px, 100%), 1fr))', gap: 10, padding: 14, border: '1px solid var(--color-border)', borderRadius: 10, background: 'var(--color-surface-raised)', marginBottom: 16 };
const twoPanels = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))', gap: 12, alignItems: 'start' };
const heading = { gridColumn: '1 / -1', margin: 0, fontSize: 15, color: 'var(--color-text-primary)' };
const errorStyle = { padding: 12, marginBottom: 12, borderRadius: 8, background: 'rgba(248,113,113,.12)', color: 'var(--tool-hex-f87171)' };
const note = { color: 'var(--color-text-secondary)', fontSize: 12, lineHeight: 1.5, marginTop: 14 };
const linkButton = { border: 0, background: 'transparent', color: 'var(--accent-primary)', cursor: 'pointer', textDecoration: 'underline', padding: 4 };
