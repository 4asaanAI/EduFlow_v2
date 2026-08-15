/**
 * Approvals - one screen for every approval on the platform. 2026-08-15.
 *
 * **Why this exists.** R3-2 gave the transport head things he must ask permission for,
 * and then a check found there was no screen anywhere for the school's owner or the
 * principal to approve or reject anything. `getApprovalRequests` and
 * `decideApprovalRequest` sat in `lib/api.js` and nothing called them. The platform
 * could ask for permission and could not receive it.
 *
 * **This file names no kind of approval.** The kinds, who decides each one, how many
 * steps it has and what agreeing to it actually does all come from the server's
 * registry. So a seventh kind of approval appears here, with the right words on it, the
 * day somebody adds it there. That was Abhimanyu's explicit requirement.
 *
 * **THREE THINGS HERE ARE DELIBERATE AND LOOK LIKE OMISSIONS.**
 *
 * 1. **There is no Flo panel inside the conversation, and there must never be one**
 *    (decision 29). Each person has Flo privately, on their own screen, inside their
 *    own profile. Aman's Flo sees far more than Chaman's, so an answer printed into the
 *    shared transcript would be built on Aman's access and read in front of somebody
 *    who does not hold it. The permission table would be correct and the platform would
 *    leak anyway, through the transcript.
 *
 * 2. **Every approval is decided one at a time, and there is no control for doing
 *    several at once.** That was deliberately not taken from LayaaOS and it is at odds
 *    with decision 28: a request can carry out the thing it asks for, so agreeing to one
 *    deletes a bus route or commits real money. There is a test that fails if such a
 *    control appears, and it works by reading this file, so keep the wording clear of
 *    the phrases it looks for rather than weakening the test.
 *
 * 3. **There is no delete anywhere.** A decided approval closes and stays readable for
 *    ever, refusals included. The reasoning behind a refusal is often the most useful
 *    thing in the whole thread.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, Check, Clock, Inbox, Paperclip, Plus, Send, UserPlus, X,
} from 'lucide-react';
import {
  addApprovalParticipant,
  createApprovalRequest,
  decideApproval,
  getApproval,
  getApprovalKinds,
  getApprovalPeople,
  getApprovalsIRaised,
  getApprovalsWaitingOnMe,
  getGeneratedFileLink,
  replyToApproval,
  reopenApproval,
  uploadEntityFile,
} from '../../lib/api';
import { Button, Card, EmptyState, Field, Pill, inputStyle } from '../ui/primitives';

const WAITING = 'waiting';
const RAISED = 'raised';

function formatWhen(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

/** How long it has been sitting there, in words rather than a number of hours. */
function waitedFor(hours) {
  if (hours === null || hours === undefined) return '';
  if (hours < 1) return 'just now';
  if (hours < 24) return `${Math.round(hours)} hours ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? 'yesterday' : `${days} days ago`;
}

export default function ApprovalsQueue() {
  const [tab, setTab] = useState(WAITING);
  const [kinds, setKinds] = useState([]);
  const [kindFilter, setKindFilter] = useState('');
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openCard, setOpenCard] = useState(null);
  const [raising, setRaising] = useState(false);

  // Which kinds this person may ASK for from this screen. The server answers it, per
  // kind, so the button can never be offered to somebody the route would refuse, and a
  // seventh kind that declares itself raisable gets the control with no change here.
  const raisableKinds = kinds.filter((k) => k.may_raise);

  useEffect(() => {
    let alive = true;
    getApprovalKinds()
      .then((res) => { if (alive && res.success) setKinds(res.data || []); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = kindFilter ? { kind: kindFilter } : {};
      const res = tab === WAITING
        ? await getApprovalsWaitingOnMe(params)
        : await getApprovalsIRaised(params);
      if (res.success) {
        setRows(res.data || []);
        setMeta(res.meta || {});
      } else {
        setError(res.detail || 'We could not load your approvals.');
      }
    } catch (err) {
      setError(err.message || 'We could not load your approvals.');
    }
    setLoading(false);
  }, [tab, kindFilter]);

  useEffect(() => { load(); }, [load]);

  const overdueCount = meta.overdue || 0;

  return (
    <div style={{ padding: 16 }} data-testid="approvals-queue">
      <h2 style={{ margin: '0 0 4px' }}>Approvals</h2>
      <p style={{ margin: '0 0 16px', opacity: 0.75 }}>
        Everything that needs a decision, of every kind, in one place.
      </p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <Button
          variant={tab === WAITING ? 'primary' : 'ghost'}
          onClick={() => setTab(WAITING)}
          data-testid="tab-waiting"
        >
          Waiting on you
        </Button>
        <Button
          variant={tab === RAISED ? 'primary' : 'ghost'}
          onClick={() => setTab(RAISED)}
          data-testid="tab-raised"
        >
          You asked for
        </Button>
        {/*
          Until this, a person could only ANSWER a request and never start one. That is
          the same shape of gap the whole screen was built to close: the platform could
          receive permission and, for a general request, nobody could ask for it except
          through Flo. Abhimanyu's own example, the accountant head raising a salary
          approval, had no button anywhere.

          The control appears only when the server says this person may raise something,
          which is why the school's owner does not see it: he approves, he does not ask.
        */}
        {raisableKinds.length > 0 && (
          <Button onClick={() => setRaising(true)} data-testid="raise-request">
            <Plus size={14} /> Ask for something
          </Button>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label htmlFor="approval-kind" style={{ marginRight: 8 }}>Kind</label>
        <select
          id="approval-kind"
          style={{ ...inputStyle, width: 'auto' }}
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
        >
          <option value="">Every kind</option>
          {kinds.map((k) => (
            <option key={k.kind} value={k.kind}>{k.label}</option>
          ))}
        </select>
      </div>

      {/* Decision 28: overdue is SHOWN and nothing is ever decided automatically. */}
      {tab === WAITING && overdueCount > 0 && (
        <div style={{ marginBottom: 12 }} data-testid="overdue-banner">
          <Pill tone="yellow" icon={AlertTriangle}>
            {overdueCount === 1
              ? '1 of these has been waiting a long time'
              : `${overdueCount} of these have been waiting a long time`}
          </Pill>
        </div>
      )}

      {error && <p style={{ color: 'crimson' }} role="alert">{error}</p>}
      {loading && <p>Loading your approvals...</p>}

      {!loading && !error && rows.length === 0 && (
        <EmptyState
          icon={Inbox}
          title={tab === WAITING ? 'Nothing is waiting on you' : 'You have not asked for anything'}
          message={tab === WAITING
            ? 'When somebody needs your agreement, it will appear here.'
            : 'Anything you ask permission for will appear here, with what happened to it.'}
        />
      )}

      {!loading && rows.map((card) => (
        <ApprovalRow
          key={`${card.kind}:${card.id}`}
          card={card}
          onOpen={() => setOpenCard(card)}
        />
      ))}

      {openCard && (
        <ApprovalDetail
          card={openCard}
          onClose={() => setOpenCard(null)}
          onChanged={() => { setOpenCard(null); load(); }}
        />
      )}

      {raising && (
        <RaiseRequest
          kinds={raisableKinds}
          onClose={() => setRaising(false)}
          onRaised={() => { setRaising(false); setTab(RAISED); load(); }}
        />
      )}
    </div>
  );
}

/**
 * Ask for something. The other half of this screen.
 *
 * **Only the general kind is raisable here, and that is deliberate rather than an
 * omission.** A certificate is asked for on the certificates screen, where the child and
 * the type of certificate are chosen; leave is asked for on the leave screen. Offering
 * those here would be a SECOND way to create the same record, and two ways to create one
 * thing is how the two drift apart and start disagreeing.
 *
 * The kinds come from the server, so this file still names none of them.
 *
 * **One honest limit, written down rather than left to be discovered.** There is exactly
 * one route for raising a request today, the general one, so if a seventh kind ever
 * declares itself raisable it needs its own create route and a line here to reach it.
 * The picker below only appears when the server offers more than one, so nothing today
 * can be sent to the wrong place.
 */
function RaiseRequest({ kinds, onClose, onRaised }) {
  const [kind, setKind] = useState(kinds[0] ? kinds[0].kind : '');
  const [form, setForm] = useState({
    title: '', description: '', estimated_impact: '', note: '', routing: 'owner_and_principal',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const set = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const submit = async () => {
    // The route insists on all five. Saying so here means the person is told which box
    // is empty before anything is sent, rather than getting one refusal for the lot.
    const missing = ['title', 'description', 'estimated_impact', 'note']
      .filter((field) => !form[field].trim());
    if (missing.length > 0) {
      setError('Every box needs filling in before this can be sent.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await createApprovalRequest({
        title: form.title.trim(),
        description: form.description.trim(),
        estimated_impact: form.estimated_impact.trim(),
        note: form.note.trim(),
        routing: form.routing,
      });
      if (res.success) onRaised();
      else setError(res.detail || 'That request was not sent.');
    } catch (err) {
      setError(err.message || 'That request was not sent.');
    }
    setBusy(false);
  };

  return (
    <div
      role="dialog"
      aria-label="Ask for something"
      data-testid="raise-request-form"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 60,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <Card style={{ maxWidth: 620, width: '100%', maxHeight: '90vh', overflowY: 'auto', padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 8 }}>
          <h3 style={{ margin: '0 0 4px' }}>Ask for something</h3>
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            <X size={16} />
          </Button>
        </div>

        {error && <p style={{ color: 'crimson' }} role="alert">{error}</p>}

        {kinds.length > 1 && (
          <Field label="What kind" htmlFor="raise-kind">
            <select
              id="raise-kind"
              style={inputStyle}
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {kinds.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
            </select>
          </Field>
        )}

        <Field label="What are you asking for" htmlFor="raise-title">
          <input
            id="raise-title"
            style={inputStyle}
            value={form.title}
            onChange={set('title')}
            placeholder="A short line, as it will appear in their list"
          />
        </Field>

        <Field label="Why" htmlFor="raise-description">
          <textarea
            id="raise-description"
            style={{ ...inputStyle, minHeight: 70 }}
            value={form.description}
            onChange={set('description')}
            placeholder="What this is for, in enough detail for somebody to decide"
          />
        </Field>

        <Field
          label="What it costs or changes"
          htmlFor="raise-impact"
          hint="Money, time, or who it affects. This is the line an approver reads first."
        >
          <input
            id="raise-impact"
            style={inputStyle}
            value={form.estimated_impact}
            onChange={set('estimated_impact')}
          />
        </Field>

        <Field label="Anything else they should know" htmlFor="raise-note">
          <textarea
            id="raise-note"
            style={{ ...inputStyle, minHeight: 50 }}
            value={form.note}
            onChange={set('note')}
          />
        </Field>

        {/*
          Who it goes to. The wording says what each choice MEANS rather than naming the
          setting, because "owner_and_principal" tells a person nothing about how long
          they will be waiting or who can unblock them.
        */}
        <Field label="Who should decide it" htmlFor="raise-routing">
          <select
            id="raise-routing"
            style={inputStyle}
            value={form.routing}
            onChange={set('routing')}
          >
            <option value="owner_and_principal">
              Either the school&apos;s owner or the principal, whoever gets to it first
            </option>
            <option value="owner_only">The school&apos;s owner only</option>
          </select>
        </Field>

        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <Button onClick={submit} disabled={busy} data-testid="send-request">
            <Send size={14} /> Send it
          </Button>
          <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        </div>
        <p style={{ fontSize: 12, opacity: 0.7, margin: '8px 0 0' }}>
          It will appear under &quot;You asked for&quot;, with whatever happens to it.
        </p>
      </Card>
    </div>
  );
}

function ApprovalRow({ card, onOpen }) {
  return (
    <Card style={{ marginBottom: 10, padding: 12 }} data-testid="approval-row">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Pill tone="blue">{card.kind_label}</Pill>
        {card.overdue && (
          <Pill tone="yellow" icon={Clock} data-testid="overdue-pill">Waiting a long time</Pill>
        )}
        {!card.is_pending && (
          <Pill tone={card.status === 'rejected' ? 'red' : 'green'}>
            {card.status === 'rejected' ? 'Refused' : 'Decided'}
          </Pill>
        )}
      </div>
      <h3 style={{ margin: '8px 0 4px' }}>{card.title}</h3>
      {card.detail && <p style={{ margin: '0 0 6px', opacity: 0.8 }}>{card.detail}</p>}
      <p style={{ margin: '0 0 8px', fontSize: 13, opacity: 0.7 }}>
        {card.step_label}
        {card.hours_waiting !== null && card.hours_waiting !== undefined
          ? ` · raised ${waitedFor(card.hours_waiting)}`
          : ''}
      </p>

      {/*
        R3-2's rule, carried onto the shared screen: say out loud when agreeing to
        something CARRIES IT OUT. Without it the card reads like every other request and
        a person would press Approve believing they were recording an opinion.
      */}
      {card.carries_out_the_action && (
        <p
          data-testid="carries-out-the-action"
          style={{
            margin: '0 0 8px', padding: 8, borderRadius: 6,
            background: 'rgba(234,179,8,0.12)', fontSize: 13,
          }}
        >
          {card.what_approving_does}
        </p>
      )}

      <Button variant="ghost" onClick={onOpen} data-testid="open-approval">
        Open
      </Button>
    </Card>
  );
}

/**
 * One attached file, as something a person can actually open.
 *
 * Before this, an attachment was drawn as "2 attached" and there was no way to read
 * either of them. A count is not a document: the accountant head sitting in a repair-cost
 * conversation precisely because he pays it could see that a quote existed and could not
 * open it.
 *
 * **The link is minted when it is clicked, never held.** A stored link goes stale and
 * fails later with a signature error, which reads to the person like the file being gone.
 * A fresh one cannot be stale. A file whose record has vanished says so rather than
 * offering a button that fails.
 */
function Attachment({ file }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (file.missing) {
    return (
      <div style={{ opacity: 0.7 }} data-testid="attachment-missing">
        <Paperclip size={12} /> {file.file_name}
      </div>
    );
  }

  const open = async () => {
    setBusy(true);
    setError('');
    try {
      const link = await getGeneratedFileLink(file.id);
      const url = (link.data && link.data.download_url) || link.download_url;
      if (url) window.open(url, '_blank', 'noopener,noreferrer');
      else setError('That file could not be opened.');
    } catch (err) {
      setError(err.message || 'That file could not be opened.');
    }
    setBusy(false);
  };

  return (
    <div>
      <Button variant="ghost" onClick={open} disabled={busy} data-testid="open-attachment">
        <Paperclip size={12} /> {file.file_name}
        {file.file_size_kb ? ` (${Math.round(file.file_size_kb)} KB)` : ''}
      </Button>
      {error && <span style={{ color: 'crimson' }} role="alert">{error}</span>}
    </div>
  );
}

/**
 * Choose a colleague BY NAME, by typing part of it.
 *
 * Two faults in one control before this. It asked for an account id, which is a string
 * nobody at the school knows or could look up, so the control was there and could not be
 * used. And a plain drop-down of ninety-odd colleagues only matches the first letter you
 * press, so finding somebody means scrolling a list you cannot search.
 *
 * The id is still what the server is sent. It simply never appears on screen and nobody
 * ever types it.
 *
 * **The count of what is being shown is always visible**, which is the standing rule from
 * the tables release: a list narrowed to three matches out of ninety must not read like a
 * school with three staff.
 */
function PeoplePicker({ people, value, onChange }) {
  const [query, setQuery] = useState('');
  const chosen = people.find((p) => p.id === value);
  const needle = query.trim().toLowerCase();
  const matches = needle
    ? people.filter((p) => `${p.name} ${p.job || ''}`.toLowerCase().includes(needle))
    : people;

  if (chosen) {
    return (
      <div data-testid="person-chosen" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span>{chosen.name}{chosen.job ? ` (${chosen.job})` : ''}</span>
        <Button variant="ghost" onClick={() => { onChange(''); setQuery(''); }}>
          Choose somebody else
        </Button>
      </div>
    );
  }

  return (
    <div data-testid="person-picklist">
      <input
        aria-label="Who to bring in"
        style={inputStyle}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Start typing a colleague's name"
      />
      <p style={{ fontSize: 12, opacity: 0.7, margin: '4px 0' }} data-testid="people-count">
        {needle
          ? `${matches.length} of ${people.length} colleagues match`
          : `${people.length} colleagues`}
      </p>
      {needle && matches.length === 0 && (
        <p style={{ fontSize: 13 }} data-testid="no-people-match">
          Nobody by that name. Only colleagues who can sign in are listed.
        </p>
      )}
      <div style={{ maxHeight: 180, overflowY: 'auto' }}>
        {matches.map((person) => (
          <div key={person.id}>
            <Button
              variant="ghost"
              disabled={person.already_in}
              onClick={() => onChange(person.id)}
              data-testid="person-option"
            >
              {person.name}
              {person.job ? ` (${person.job})` : ''}
              {person.already_in ? ' - already in this conversation' : ''}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function ApprovalDetail({ card, onClose, onChanged }) {
  const [full, setFull] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');
  const [reply, setReply] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [adding, setAdding] = useState(false);
  const [newPerson, setNewPerson] = useState('');
  const [shareHistory, setShareHistory] = useState(true);
  const [people, setPeople] = useState([]);
  const [peopleError, setPeopleError] = useState('');

  const refresh = useCallback(async () => {
    setError('');
    try {
      const res = await getApproval(card.kind, card.id);
      if (res.success) setFull(res.data);
      else setError(res.detail || 'We could not open this approval.');
    } catch (err) {
      setError(err.message || 'We could not open this approval.');
    }
  }, [card.kind, card.id]);

  useEffect(() => { refresh(); }, [refresh]);

  const decide = async (decision) => {
    // Every one of the six already insisted on a reason for a refusal. Saying so here
    // rather than letting the server refuse means the person is told before they have
    // typed anything else.
    if (decision === 'reject' && !reason.trim()) {
      setError('Say why it was refused, so the person knows what to fix.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await decideApproval(card.kind, card.id, { decision, reason: reason.trim() });
      if (res.success) onChanged();
      else setError(res.detail || 'That decision was not recorded.');
    } catch (err) {
      setError(err.message || 'That decision was not recorded.');
    }
    setBusy(false);
  };

  const send = async () => {
    if (!reply.trim() && attachments.length === 0) return;
    setBusy(true);
    setError('');
    try {
      const res = await replyToApproval(card.kind, card.id, {
        body: reply.trim(),
        attachments: attachments.map((a) => a.id),
      });
      if (res.success) {
        setReply('');
        setAttachments([]);
        refresh();
      } else {
        setError(res.detail || 'Your reply was not sent.');
      }
    } catch (err) {
      setError(err.message || 'Your reply was not sent.');
    }
    setBusy(false);
  };

  const attach = async (file) => {
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      // The ordinary upload door, so a quote or a bill gets the ordinary rules: the
      // same allowed file types, the same size ceiling, the same check that the
      // contents match the extension, and the same private storage. There is
      // deliberately no second way to put a file into the school's storage.
      const res = await uploadEntityFile(file, 'approval_attachment', `${card.kind}:${card.id}`);
      if (res.success) setAttachments((prev) => [...prev, res.data]);
      else setError(res.detail || 'That file was not attached.');
    } catch (err) {
      setError(err.message || 'That file was not attached.');
    }
    setBusy(false);
  };

  // Fetched when the control is opened rather than with the page, because most people
  // reading an approval never bring anybody in.
  const openAddPerson = async () => {
    setAdding(true);
    setPeopleError('');
    try {
      const res = await getApprovalPeople(card.kind, card.id);
      if (res.success) setPeople(res.data || []);
      else setPeopleError(res.detail || 'We could not load your colleagues.');
    } catch (err) {
      setPeopleError(err.message || 'We could not load your colleagues.');
    }
  };

  const addPerson = async () => {
    if (!newPerson.trim()) return;
    setBusy(true);
    setError('');
    try {
      const res = await addApprovalParticipant(card.kind, card.id, {
        user_id: newPerson.trim(), share_history: shareHistory,
      });
      if (res.success) { setNewPerson(''); setAdding(false); refresh(); }
      else setError(res.detail || 'That person was not added.');
    } catch (err) {
      setError(err.message || 'That person was not added.');
    }
    setBusy(false);
  };

  const reopen = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await reopenApproval(card.kind, card.id, { reason: reason.trim() });
      if (res.success) refresh();
      else setError(res.detail || 'This could not be re-opened.');
    } catch (err) {
      setError(err.message || 'This could not be re-opened.');
    }
    setBusy(false);
  };

  return (
    <div
      role="dialog"
      aria-label={card.title}
      data-testid="approval-detail"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 60,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <Card style={{ maxWidth: 720, width: '100%', maxHeight: '90vh', overflowY: 'auto', padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 8 }}>
          <div>
            <Pill tone="blue">{card.kind_label}</Pill>
            <h3 style={{ margin: '8px 0 4px' }}>{card.title}</h3>
          </div>
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            <X size={16} />
          </Button>
        </div>

        {error && <p style={{ color: 'crimson' }} role="alert">{error}</p>}
        {!full && !error && <p>Loading...</p>}

        {full && (
          <>
            {full.detail && <p style={{ opacity: 0.85 }}>{full.detail}</p>}
            <p style={{ fontSize: 13, opacity: 0.7 }}>
              {full.step_label} {full.who_decides ? `· ${full.who_decides}` : ''}
            </p>

            {full.carries_out_the_action && (
              <p
                data-testid="detail-carries-out"
                style={{
                  padding: 8, borderRadius: 6, background: 'rgba(234,179,8,0.12)', fontSize: 13,
                }}
              >
                {full.what_approving_does}
              </p>
            )}

            <h4 style={{ marginBottom: 4 }}>Conversation</h4>
            <div data-testid="approval-conversation" style={{ marginBottom: 12 }}>
              {(full.messages || []).length === 0 && (
                <p style={{ opacity: 0.6, fontSize: 13 }}>Nothing has been said yet.</p>
              )}
              {(full.messages || []).map((m) => (
                <div
                  key={m.id}
                  style={{
                    padding: 8, marginBottom: 6, borderRadius: 6,
                    background: m.system ? 'rgba(127,127,127,0.10)' : 'rgba(59,130,246,0.08)',
                    fontStyle: m.system ? 'italic' : 'normal',
                  }}
                >
                  <div style={{ fontSize: 12, opacity: 0.7 }}>
                    {m.system ? 'The platform' : (m.author_name || 'Somebody')} {'·'} {formatWhen(m.created_at)}
                  </div>
                  <div>{m.body}</div>
                  {(m.attachment_files || []).length > 0 && (
                    <div style={{ fontSize: 12, opacity: 0.8 }} data-testid="message-attachments">
                      {m.attachment_files.map((file) => (
                        <Attachment key={file.id} file={file} />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {full.may_reply ? (
              <div style={{ marginBottom: 12 }}>
                <textarea
                  aria-label="Reply"
                  style={{ ...inputStyle, minHeight: 60 }}
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  placeholder="Say something about this request"
                />
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' }}>
                  <input
                    type="file"
                    aria-label="Attach a file"
                    onChange={(e) => attach(e.target.files && e.target.files[0])}
                  />
                  <Button onClick={send} disabled={busy} data-testid="send-reply">
                    <Send size={14} /> Reply
                  </Button>
                  {attachments.length > 0 && (
                    <span style={{ fontSize: 12 }}>{attachments.length} file(s) ready to send</span>
                  )}
                </div>
              </div>
            ) : (
              <p style={{ fontSize: 13, opacity: 0.7 }} data-testid="conversation-closed">
                This has been decided, so the conversation is closed. It stays here to read.
              </p>
            )}

            {/*
              Decision 26. Both the raiser and anybody who may decide can bring somebody
              in, and the person doing the adding CHOOSES whether the conversation so far
              comes with them.
            */}
            <div style={{ marginBottom: 12 }}>
              {!adding ? (
                <Button variant="ghost" onClick={openAddPerson} data-testid="add-person">
                  <UserPlus size={14} /> Bring somebody in
                </Button>
              ) : (
                <div>
                  {/*
                    A LIST OF PEOPLE, BY NAME. This used to be a box asking for an
                    account id, which is a string nobody at the school knows or could
                    look up, so the control was there and could not be used. The id is
                    still what the server is sent; it simply never appears on screen and
                    nobody has to type it.

                    Only colleagues whose profile has been switched on are offered, which
                    is the same rule as the staff room: somebody who cannot sign in
                    cannot answer, and adding them would look like being ignored.
                  */}
                  {peopleError && <p style={{ color: 'crimson' }} role="alert">{peopleError}</p>}
                  <PeoplePicker
                    people={people}
                    value={newPerson}
                    onChange={setNewPerson}
                  />
                  {!peopleError && people.length === 0 && (
                    <p style={{ fontSize: 12, opacity: 0.7 }} data-testid="nobody-to-add">
                      There is nobody else to bring in.
                    </p>
                  )}
                  <label style={{ display: 'block', margin: '6px 0', fontSize: 13 }}>
                    <input
                      type="checkbox"
                      checked={shareHistory}
                      onChange={(e) => setShareHistory(e.target.checked)}
                    />{' '}
                    Let them read what has been said so far
                  </label>
                  <Button onClick={addPerson} disabled={busy}>Add them</Button>
                  <Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
                </div>
              )}
              <p style={{ fontSize: 12, opacity: 0.7, margin: '4px 0 0' }}>
                {(full.participants || []).length} people are in this conversation.
              </p>
            </div>

            {(full.may_decide || full.may_reopen) && (
              <div>
                <textarea
                  aria-label="Reason"
                  style={{ ...inputStyle, minHeight: 50 }}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Why. Required to refuse."
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  {full.may_decide && (
                    <>
                      <Button onClick={() => decide('approve')} disabled={busy} data-testid="approve">
                        <Check size={14} /> Approve
                      </Button>
                      <Button variant="danger" onClick={() => decide('reject')} disabled={busy} data-testid="reject">
                        <X size={14} /> Refuse
                      </Button>
                    </>
                  )}
                  {full.may_reopen && (
                    <Button variant="ghost" onClick={reopen} disabled={busy} data-testid="reopen">
                      Re-open this
                    </Button>
                  )}
                </div>
              </div>
            )}

            {!full.may_decide && full.is_pending && (
              <p style={{ fontSize: 13, opacity: 0.7 }} data-testid="not-yours-to-decide">
                This is not yours to decide. {full.who_decides}.
              </p>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
