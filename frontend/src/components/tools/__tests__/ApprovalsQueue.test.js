/**
 * The approvals screen. 2026-08-15.
 *
 * Until this screen existed, `getApprovalRequests` and `decideApprovalRequest` sat in
 * `lib/api.js` and nothing called them: the platform could ask for permission and could
 * not receive it, so every deletion the transport head asked for and every repair cost
 * he proposed stayed pending for ever.
 *
 * These tests render the real screen and read the words a person would actually see,
 * rather than checking a variable. Two screen-side faults on 2026-08-15 were both of the
 * kind no test then existing could have caught, because the fault was the absence of one.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ApprovalsQueue from '../ApprovalsQueue';
import * as api from '../../../lib/api';

jest.mock('../../../lib/api');

const KINDS = [
  { kind: 'general', label: 'Approval request', who_decides: 'The school\'s owner', steps: 1 },
  { kind: 'certificate', label: 'Certificate', who_decides: 'The owner or principal', steps: 1 },
  { kind: 'student_leave', label: 'Student leave', who_decides: 'The class teacher first', steps: 2 },
];

function card(over = {}) {
  return {
    kind: 'general',
    kind_label: 'Approval request',
    id: 'a1',
    title: 'Delete the bus route Joya Town',
    detail: 'No longer used',
    status: 'pending',
    is_pending: true,
    raised_by: 'chaman',
    raised_at: '2026-08-15T09:00:00+00:00',
    who_decides: "The school's owner, or the principal when it is sent to both",
    steps: 1,
    step_label: "The school's owner, or the principal when it is sent to both",
    hours_waiting: 3,
    overdue: false,
    ...over,
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  api.getApprovalKinds.mockResolvedValue({ success: true, data: KINDS });
  api.getApprovalPeople.mockResolvedValue({
    success: true,
    data: [
      { id: 'sonu', name: 'Sonu Ruhal', job: 'Accountant', already_in: false },
      { id: 'lalit', name: 'Lalit Thomas', job: 'Management', already_in: false },
    ],
    meta: { count: 2 },
  });
  api.getApprovalsWaitingOnMe.mockResolvedValue({
    success: true, data: [card()], meta: { count: 1, overdue: 0 },
  });
  api.getApprovalsIRaised.mockResolvedValue({
    success: true, data: [], meta: { count: 0, still_waiting: 0 },
  });
  api.getApproval.mockResolvedValue({
    success: true,
    data: { ...card(), may_decide: true, may_reply: true, may_reopen: false, may_edit: false,
            participants: [{ user_id: 'aman' }], conversation_status: 'open', messages: [] },
  });
});

test('it shows what is waiting on you', async () => {
  render(<ApprovalsQueue />);
  expect(await screen.findByText('Delete the bus route Joya Town')).toBeInTheDocument();
});

test('the two directions are both offered, because a department head raises far more than he decides', async () => {
  render(<ApprovalsQueue />);
  await screen.findByText('Delete the bus route Joya Town');
  fireEvent.click(screen.getByTestId('tab-raised'));
  await waitFor(() => expect(api.getApprovalsIRaised).toHaveBeenCalled());
  expect(await screen.findByText(/You have not asked for anything/i)).toBeInTheDocument();
});

test('the filter offers every kind the SERVER knows about, and names none of its own', async () => {
  // The whole promise is that a seventh kind of approval appears here the day it is
  // added on the server. A hard-coded list in this file would break that quietly.
  render(<ApprovalsQueue />);
  await screen.findByText('Delete the bus route Joya Town');
  expect(await screen.findByRole('option', { name: 'Certificate' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Student leave' })).toBeInTheDocument();
});

test('a request that CARRIES OUT the action says so, in ordinary words', async () => {
  // R3-2's rule, on the shared screen. Without it the card reads like every other
  // request and a person would press Approve believing they were recording an opinion,
  // and a bus route would disappear.
  api.getApprovalsWaitingOnMe.mockResolvedValue({
    success: true,
    data: [card({
      carries_out_the_action: true,
      what_approving_does: 'Agreeing to this DELETES the bus route straight away.',
    })],
    meta: { count: 1, overdue: 0 },
  });
  render(<ApprovalsQueue />);
  expect(await screen.findByTestId('carries-out-the-action'))
    .toHaveTextContent('DELETES the bus route');
});

test('something left too long is flagged, and nothing is decided for anybody', async () => {
  api.getApprovalsWaitingOnMe.mockResolvedValue({
    success: true, data: [card({ overdue: true, hours_waiting: 120 })],
    meta: { count: 1, overdue: 1 },
  });
  render(<ApprovalsQueue />);
  expect(await screen.findByTestId('overdue-banner')).toBeInTheDocument();
  expect(screen.getByTestId('overdue-pill')).toBeInTheDocument();
  // Still sitting there waiting for a person. There is no auto-decide anywhere.
  expect(api.decideApproval).not.toHaveBeenCalled();
});

test('refusing without saying why is refused before anything is sent', async () => {
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  fireEvent.click(await screen.findByTestId('reject'));
  expect(await screen.findByRole('alert')).toHaveTextContent(/why it was refused/i);
  expect(api.decideApproval).not.toHaveBeenCalled();
});

test('approving sends the decision and the reason', async () => {
  api.decideApproval.mockResolvedValue({ success: true, data: {} });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  fireEvent.change(await screen.findByLabelText('Reason'), { target: { value: 'Go ahead' } });
  fireEvent.click(screen.getByTestId('approve'));
  await waitFor(() => expect(api.decideApproval)
    .toHaveBeenCalledWith('general', 'a1', { decision: 'approve', reason: 'Go ahead' }));
});

test('somebody who cannot decide is TOLD SO, rather than shown buttons that will refuse', async () => {
  api.getApproval.mockResolvedValue({
    success: true,
    data: { ...card(), may_decide: false, may_reply: true, may_reopen: false,
            participants: [], conversation_status: 'open', messages: [] },
  });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  expect(await screen.findByTestId('not-yours-to-decide')).toBeInTheDocument();
  expect(screen.queryByTestId('approve')).not.toBeInTheDocument();
});

test('a decided conversation is closed to replies and still readable', async () => {
  api.getApproval.mockResolvedValue({
    success: true,
    data: {
      ...card({ status: 'rejected', is_pending: false }),
      may_decide: false, may_reply: false, may_reopen: false,
      participants: [], conversation_status: 'closed',
      messages: [{ id: 'm1', body: 'twelve thousand', author_name: 'Chaman',
                   system: false, created_at: '2026-08-15T09:05:00+00:00', attachments: [] }],
    },
  });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  expect(await screen.findByTestId('conversation-closed')).toBeInTheDocument();
  // Nothing is ever destroyed: the reasoning behind a refusal is often the most useful
  // thing in the whole thread.
  expect(screen.getByText('twelve thousand')).toBeInTheDocument();
});

test('bringing somebody in asks whether the history comes with them', async () => {
  // Decision 26, and the half that would leak if it were missing: sometimes what was
  // said before should come with a person and sometimes it must not.
  api.addApprovalParticipant.mockResolvedValue({ success: true, data: {} });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  fireEvent.click(await screen.findByTestId('add-person'));
  // Chosen from a list BY NAME, typed to narrow it. The account id still travels to the
  // server and never appears on screen; nobody has to know or type one.
  fireEvent.change(await screen.findByLabelText('Who to bring in'),
    { target: { value: 'sonu r' } });
  fireEvent.click(await screen.findByText(/Sonu Ruhal/));
  fireEvent.click(screen.getByLabelText(/read what has been said so far/i));
  fireEvent.click(screen.getByText('Add them'));
  await waitFor(() => expect(api.addApprovalParticipant)
    .toHaveBeenCalledWith('general', 'a1', { user_id: 'sonu', share_history: false }));
});

test('an attachment goes through the ORDINARY upload door, not a second one', async () => {
  // The 2026-08-15 photo rules are not worked around: the same allowed types, the same
  // size ceiling, the same private storage. There is deliberately no second way to put
  // a file into this school's storage.
  api.uploadEntityFile.mockResolvedValue({ success: true, data: { id: 'file-1' } });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  const file = new File(['quote'], 'quote.pdf', { type: 'application/pdf' });
  fireEvent.change(await screen.findByLabelText('Attach a file'), { target: { files: [file] } });
  await waitFor(() => expect(api.uploadEntityFile)
    .toHaveBeenCalledWith(file, 'approval_attachment', 'general:a1'));
});

test('there is no approve-all anywhere on this screen', () => {
  // Deliberately not taken from LayaaOS, and at odds with decision 28. Approving can
  // delete a bus route or commit real money, so every one is decided on its own.
  const source = require('fs').readFileSync(
    require('path').join(__dirname, '..', 'ApprovalsQueue.js'), 'utf8');
  expect(source).not.toMatch(/approve[ _]?all/i);
  expect(source).not.toMatch(/batch/i);
});

test('Flo is never rendered inside the shared conversation', () => {
  // Decision 29, the sharpest one. Aman's Flo sees far more than Chaman's, so an answer
  // printed into the shared transcript would be built on Aman's access and read in front
  // of somebody who does not hold it. Pinned as a fact about the file: this screen
  // cannot reach the assistant at all.
  const source = require('fs').readFileSync(
    require('path').join(__dirname, '..', 'ApprovalsQueue.js'), 'utf8');
  expect(source).not.toMatch(/ChatInterface|sendChatMessage|askFlo/);
});

// ── The three leftovers, closed 2026-08-15 ──────────────────────────────────

test('a person can ASK for something, not only answer', async () => {
  // Until this the screen could receive permission and, for a general request, nobody
  // could ask for it except through Flo. Abhimanyu's own example, the accountant head
  // raising a salary approval, had no button anywhere.
  api.getApprovalKinds.mockResolvedValue({
    success: true,
    data: [{ ...KINDS[0], may_raise: true }, { ...KINDS[1], may_raise: false }],
  });
  api.createApprovalRequest.mockResolvedValue({ success: true, data: { id: 'new-1' } });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('raise-request'));

  fireEvent.change(screen.getByLabelText(/What are you asking for/i),
    { target: { value: 'A second bus for the Amroha run' } });
  fireEvent.change(screen.getByLabelText(/^Why/i),
    { target: { value: 'Forty children are standing' } });
  fireEvent.change(screen.getByLabelText(/What it costs or changes/i),
    { target: { value: 'About 18,000 a month' } });
  fireEvent.change(screen.getByLabelText(/Anything else/i),
    { target: { value: 'The driver is already on the roll' } });
  fireEvent.click(screen.getByTestId('send-request'));

  await waitFor(() => expect(api.createApprovalRequest).toHaveBeenCalledWith({
    title: 'A second bus for the Amroha run',
    description: 'Forty children are standing',
    estimated_impact: 'About 18,000 a month',
    note: 'The driver is already on the roll',
    routing: 'owner_and_principal',
  }));
});

test('the ask control is hidden from somebody the server says may not raise', async () => {
  // Decision 25: Aman and Adesh approve, they do not raise. The server answers it per
  // kind, so the screen never holds its own idea of who may ask for what.
  api.getApprovalKinds.mockResolvedValue({
    success: true, data: KINDS.map((k) => ({ ...k, may_raise: false })),
  });
  render(<ApprovalsQueue />);
  await screen.findByTestId('open-approval');
  expect(screen.queryByTestId('raise-request')).not.toBeInTheDocument();
});

test('an empty box is named before anything is sent', async () => {
  api.getApprovalKinds.mockResolvedValue({
    success: true, data: [{ ...KINDS[0], may_raise: true }],
  });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('raise-request'));
  fireEvent.click(screen.getByTestId('send-request'));
  expect(await screen.findByRole('alert')).toHaveTextContent(/needs filling in/i);
  expect(api.createApprovalRequest).not.toHaveBeenCalled();
});

test('the colleague list shows names and can be narrowed by typing', async () => {
  // It used to ask for an account id, which is a string nobody at the school knows or
  // could look up, so the control was there and could not be used.
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  fireEvent.click(await screen.findByTestId('add-person'));

  expect(await screen.findByText(/Sonu Ruhal/)).toBeInTheDocument();
  expect(screen.getByText(/Lalit Thomas/)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('Who to bring in'), { target: { value: 'lal' } });
  expect(screen.queryByText(/Sonu Ruhal/)).not.toBeInTheDocument();
  expect(screen.getByText(/Lalit Thomas/)).toBeInTheDocument();
  // The count stays visible, so three matches out of ninety never reads like a school
  // with three staff.
  expect(screen.getByTestId('people-count')).toHaveTextContent('1 of 2');
});

test('no account id is ever shown to the person choosing', async () => {
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  fireEvent.click(await screen.findByTestId('add-person'));
  await screen.findByText(/Sonu Ruhal/);
  expect(screen.getByTestId('person-picklist')).not.toHaveTextContent(/\bsonu\b(?! Ruhal)/);
});

test('an attachment can be opened, and is not just a count', async () => {
  // A count is not a document. The accountant head sitting in a repair-cost conversation
  // precisely because he pays it could see that a quote existed and could not open it.
  api.getApproval.mockResolvedValue({
    success: true,
    data: {
      ...card(), may_decide: false, may_reply: true, may_reopen: false, may_edit: false,
      participants: [], conversation_status: 'open',
      messages: [{
        id: 'm1', body: 'The quote', author_name: 'Chaman', system: false,
        created_at: '2026-08-15T09:05:00+00:00',
        attachments: ['file-1'],
        attachment_files: [{ id: 'file-1', file_name: 'garage-quote.pdf', file_size_kb: 42 }],
      }],
    },
  });
  api.getGeneratedFileLink.mockResolvedValue({
    success: true, data: { download_url: 'https://example.test/signed', file_name: 'garage-quote.pdf' },
  });
  window.open = jest.fn();

  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  const button = await screen.findByTestId('open-attachment');
  expect(button).toHaveTextContent('garage-quote.pdf');

  fireEvent.click(button);
  // Minted when it is clicked, never held: a stored link goes stale and then fails in a
  // way that reads like the file being gone.
  await waitFor(() => expect(api.getGeneratedFileLink).toHaveBeenCalledWith('file-1'));
  await waitFor(() => expect(window.open).toHaveBeenCalledWith(
    'https://example.test/signed', '_blank', 'noopener,noreferrer'));
});

test('a file that is no longer stored says so instead of offering a broken button', async () => {
  api.getApproval.mockResolvedValue({
    success: true,
    data: {
      ...card(), may_decide: false, may_reply: true, may_reopen: false, may_edit: false,
      participants: [], conversation_status: 'open',
      messages: [{
        id: 'm1', body: 'The quote', author_name: 'Chaman', system: false,
        created_at: '2026-08-15T09:05:00+00:00', attachments: ['gone'],
        attachment_files: [{ id: 'gone', file_name: 'A file that is no longer stored',
                             missing: true }],
      }],
    },
  });
  render(<ApprovalsQueue />);
  fireEvent.click(await screen.findByTestId('open-approval'));
  expect(await screen.findByTestId('attachment-missing')).toBeInTheDocument();
  expect(screen.queryByTestId('open-attachment')).not.toBeInTheDocument();
});
