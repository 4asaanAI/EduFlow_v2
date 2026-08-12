import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useUser } from '../../contexts/UserContext';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ActionBtn, Badge, DataTable, FormField, ToolPage } from './ToolPage';

async function request(url, options = {}) {
  const response = await apiFetch(url, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Campus operation failed');
  return body;
}

const tomorrow = () => {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  value.setMinutes(0, 0, 0);
  return value.toISOString().slice(0, 16);
};

export function ResourceCalendar() {
  const { currentUser } = useUser();
  const [resources, setResources] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [resourceForm, setResourceForm] = useState({ name: '', resource_type: 'room', capacity: 1, location: '' });
  const [bookingForm, setBookingForm] = useState({ resource_id: '', purpose: '', start_at: tomorrow(), end_at: tomorrow(), attendees: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [resourcesBody, bookingsBody] = await Promise.all([
        request(`${API}/campus/resources`), request(`${API}/campus/resource-bookings`),
      ]);
      setResources(resourcesBody.data || []);
      setBookings(bookingsBody.data || []);
      setBookingForm(form => ({ ...form, resource_id: form.resource_id || resourcesBody.data?.[0]?.id || '' }));
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function createResource(event) {
    event.preventDefault();
    try {
      await request(`${API}/campus/resources`, { method: 'POST', body: JSON.stringify(resourceForm) });
      setResourceForm({ name: '', resource_type: 'room', capacity: 1, location: '' });
      await load();
    } catch (err) { setError(err.message); }
  }

  async function book(event) {
    event.preventDefault();
    try {
      await request(`${API}/campus/resource-bookings`, {
        method: 'POST', body: JSON.stringify({ ...bookingForm, start_at: new Date(bookingForm.start_at).toISOString(), end_at: new Date(bookingForm.end_at).toISOString() }),
      });
      await load();
    } catch (err) { setError(err.message); }
  }

  return <ToolPage title="Room & Resource Calendar" subtitle="Conflict-safe booking for rooms, labs, halls, equipment, and sports spaces" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    <div className="responsive-form-grid" style={twoPanels}>
      {currentUser?.role !== 'teacher' && <form onSubmit={createResource} style={panel}>
        <h3 style={heading}>Add resource</h3>
        <FormField label="Name" value={resourceForm.name} onChange={value => setResourceForm(form => ({ ...form, name: value }))} required />
        <FormField label="Type" type="select" value={resourceForm.resource_type} onChange={value => setResourceForm(form => ({ ...form, resource_type: value }))} options={['room', 'lab', 'hall', 'equipment', 'sports'].map(value => ({ value, label: value }))} />
        <FormField label="Capacity" type="number" value={resourceForm.capacity} onChange={value => setResourceForm(form => ({ ...form, capacity: Number(value) }))} />
        <FormField label="Location" value={resourceForm.location} onChange={value => setResourceForm(form => ({ ...form, location: value }))} />
        <ActionBtn label="Add resource" type="submit" />
      </form>}
      <form onSubmit={book} style={panel}>
        <h3 style={heading}>Book a resource</h3>
        <FormField label="Resource" type="select" value={bookingForm.resource_id} onChange={value => setBookingForm(form => ({ ...form, resource_id: value }))} options={resources.map(item => ({ value: item.id, label: `${item.name} (${item.capacity})` }))} />
        <FormField label="Purpose" value={bookingForm.purpose} onChange={value => setBookingForm(form => ({ ...form, purpose: value }))} required />
        <FormField label="Starts" type="datetime-local" value={bookingForm.start_at} onChange={value => setBookingForm(form => ({ ...form, start_at: value }))} required />
        <FormField label="Ends" type="datetime-local" value={bookingForm.end_at} onChange={value => setBookingForm(form => ({ ...form, end_at: value }))} required />
        <FormField label="Attendees" type="number" value={bookingForm.attendees} onChange={value => setBookingForm(form => ({ ...form, attendees: Number(value) }))} />
        <ActionBtn label="Book resource" type="submit" />
      </form>
    </div>
    <DataTable headers={['Resource', 'Purpose', 'Starts', 'Ends', 'Status']}
      rows={bookings.map(item => [item.resource_name, item.purpose, new Date(item.start_at).toLocaleString(), new Date(item.end_at).toLocaleString(), <Badge text={item.status} color={item.status === 'confirmed' ? 'green' : 'gray'} />])}
      emptyMsg="No resource bookings" />
  </ToolPage>;
}

export function AssetCustody() {
  const [assets, setAssets] = useState([]);
  const [custody, setCustody] = useState([]);
  const [form, setForm] = useState({ asset_id: '', holder_type: 'staff', holder_id: '', condition: 'good' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [assetBody, custodyBody] = await Promise.all([
        request(`${API}/ops/assets`), request(`${API}/campus/asset-custody`),
      ]);
      setAssets(assetBody.data || []); setCustody(custodyBody.data || []);
      setForm(value => ({ ...value, asset_id: value.asset_id || assetBody.data?.[0]?.id || '' }));
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  async function checkout(event) {
    event.preventDefault();
    try {
      await request(`${API}/campus/assets/${encodeURIComponent(form.asset_id)}/checkout`, { method: 'POST', body: JSON.stringify(form) });
      setForm(value => ({ ...value, holder_id: '' })); await load();
    } catch (err) { setError(err.message); }
  }
  async function returnItem(id) {
    try { await request(`${API}/campus/asset-custody/${encodeURIComponent(id)}/return`, { method: 'PATCH', body: JSON.stringify({ condition: 'good' }) }); await load(); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="Asset Custody" subtitle="Issue, return, and trace responsibility for school assets" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    <form onSubmit={checkout} className="responsive-form-grid" style={horizontalForm}>
      <FormField label="Asset" type="select" value={form.asset_id} onChange={value => setForm(item => ({ ...item, asset_id: value }))} options={assets.filter(item => item.custody_status !== 'checked_out').map(item => ({ value: item.id, label: item.name }))} />
      <FormField label="Holder type" type="select" value={form.holder_type} onChange={value => setForm(item => ({ ...item, holder_type: value }))} options={['staff', 'student', 'department'].map(value => ({ value, label: value }))} />
      <FormField label="Holder ID" value={form.holder_id} onChange={value => setForm(item => ({ ...item, holder_id: value }))} required />
      <div style={{ alignSelf: 'end' }}><ActionBtn label="Check out" type="submit" /></div>
    </form>
    <DataTable headers={['Asset', 'Holder', 'Checked out', 'Status', 'Action']}
      rows={custody.map(item => [item.asset_name, `${item.holder_type}: ${item.holder_id}`, item.checked_out_at?.slice(0, 10), <Badge text={item.status} color={item.status === 'returned' ? 'green' : 'yellow'} />, item.status === 'checked_out' ? <ActionBtn label="Return" onClick={() => returnItem(item.id)} /> : 'Completed'])}
      emptyMsg="No custody records" />
  </ToolPage>;
}

export function ProcurementInventory() {
  const [items, setItems] = useState([]);
  const [requisitions, setRequisitions] = useState([]);
  const [orders, setOrders] = useState([]);
  const [itemForm, setItemForm] = useState({ sku: '', name: '', opening_quantity: 0, reorder_level: 0, unit: 'each' });
  const [requestForm, setRequestForm] = useState({ purpose: '', item_id: '', description: '', quantity: 1, estimated_unit_cost: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [itemBody, requestBody, orderBody] = await Promise.all([
        request(`${API}/campus/inventory/items`), request(`${API}/campus/procurement/requisitions`), request(`${API}/campus/procurement/orders`),
      ]);
      setItems(itemBody.data || []); setRequisitions(requestBody.data || []); setOrders(orderBody.data || []);
      setRequestForm(form => ({ ...form, item_id: form.item_id || itemBody.data?.[0]?.id || '' }));
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function addItem(event) {
    event.preventDefault();
    try { await request(`${API}/campus/inventory/items`, { method: 'POST', body: JSON.stringify(itemForm) }); setItemForm({ sku: '', name: '', opening_quantity: 0, reorder_level: 0, unit: 'each' }); await load(); }
    catch (err) { setError(err.message); }
  }
  async function addRequisition(event) {
    event.preventDefault();
    try {
      await request(`${API}/campus/procurement/requisitions`, { method: 'POST', body: JSON.stringify({
        purpose: requestForm.purpose, lines: [{ item_id: requestForm.item_id || null, description: requestForm.description, quantity: Number(requestForm.quantity), estimated_unit_cost: Number(requestForm.estimated_unit_cost) }],
      }) });
      setRequestForm(form => ({ ...form, purpose: '', description: '', quantity: 1, estimated_unit_cost: 0 })); await load();
    } catch (err) { setError(err.message); }
  }
  async function decision(id, value) {
    const reason = value === 'reject' ? window.prompt('Reason for rejection') : '';
    if (value === 'reject' && !reason) return;
    try { await request(`${API}/campus/procurement/requisitions/${id}/decision`, { method: 'PATCH', body: JSON.stringify({ decision: value, reason }) }); await load(); }
    catch (err) { setError(err.message); }
  }
  async function order(id) {
    const supplier = window.prompt('Supplier name'); if (!supplier) return;
    try { await request(`${API}/campus/procurement/requisitions/${id}/order`, { method: 'POST', body: JSON.stringify({ supplier }) }); await load(); }
    catch (err) { setError(err.message); }
  }
  async function receive(id) {
    try { await request(`${API}/campus/procurement/orders/${id}/receive`, { method: 'PATCH' }); await load(); }
    catch (err) { setError(err.message); }
  }
  async function stock(item, movement_type) {
    const raw = window.prompt(`${movement_type === 'issue' ? 'Issue' : 'Receive'} quantity for ${item.name}`);
    if (!raw) return;
    try { await request(`${API}/campus/inventory/items/${item.id}/movements`, { method: 'POST', body: JSON.stringify({ movement_type, quantity: Number(raw), notes: 'Panel adjustment' }) }); await load(); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="Procurement & Inventory" subtitle="Requisitions, approvals, purchase orders, receipts, and auditable stock" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    <div className="responsive-form-grid" style={twoPanels}>
      <form onSubmit={addItem} style={panel}><h3 style={heading}>New inventory item</h3>
        <FormField label="SKU" value={itemForm.sku} onChange={value => setItemForm(form => ({ ...form, sku: value }))} required />
        <FormField label="Name" value={itemForm.name} onChange={value => setItemForm(form => ({ ...form, name: value }))} required />
        <FormField label="Opening quantity" type="number" value={itemForm.opening_quantity} onChange={value => setItemForm(form => ({ ...form, opening_quantity: Number(value) }))} />
        <FormField label="Reorder level" type="number" value={itemForm.reorder_level} onChange={value => setItemForm(form => ({ ...form, reorder_level: Number(value) }))} />
        <ActionBtn label="Add item" type="submit" />
      </form>
      <form onSubmit={addRequisition} style={panel}><h3 style={heading}>Purchase requisition</h3>
        <FormField label="Purpose" value={requestForm.purpose} onChange={value => setRequestForm(form => ({ ...form, purpose: value }))} required />
        <FormField label="Existing item" type="select" value={requestForm.item_id} onChange={value => setRequestForm(form => ({ ...form, item_id: value, description: items.find(item => item.id === value)?.name || form.description }))} options={[{ value: '', label: 'Uncatalogued item' }, ...items.map(item => ({ value: item.id, label: item.name }))]} />
        <FormField label="Description" value={requestForm.description} onChange={value => setRequestForm(form => ({ ...form, description: value }))} required />
        <FormField label="Quantity" type="number" value={requestForm.quantity} onChange={value => setRequestForm(form => ({ ...form, quantity: Number(value) }))} />
        <FormField label="Estimated unit cost" type="number" value={requestForm.estimated_unit_cost} onChange={value => setRequestForm(form => ({ ...form, estimated_unit_cost: Number(value) }))} />
        <ActionBtn label="Submit requisition" type="submit" />
      </form>
    </div>
    <DataTable title="Inventory" headers={['SKU', 'Item', 'On hand', 'Reorder', 'Actions']}
      rows={items.map(item => [item.sku, item.name, item.on_hand, item.needs_reorder ? <Badge text="Reorder" color="red" /> : <Badge text="Healthy" color="green" />, <div style={{ display: 'flex', gap: 6 }}><ActionBtn label="Receive" onClick={() => stock(item, 'receipt')} /><ActionBtn label="Issue" variant="secondary" onClick={() => stock(item, 'issue')} /></div>])} emptyMsg="No inventory items" />
    <DataTable title="Requisitions" headers={['Purpose', 'Total', 'Status', 'Action']}
      rows={requisitions.map(item => [item.purpose, `Rs ${Number(item.estimated_total || 0).toLocaleString('en-IN')}`, <Badge text={item.status} color={item.status === 'approved' || item.status === 'received' ? 'green' : item.status === 'rejected' ? 'red' : 'yellow'} />, item.status === 'submitted' ? <div style={{ display: 'flex', gap: 6 }}><ActionBtn label="Approve" onClick={() => decision(item.id, 'approve')} /><ActionBtn label="Reject" variant="danger" onClick={() => decision(item.id, 'reject')} /></div> : item.status === 'approved' ? <ActionBtn label="Create order" onClick={() => order(item.id)} /> : '-'])} emptyMsg="No requisitions" />
    <DataTable title="Purchase orders" headers={['Supplier', 'Total', 'Status', 'Action']}
      rows={orders.map(item => [item.supplier, `Rs ${Number(item.total || 0).toLocaleString('en-IN')}`, <Badge text={item.status} color={item.status === 'received' ? 'green' : 'yellow'} />, item.status === 'ordered' ? <ActionBtn label="Receive" onClick={() => receive(item.id)} /> : 'Completed'])} emptyMsg="No purchase orders" />
  </ToolPage>;
}

export function LibraryCirculation() {
  const { currentUser } = useUser();
  const manager = currentUser?.role === 'owner' || currentUser?.role === 'admin';
  const [titles, setTitles] = useState([]);
  const [loans, setLoans] = useState([]);
  const [titleForm, setTitleForm] = useState({ accession_number: '', title: '', author: '', copies: 1 });
  const [issueForm, setIssueForm] = useState({ title_id: '', borrower_type: 'student', borrower_id: '', due_at: tomorrow() });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [titleBody, loanBody] = await Promise.all([request(`${API}/campus/library/titles`), request(`${API}/campus/library/loans`)]);
      setTitles(titleBody.data || []); setLoans(loanBody.data || []);
      setIssueForm(form => ({ ...form, title_id: form.title_id || titleBody.data?.[0]?.id || '' }));
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const availableTitles = useMemo(() => titles.filter(item => Number(item.copies_available || 0) > 0), [titles]);
  async function addTitle(event) {
    event.preventDefault();
    try { await request(`${API}/campus/library/titles`, { method: 'POST', body: JSON.stringify(titleForm) }); setTitleForm({ accession_number: '', title: '', author: '', copies: 1 }); await load(); }
    catch (err) { setError(err.message); }
  }
  async function issue(event) {
    event.preventDefault();
    try { await request(`${API}/campus/library/titles/${issueForm.title_id}/issue`, { method: 'POST', body: JSON.stringify({ ...issueForm, due_at: new Date(issueForm.due_at).toISOString() }) }); setIssueForm(form => ({ ...form, borrower_id: '' })); await load(); }
    catch (err) { setError(err.message); }
  }
  async function returnLoan(id) {
    try { await request(`${API}/campus/library/loans/${id}/return`, { method: 'PATCH', body: JSON.stringify({ daily_fine: 1 }) }); await load(); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="Library Circulation" subtitle="Catalog availability, issue, return, renewal, and overdue visibility" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    {manager && <div className="responsive-form-grid" style={twoPanels}>
      <form onSubmit={addTitle} style={panel}><h3 style={heading}>Add title</h3>
        <FormField label="Accession number" value={titleForm.accession_number} onChange={value => setTitleForm(form => ({ ...form, accession_number: value }))} required />
        <FormField label="Title" value={titleForm.title} onChange={value => setTitleForm(form => ({ ...form, title: value }))} required />
        <FormField label="Author" value={titleForm.author} onChange={value => setTitleForm(form => ({ ...form, author: value }))} />
        <FormField label="Copies" type="number" value={titleForm.copies} onChange={value => setTitleForm(form => ({ ...form, copies: Number(value) }))} />
        <ActionBtn label="Add title" type="submit" />
      </form>
      <form onSubmit={issue} style={panel}><h3 style={heading}>Issue book</h3>
        <FormField label="Title" type="select" value={issueForm.title_id} onChange={value => setIssueForm(form => ({ ...form, title_id: value }))} options={availableTitles.map(item => ({ value: item.id, label: `${item.title} (${item.copies_available})` }))} />
        <FormField label="Borrower type" type="select" value={issueForm.borrower_type} onChange={value => setIssueForm(form => ({ ...form, borrower_type: value }))} options={[{ value: 'student', label: 'Student' }, { value: 'staff', label: 'Staff' }]} />
        <FormField label="Borrower ID" value={issueForm.borrower_id} onChange={value => setIssueForm(form => ({ ...form, borrower_id: value }))} required />
        <FormField label="Due" type="datetime-local" value={issueForm.due_at} onChange={value => setIssueForm(form => ({ ...form, due_at: value }))} required />
        <ActionBtn label="Issue" type="submit" />
      </form>
    </div>}
    <DataTable title="Catalog" headers={['Accession', 'Title', 'Author', 'Available']}
      rows={titles.map(item => [item.accession_number, item.title, item.author || '-', `${item.copies_available}/${item.copies_total}`])} emptyMsg="No library titles" />
    <DataTable title={manager ? 'Circulation' : 'My loans'} headers={['Title', 'Issued', 'Due', 'Status', 'Action']}
      rows={loans.map(item => [item.title, item.issued_at?.slice(0, 10), item.due_at?.slice(0, 10), <Badge text={item.status} color={item.status === 'returned' ? 'green' : 'yellow'} />, manager && item.status === 'issued' ? <ActionBtn label="Return" onClick={() => returnLoan(item.id)} /> : '-'])} emptyMsg="No library loans" />
  </ToolPage>;
}

function ErrorText({ text }) { return <div role="alert" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 12 }}>{text}</div>; }
const panel = { background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14 };
const heading = { color: 'var(--c-text)', fontSize: 13, margin: '0 0 12px' };
const twoPanels = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 12, marginBottom: 16 };
const horizontalForm = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(170px, 100%), 1fr))', gap: 10, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14, marginBottom: 16 };
