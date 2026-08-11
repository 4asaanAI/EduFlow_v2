/**
 * The recycle bin controls, shared by the student screen and the staff screen.
 *
 * Owner request 10, 2026-08-06, and decision 2 of the same night: the three states
 * apply to students, staff AND teachers. One set of controls means the words, the
 * warnings and the character limit are identical wherever a person is moved between
 * the three, rather than two screens that slowly stop agreeing.
 *
 * Three pieces:
 *   ViewPicker         - "Who to show": on the roll, NSO, left, recycle bin, everyone.
 *   EnrolmentStateModal - move one person between the three states, with a note.
 *   EraseConfirmModal   - destroy a record for good. The reason is compulsory and
 *                         the screen says so BEFORE the button, which is the half
 *                         that was missing: the server already refused anything
 *                         under ten characters, silently, after the fact.
 */

import React, { useState } from 'react';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { Pill, inputStyle } from './primitives';
import {
  ENROLMENT_STATES,
  ENROLMENT_VIEWS,
  MIN_ERASE_REASON,
  RESTRICTED_VIEWS,
  stateBadge,
} from '../../lib/enrolmentStates';

const overlayStyle = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 210, padding: 16,
};

const panelStyle = {
  background: 'var(--c-input)', border: '1px solid var(--c-border)',
  borderRadius: 10, padding: 22, width: 520, maxWidth: '100%',
  maxHeight: '90vh', overflowY: 'auto',
};

/** The badge a table row shows. One rule, so the two tables cannot disagree. */
export function EnrolmentBadge({ state, 'data-testid': testId }) {
  const badge = stateBadge(state);
  return <Pill tone={badge.tone} data-testid={testId}>{badge.text}</Pill>;
}

/**
 * "Who to show".
 *
 * `canSeeOffRoll` is the owner-or-principal test. Anyone else is offered only the
 * two views the server will actually serve them, because offering a choice that
 * comes back as a refusal is worse than not offering it.
 */
export function ViewPicker({ value, onChange, canSeeOffRoll, label = 'Who to show', 'data-testid': testId }) {
  const options = canSeeOffRoll
    ? ENROLMENT_VIEWS
    : ENROLMENT_VIEWS.filter((v) => !RESTRICTED_VIEWS.includes(v.value));
  const active = options.find((o) => o.value === value);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        data-testid={testId}
        // 200px is the comfortable desktop width, but it must never be a floor: this
        // sits in a wrapping toolbar beside a search box, and a fixed width there is
        // what pushes a 320px phone into sideways scrolling (owner request 20 sweep).
        style={{ ...inputStyle, width: 200, maxWidth: '100%' }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {active?.help ? (
        <span style={{ fontSize: 11, color: 'var(--c-faint)', maxWidth: 260, lineHeight: 1.45 }}>
          {active.help}
        </span>
      ) : null}
    </div>
  );
}

/**
 * Move one person between on the roll, NSO and TC issued.
 *
 * Every option carries its plain-language consequence, because the difference that
 * matters is invisible otherwise: an NSO child is still marked every morning and a
 * child with a TC is not, and nobody can be expected to remember which is which
 * from a two-word label.
 */
