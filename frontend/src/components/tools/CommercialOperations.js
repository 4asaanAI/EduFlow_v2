import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useUser } from '../../contexts/UserContext';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ActionBtn, Badge, DataTable, FormField, StatCard, ToolPage } from './ToolPage';

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
const uniqueKey = prefix => `${prefix}-${typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`}`;

export default function CommercialOperations() {
  const { currentUser } = useUser();
  const subRole = currentUser?.sub_category;
  const canCrm = currentUser?.role === 'owner' || ['principal', 'admission', 'receptionist'].includes(subRole);
  const canSummary = currentUser?.role === 'owner' || ['principal', 'accountant'].includes(subRole);
  const canRetail = currentUser?.role === 'owner' || ['principal', 'accountant', 'receptionist'].includes(subRole);
  const requestSeq = useRef(0);
  const [tab, setTab] = useState(canSummary ? 'overview' : canCrm ? 'crm' : 'retail');
  const [entities, setEntities] = useState([]);
  const [entityId, setEntityId] = useState('');
  const [summary, setSummary] = useState(null);
  const [leads, setLeads] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [products, setProducts] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [sales, setSales] = useState([]);
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
        ...(canCrm ? [
          ['leads', request(`/commercial/crm/leads?${query}`)],
          ['opportunities', request(`/commercial/crm/opportunities?${query}`)],
        ] : []),
        ...(canRetail ? [
          ['products', request(`/commercial/products?${query}`)],
          ['shifts', request(`/commercial/pos/shifts?${query}`)],
          ['sales', request(`/commercial/pos/sales?${query}`)],
          ['inventory', request('/campus/inventory/items')],
        ] : []),
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
        if (key === 'opportunities') setOpportunities(data || []);
        if (key === 'products') setProducts(data || []);
        if (key === 'shifts') setShifts(data || []);
        if (key === 'sales') setSales(data || []);
        if (key === 'inventory') setInventory(data || []);
      });
      if (failures.length) setError(failures.join(' '));
    } catch (err) { setError(err.message); }
    finally { if (sequence === requestSeq.current) setLoading(false); }
  }, [canCrm, canRetail, canSummary, entityId]);

  useEffect(() => { loadEntities().catch(err => { setError(err.message); setLoading(false); }); }, [loadEntities]);
  useEffect(() => { loadDomain(); }, [loadDomain]);

  const refresh = async () => { await loadEntities(); await loadDomain(); };
  const selected = entities.find(item => item.id === entityId);
  const openShift = shifts.find(item => item.status === 'open'
    && (currentUser?.role === 'owner' || item.cashier_id === currentUser?.id));
  const total = summary?.totals || {};
  const operatingEntities = entities.filter(item => !item.is_group && item.is_active !== false);
  const availableTabs = [...(canSummary ? ['overview'] : []), ...(canCrm ? ['crm'] : []), ...(canRetail ? ['retail'] : []), 'entities'];

  return <ToolPage title="Commercial Operations" subtitle="Admissions CRM, legal entities and campus retail in one controlled workspace" loading={loading} onRefresh={refresh}>
    {error && <div role="alert" style={errorStyle}>{error}</div>}
    <div style={toolbar}>
      <label style={{ minWidth: 210, flex: '1 1 240px' }}>
        <span style={labelStyle}>Operating legal entity</span>
        <select aria-label="Operating legal entity" value={entityId} onChange={event => setEntityId(event.target.value)} style={inputStyle}>
          {operatingEntities.map(item => <option key={item.id} value={item.id}>{item.name}{item.is_default ? ' (default)' : ''}</option>)}
        </select>
      </label>
      <div role="tablist" aria-label="Commercial operation sections" style={tabs}>
        {availableTabs.map(value => <button key={value} role="tab" aria-selected={tab === value}
          onClick={() => setTab(value)} style={{ ...tabButton, ...(tab === value ? activeTab : {}) }}>{value === 'crm' ? 'CRM' : value[0].toUpperCase() + value.slice(1)}</button>)}
      </div>
    </div>
    {tab === 'overview' && canSummary && <Overview entity={selected} total={total} leads={leads} shifts={shifts} sales={sales} />}
    {tab === 'crm' && <CrmPanel entityId={entityId} leads={leads} opportunities={opportunities} onChanged={loadDomain} setError={setError} />}
    {tab === 'retail' && <RetailPanel entityId={entityId} products={products} inventory={inventory} shifts={shifts}
      openShift={openShift} sales={sales} onChanged={loadDomain} setError={setError} />}
    {tab === 'entities' && <EntitiesPanel currentUser={currentUser} entities={entities} onChanged={refresh} setError={setError} />}
  </ToolPage>;
}

function Overview({ entity, total, leads, shifts, sales }) {
  return <>
    <div style={stats}>
      <StatCard value={entity?.name || 'Not configured'} label="OPERATING ENTITY" color="var(--tool-hex-4f8ff7)" />
      <StatCard value={money(total.net_sales_paise)} label="NET CAMPUS SALES" color="var(--tool-hex-34d399)" />
      <StatCard value={money(total.weighted_pipeline_paise)} label="WEIGHTED PIPELINE" color="var(--tool-hex-a78bfa)" />
      <StatCard value={leads.length} label="CRM LEADS" color="var(--tool-hex-fbbf24)" />
      <StatCard value={shifts.filter(item => item.status === 'open').length} label="OPEN POS SHIFTS" color="var(--tool-hex-f87171)" />
      <StatCard value={sales.length} label="POSTED SALES" color="var(--tool-hex-22d3ee)" />
    </div>
    <p style={note}>Legacy records without a legal-entity field remain readable through the configured default. EduFlow does not rewrite them.</p>
  </>;
}

function CrmPanel({ entityId, leads, opportunities, onChanged, setError }) {
  const emptyLead = { student_name: '', parent_name: '', phone: '', email: '', class_applying: '', source: 'walk_in', next_follow_up: '', estimated_value: '', probability: 0 };
  const [form, setForm] = useState(emptyLead);
  const [selectedLeadId, setSelectedLeadId] = useState('');
  const [activities, setActivities] = useState([]);
  const [activity, setActivity] = useState({ activity_type: 'note', subject: '', notes: '', next_follow_up: '' });
  const [opportunity, setOpportunity] = useState({ title: '', amount: '', probability: 10, expected_close_date: '' });
  const [conversion, setConversion] = useState({ application_id: '', student_id: '' });
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
    if (status === 'enrolled' && (!conversion.application_id || !conversion.student_id)) {
      setSelectedLeadId(lead.id); setError('Link the admission application and student before marking this lead enrolled.'); return;
    }
    try {
      await request(`/commercial/crm/leads/${lead.id}`, { method: 'PATCH', body: JSON.stringify({ status, lost_reason, ...(status === 'enrolled' ? conversion : {}) }) });
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
      rows={leads.map(lead => [lead.student_name, lead.phone || lead.email || '—', lead.class_applying || '—',
        `${Math.max(0, Math.floor((Date.now() - new Date(lead.created_at || Date.now()).getTime()) / 86400000))}d`, money(lead.estimated_value_paise), lead.next_follow_up || '—',
        <select aria-label={`Change stage for ${lead.student_name}`} value={lead.status || 'new'} onChange={event => changeStatus(lead, event.target.value)} style={smallSelect}>
          {['new', 'contacted', 'visit_scheduled', 'visited', 'documents_submitted', 'fee_paid', 'enrolled', 'lost'].map(value => <option key={value}>{value}</option>)}
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
        <FormField label="Application ID" value={conversion.application_id} onChange={value => setConversion(row => ({ ...row, application_id: value }))} />
        <FormField label="Student ID" value={conversion.student_id} onChange={value => setConversion(row => ({ ...row, student_id: value }))} />
        <ActionBtn label="Add opportunity" type="submit" />
      </form>
    </div>}
    <DataTable headers={['Opportunity', 'Lead', 'Stage', 'Amount', 'Probability', 'Expected close']}
      rows={opportunities.map(row => [row.title, leads.find(lead => lead.id === row.enquiry_id)?.student_name || row.enquiry_id, row.stage, money(row.amount_paise), `${row.probability || 0}%`, row.expected_close_date || '—'])} emptyMsg="No CRM opportunities" />
  </>;
}

function RetailPanel({ entityId, products, inventory, shifts, openShift, sales, onChanged, setError }) {
  const [product, setProduct] = useState({ inventory_item_id: '', sku: '', name: '', unit_price: '', tax_rate_percent: 0 });
  const [shift, setShift] = useState({ register_name: 'Campus Counter', opening_cash: 0 });
  const [sale, setSale] = useState({ product_id: '', quantity: 1, customer_name: '' });
  const [cart, setCart] = useState([]);
  const [payments, setPayments] = useState([]);
  const [paymentDraft, setPaymentDraft] = useState({ mode: 'cash', amount: '' });
  const [posting, setPosting] = useState(false);
  const pendingSale = useRef(null);
  const pendingReturn = useRef(null);
  const selectedProduct = products.find(item => item.id === sale.product_id);
  useEffect(() => {
    setProduct(row => ({ ...row, inventory_item_id: row.inventory_item_id || inventory[0]?.id || '' }));
    setSale(row => ({ ...row, product_id: row.product_id || products[0]?.id || '' }));
  }, [inventory, products]);
  const cartTotalPaise = cart.reduce((sum, line) => sum + line.total_paise, 0);
  const paidPaise = payments.reduce((sum, row) => sum + Math.round(Number(row.amount || 0) * 100), 0);
  function addLine() {
    if (!selectedProduct || Number(sale.quantity) <= 0) return;
    const quantity = Number(sale.quantity);
    const total = (selectedProduct.unit_price_paise * quantity)
      + Math.round(selectedProduct.unit_price_paise * quantity * (selectedProduct.tax_rate_bps || 0) / 10000);
    setCart(rows => [...rows, { product_id: selectedProduct.id, name: selectedProduct.name, quantity,
      unit_price: selectedProduct.unit_price_paise / 100, total_paise: total }]);
  }
  function addPayment() {
    if (Number(paymentDraft.amount) <= 0) return;
    setPayments(rows => [...rows, { mode: paymentDraft.mode, amount: Number(paymentDraft.amount) }]);
    setPaymentDraft(row => ({ ...row, amount: '' }));
  }
  async function addProduct(event) {
    event.preventDefault();
    try { await request('/commercial/products', { method: 'POST', body: JSON.stringify({ ...product, entity_id: entityId, unit_price: Number(product.unit_price), tax_rate_percent: Number(product.tax_rate_percent) }) }); await onChanged(); }
    catch (err) { setError(err.message); }
  }
  async function open(event) {
    event.preventDefault();
    try { await request('/commercial/pos/shifts', { method: 'POST', body: JSON.stringify({ ...shift, entity_id: entityId, opening_cash: Number(shift.opening_cash) }) }); await onChanged(); }
    catch (err) { setError(err.message); }
  }
  async function postSale(event) {
    event.preventDefault();
    if (posting || !openShift || !cart.length) return;
    const effectivePayments = payments.length ? payments : [{ mode: 'cash', amount: cartTotalPaise / 100 }];
    const payload = {
        entity_id: entityId, shift_id: openShift.id, customer_type: sale.customer_name ? 'walk_in' : 'walk_in', customer_name: sale.customer_name,
        lines: cart.map(({ product_id, quantity, unit_price }) => ({ product_id, quantity, unit_price })),
        payments: effectivePayments,
      };
    const signature = JSON.stringify(payload);
    if (pendingSale.current?.signature !== signature) pendingSale.current = { signature, key: uniqueKey('sale') };
    setPosting(true);
    try {
      await request('/commercial/pos/sales', { method: 'POST', headers: { 'Idempotency-Key': pendingSale.current.key }, body: signature });
      pendingSale.current = null;
      setCart([]); setPayments([]);
      await onChanged();
    } catch (err) { setError(err.message); }
    finally { setPosting(false); }
  }
  async function close() {
    const counted = window.prompt('Counted cash at the register');
    if (counted === null) return;
    try { await request(`/commercial/pos/shifts/${openShift.id}/close`, { method: 'PATCH', body: JSON.stringify({ counted_cash: Number(counted), variance_reason: 'Counted at close' }) }); await onChanged(); }
    catch (err) { setError(err.message); }
  }
  async function returnOne(row) {
    const line = row.lines?.[0];
    if (posting || !line || !openShift) return;
    const reason = window.prompt('Reason for return');
    if (!reason) return;
    const payload = { entity_id: entityId, shift_id: openShift.id, reason,
      lines: [{ product_id: line.product_id, quantity: 1 }] };
    const signature = JSON.stringify({ sale_id: row.id, ...payload });
    if (pendingReturn.current?.signature !== signature) pendingReturn.current = { signature, key: uniqueKey('return') };
    setPosting(true);
    try {
      await request(`/commercial/pos/sales/${row.id}/returns`, { method: 'POST',
        headers: { 'Idempotency-Key': pendingReturn.current.key }, body: JSON.stringify(payload) });
      pendingReturn.current = null;
      await onChanged();
    } catch (err) { setError(err.message); }
    finally { setPosting(false); }
  }
  return <>
    <div className="responsive-form-grid" style={twoPanels}>
      <form onSubmit={addProduct} style={formPanel}>
        <h3 style={heading}>Retail product</h3>
        <FormField label="Inventory item" type="select" value={product.inventory_item_id} onChange={value => { const item = inventory.find(row => row.id === value); setProduct(row => ({ ...row, inventory_item_id: value, sku: item?.sku || row.sku, name: item?.name || row.name })); }} options={inventory.map(item => ({ value: item.id, label: `${item.name} (${item.on_hand ?? item.quantity ?? 0})` }))} />
        <FormField label="SKU" value={product.sku} onChange={value => setProduct(row => ({ ...row, sku: value }))} required />
        <FormField label="Product name" value={product.name} onChange={value => setProduct(row => ({ ...row, name: value }))} required />
        <FormField label="Price (₹)" type="number" value={product.unit_price} onChange={value => setProduct(row => ({ ...row, unit_price: value }))} required />
        <FormField label="Tax %" type="number" value={product.tax_rate_percent} onChange={value => setProduct(row => ({ ...row, tax_rate_percent: value }))} />
        <ActionBtn label="Add product" type="submit" />
      </form>
      {!openShift ? <form onSubmit={open} style={formPanel}>
        <h3 style={heading}>Open POS shift</h3>
        <FormField label="Register" value={shift.register_name} onChange={value => setShift(row => ({ ...row, register_name: value }))} required />
        <FormField label="Opening cash (₹)" type="number" value={shift.opening_cash} onChange={value => setShift(row => ({ ...row, opening_cash: value }))} />
        <ActionBtn label="Open shift" type="submit" />
      </form> : <form onSubmit={postSale} style={formPanel}>
        <h3 style={heading}>New sale · {openShift.shift_number}</h3>
        <FormField label="Product" type="select" value={sale.product_id} onChange={value => setSale(row => ({ ...row, product_id: value }))} options={products.map(item => ({ value: item.id, label: `${item.name} · ${money(item.unit_price_paise)}` }))} />
        <FormField label="Quantity" type="number" value={sale.quantity} onChange={value => setSale(row => ({ ...row, quantity: value }))} />
        <div style={{ alignSelf: 'end' }}><ActionBtn label="Add line" onClick={addLine} variant="secondary" /></div>
        <FormField label="Customer name" value={sale.customer_name} onChange={value => setSale(row => ({ ...row, customer_name: value }))} />
        <FormField label="Payment mode" type="select" value={paymentDraft.mode} onChange={value => setPaymentDraft(row => ({ ...row, mode: value }))} options={['cash', 'upi', 'card', 'bank_transfer'].map(value => ({ value, label: value }))} />
        <FormField label="Payment amount (₹)" type="number" value={paymentDraft.amount} onChange={value => setPaymentDraft(row => ({ ...row, amount: value }))} />
        <div style={{ alignSelf: 'end' }}><ActionBtn label="Add split payment" onClick={addPayment} variant="secondary" /></div>
        <div style={{ gridColumn: '1 / -1', ...note }} data-testid="pos-sale-composer">
          {cart.map((line, index) => <div key={`${line.product_id}-${index}`}>{line.name} × {line.quantity}: {money(line.total_paise)}</div>)}
          <strong>Total: {money(cartTotalPaise)}</strong> · Payments: {money(paidPaise || cartTotalPaise)}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><ActionBtn label={posting ? 'Posting...' : 'Post sale'} type="submit" disabled={posting} /><ActionBtn label="Close shift" onClick={close} variant="secondary" disabled={posting} /></div>
      </form>}
    </div>
    <DataTable headers={['Receipt', 'Customer', 'Items', 'Total', 'Payment', 'Posted', 'Return']}
      rows={sales.map(row => [row.receipt_number, row.customer_name, row.lines?.length || 0, money(row.total_paise), row.payments?.map(item => item.mode).join(', '), row.created_at?.slice(0, 10),
        <button type="button" disabled={!openShift || posting} onClick={() => returnOne(row)} style={linkButton}>Return one item</button>])} emptyMsg="No campus retail sales" />
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
      rows={entities.map(row => [row.name, row.code, row.entity_type, entities.find(item => item.id === row.parent_entity_id)?.name || '—', row.currency,
        <Badge text={row.is_group ? 'consolidation only' : row.is_active ? 'active' : 'inactive'} color={row.is_group ? 'blue' : 'green'} />,
        row.is_default ? <Badge text="default" color="green" /> : (!row.is_group && currentUser?.role === 'owner' ? <button type="button" style={linkButton} onClick={() => makeDefault(row.id)}>Make default</button> : '—')])} emptyMsg="No legal entities configured" />
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
