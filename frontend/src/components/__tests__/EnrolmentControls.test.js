/**
 * The recycle bin controls (owner request 10, 2026-08-06).
 *
 * Two things these guard, both of which were real reports:
 *  - "Include inactive" told you nothing about WHY someone was off the roll, and could
 *    not tell a child who stopped attending from one who has taken their TC.
 *  - The erase box demanded ten characters on the SERVER and said nothing on the
 *    screen, so you typed "x", pressed the button, and got a refusal with no reason.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  EnrolmentBadge,
  EnrolmentStateModal,
  EraseConfirmModal,
  ViewPicker,
} from '../ui/EnrolmentControls';
import { MIN_ERASE_REASON, readState } from '../../lib/enrolmentStates';

describe('reading which state a row is in', () => {
  it('trusts the state the server sent', () => {
    expect(readState({ enrolment_state: 'nso' })).toBe('nso');
  });

  it('reads NSO off the stored status when the server did not say', () => {
    expect(readState({ status: 'nso', is_active: false })).toBe('nso');
  });

  it('treats a legacy withdrawn record as one that has left', () => {
    // Records switched off before any of this existed carry status "withdrawn".
    // They behaved exactly like a TC-issued record yesterday and must keep doing so.
    expect(readState({ status: 'withdrawn', is_active: false })).toBe('tc_issued');
  });

  it('treats a record with nothing set as on the roll', () => {
    expect(readState({ name: 'Someone' })).toBe('active');
  });
});

describe('the status badge', () => {
  it.each([
    ['active', 'On the roll'],
    ['nso', 'NSO'],
    ['tc_issued', 'TC issued'],
  ])('shows %s as "%s"', (state, text) => {
    render(<EnrolmentBadge state={state} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });
});

describe('who to show', () => {
  it('offers the recycle bin to the owner and the principal', () => {
    render(<ViewPicker value="active" onChange={() => {}} canSeeOffRoll />);
    expect(screen.getByRole('option', { name: 'Recycle bin' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'NSO list' })).toBeInTheDocument();
  });

  it('does not offer it to anyone else, because the server would refuse it', () => {
    render(<ViewPicker value="active" onChange={() => {}} canSeeOffRoll={false} />);
    expect(screen.queryByRole('option', { name: 'Recycle bin' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'NSO list' })).not.toBeInTheDocument();
    // The daily register stays, because a teacher marks the NSO children every morning.
    expect(screen.getByRole('option', { name: 'On the daily register' })).toBeInTheDocument();
  });

  it('explains what the chosen view actually contains', () => {
    render(<ViewPicker value="on_register" onChange={() => {}} canSeeOffRoll />);
    expect(screen.getByText(/marked every morning/i)).toBeInTheDocument();
  });
});

describe('moving one person between the three states', () => {
  const person = { id: 's1', name: 'Riya Sharma' };

  it('spells out that an NSO child is still marked every day', () => {
    render(<EnrolmentStateModal person={person} currentState="active" onCancel={() => {}} onConfirm={() => {}} />);
    expect(screen.getByText(/still appears on the daily register/i)).toBeInTheDocument();
  });

  it('will not save until something has actually changed', () => {
    render(<EnrolmentStateModal person={person} currentState="active" onCancel={() => {}} onConfirm={() => {}} />);
    expect(screen.getByTestId('enrolment-save')).toBeDisabled();
  });

  it('passes the chosen state and the note back', () => {
    const onConfirm = jest.fn();
    render(<EnrolmentStateModal person={person} currentState="active" onCancel={() => {}} onConfirm={onConfirm} />);

    fireEvent.click(screen.getByRole('radio', { name: /NSO/i }));
    fireEvent.change(screen.getByTestId('enrolment-note'), { target: { value: 'Family moved away' } });
    fireEvent.click(screen.getByTestId('enrolment-save'));

    expect(onConfirm).toHaveBeenCalledWith('nso', 'Family moved away');
  });

  it('uses the staff wording on a staff record', () => {
    render(<EnrolmentStateModal person={person} currentState="active" kind="staff" onCancel={() => {}} onConfirm={() => {}} />);
    expect(screen.getByText('Left the school')).toBeInTheDocument();
  });
});

describe('erasing a record for good', () => {
  const person = { id: 's1', name: 'Riya Sharma' };

  it('says the reason is required before the button is pressed', () => {
    render(<EraseConfirmModal person={person} onCancel={() => {}} onConfirm={() => {}} />);
    expect(screen.getByText(/required/i)).toBeInTheDocument();
    expect(screen.getByTestId('erase-reason-hint')).toHaveTextContent(
      `At least ${MIN_ERASE_REASON} characters`,
    );
  });

  it('keeps the button out of reach until the reason is long enough', () => {
    const onConfirm = jest.fn();
    render(<EraseConfirmModal person={person} onCancel={() => {}} onConfirm={onConfirm} />);
    const button = screen.getByTestId('erase-confirm');

    expect(button).toBeDisabled();
    fireEvent.change(screen.getByTestId('erase-reason'), { target: { value: 'x' } });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByTestId('erase-reason'), { target: { value: 'Duplicate record from the import' } });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onConfirm).toHaveBeenCalledWith('Duplicate record from the import');
  });

  it('counts what has been typed so far, rather than just refusing', () => {
    render(<EraseConfirmModal person={person} onCancel={() => {}} onConfirm={() => {}} />);
    fireEvent.change(screen.getByTestId('erase-reason'), { target: { value: 'abc' } });
    expect(screen.getByTestId('erase-reason-hint')).toHaveTextContent('3 so far');
  });

  it('points at the reversible option instead', () => {
    render(<EraseConfirmModal person={person} onCancel={() => {}} onConfirm={() => {}} />);
    expect(screen.getByText(/use\s+the status button instead/i)).toBeInTheDocument();
  });
});