export function EnrolmentStateModal({ person, currentState, kind = 'student', onCancel, onConfirm, busy }) {
  const [state, setState] = useState(currentState || 'active');
  const [reason, setReason] = useState('');
  const noun = kind === 'staff' ? 'staff member' : 'student';

  return (
    <div style={overlayStyle} role="dialog" aria-modal="true" aria-label={`Change enrolment state for ${person?.name}`}>
      <div style={panelStyle}>
        <h3 style={{ color: 'var(--c-text)', fontSize: 16, margin: '0 0 4px' }}>
          {person?.name}
        </h3>
        <p style={{ color: 'var(--c-faint)', fontSize: 12, margin: '0 0 14px' }}>
          Where does this {noun} stand? This can be changed back at any time.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {ENROLMENT_STATES.map((option) => (
            <label
              key={option.value}
              style={{
                display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer',
                border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 12px',
                background: state === option.value ? 'var(--c-hover, rgba(127,127,127,0.08))' : 'transparent',
              }}
            >
              <input
                type="radio"
                name="enrolment-state"
                value={option.value}
                checked={state === option.value}
                onChange={() => setState(option.value)}
                style={{ marginTop: 3 }}
              />
              <span>
                <span style={{ display: 'block', color: 'var(--c-text)', fontSize: 13, fontWeight: 700 }}>
                  {kind === 'staff' ? option.forStaff : option.label}
                </span>
                <span style={{ display: 'block', color: 'var(--c-faint)', fontSize: 12, lineHeight: 1.5, marginTop: 2 }}>
                  {option.help}
                </span>
              </span>
            </label>
          ))}
        </div>

        <label style={{ display: 'block', color: 'var(--c-muted)', fontSize: 12, margin: '14px 0 5px' }}>
          Note (optional) - kept in the action log next to your name
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          data-testid="enrolment-note"
          style={{ ...inputStyle, width: '100%', resize: 'vertical' }}
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <button type="button" onClick={onCancel} style={secondaryButton}>Cancel</button>
          <button
            type="button"
            data-testid="enrolment-save"
            disabled={busy || state === currentState}
            onClick={() => onConfirm(state, reason.trim())}
            style={{ ...primaryButton, opacity: busy || state === currentState ? 0.5 : 1 }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Destroy a record for good.
 *
 * The reason box is not decoration. The server refuses anything under
 * MIN_ERASE_REASON characters, and before this the screen never said so: you typed
 * "x", pressed the button, and got a refusal with no explanation. Now the rule is
 * on the screen, the count is live, and the button stays out of reach until it is met.
 */
export function EraseConfirmModal({ person, kind = 'student', onCancel, onConfirm, busy }) {
  const [reason, setReason] = useState('');
  const trimmed = reason.trim();
  const short = trimmed.length < MIN_ERASE_REASON;
  const noun = kind === 'staff' ? 'staff member' : 'student';

  return (
    <div style={overlayStyle} role="dialog" aria-modal="true" aria-label={`Erase ${person?.name} permanently`}>
      <div style={panelStyle}>
        <h3 style={{ color: 'var(--c-text)', fontSize: 16, margin: '0 0 6px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={16} aria-hidden="true" style={{ color: 'var(--color-danger, #fb7185)' }} />
          Erase {person?.name} permanently
        </h3>
        <p style={{ color: 'var(--c-faint)', fontSize: 12, lineHeight: 1.6, margin: '0 0 12px' }}>
          This destroys the {noun}&rsquo;s record. It cannot be undone and Restore will
          not bring it back. If you only want them off the roll, close this and use
          the status button instead.
        </p>

        <label htmlFor="erase-reason" style={{ display: 'block', color: 'var(--c-muted)', fontSize: 12, marginBottom: 5 }}>
          Why are you erasing this record? Required.
        </label>
        <textarea
          id="erase-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          data-testid="erase-reason"
          aria-describedby="erase-reason-hint"
          style={{ ...inputStyle, width: '100%', resize: 'vertical' }}
        />
        <div
          id="erase-reason-hint"
          data-testid="erase-reason-hint"
          style={{ fontSize: 11, marginTop: 5, color: short ? 'var(--color-danger, #fb7185)' : 'var(--c-faint)' }}
        >
          {short
            ? `At least ${MIN_ERASE_REASON} characters. ${trimmed.length} so far.`
            : 'This is kept in the action log with your name and the time.'}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <button type="button" onClick={onCancel} style={secondaryButton}>Cancel</button>
          <button
            type="button"
            data-testid="erase-confirm"
            disabled={short || busy}
            onClick={() => onConfirm(trimmed)}
            style={{ ...dangerButton, opacity: short || busy ? 0.5 : 1 }}
          >
            <Trash2 size={14} aria-hidden="true" />
            Erase for good
          </button>
        </div>
      </div>
    </div>
  );
}

const baseButton = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '8px 14px', borderRadius: 8, fontSize: 13, fontWeight: 700,
  cursor: 'pointer', fontFamily: 'var(--font-display)',
};
const secondaryButton = {
  ...baseButton,
  background: 'transparent', color: 'var(--c-text)', border: '1px solid var(--c-border)',
};
const primaryButton = {
  ...baseButton,
  background: 'var(--color-accent-blue, #2b8ff0)', color: '#fff', border: 'none',
};
const dangerButton = {
  ...baseButton,
  background: 'var(--color-danger, #fb7185)', color: '#fff', border: 'none',
};

export default EnrolmentStateModal;
