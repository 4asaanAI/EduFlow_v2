import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FollowUpWorklist } from '../tools/AdminTools';

/**
 * A5: who to call today.
 *
 * The tests that matter here are not "the list renders". They are the two ways this
 * block could quietly mislead somebody: an empty list reading as "the office is up to
 * date", and a refused save reading as a saved note.
 */

let mockWorklist;
let mockStatus;
let mockPosted;
let mockPostOk;

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'owner-1', role: 'owner', name: 'Owner' } }),
}));
jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));
jest.mock('../../lib/api', () => ({
  API: '',
  apiFetch: async (url, options) => {
    if (options?.method === 'POST') {
      mockPosted.push({ url, body: JSON.parse(options.body) });
      return mockPostOk
        ? { ok: true, status: 200, json: async () => ({ success: true, data: {} }) }
        : { ok: false, status: 400, json: async () => ({ detail: 'next_follow_up must be a date in YYYY-MM-DD form' }) };
    }
    return { ok: mockStatus === 200, status: mockStatus, json: async () => ({ success: true, data: mockWorklist }) };
  },
}));

const EMPTY = {
  today: '2026-08-14', upcoming_days: 7, upcoming_until: '2026-08-21',
  overdue: [], due_today: [], upcoming: [],
  counts: {
    overdue: 0, due_today: 0, upcoming: 0, scheduled_beyond_the_window: 0,
    active_enquiries: 90, no_follow_up_date_set: 90,
  },
};

const ONE_MISSED = {
  ...EMPTY,
  overdue: [{
    enquiry_id: 'enq-1', student_name: 'Aarav Singh', parent_name: 'Neha Singh',
    phone: '9000000000', status: 'contacted', next_follow_up: '2026-08-09',
    date_is_readable: true, days_overdue: 5,
    last_activity: { activity_type: 'visit', subject: 'Campus visit' },
  }],
  counts: { ...EMPTY.counts, overdue: 1, active_enquiries: 90, no_follow_up_date_set: 89 },
};

beforeEach(() => { mockWorklist = ONE_MISSED; mockStatus = 200; mockPosted = []; mockPostOk = true; });

test('a family the office missed is named, with how late it is and what was said last', async () => {
  render(<FollowUpWorklist />);
  expect(await screen.findByText('Aarav Singh')).toBeInTheDocument();
  expect(screen.getByText('5 days late')).toBeInTheDocument();
  expect(screen.getByText('last: Campus visit')).toBeInTheDocument();
});

test('an empty list still says how many families nobody has planned a call with', async () => {
  // The whole point of the item. "No calls due" and "nobody has scheduled anything for
  // ninety families" are opposite facts and must never look the same.
  mockWorklist = EMPTY;
  render(<FollowUpWorklist />);
  expect(await screen.findByText(/No calls are due/)).toBeInTheDocument();
  expect(screen.getByText(/90 of 90 open enquiries have no follow-up date at all/)).toBeInTheDocument();
});

test('a date nobody can read is shown as unreadable rather than dropped', async () => {
  mockWorklist = {
    ...EMPTY,
    overdue: [{
      enquiry_id: 'enq-2', student_name: 'Odd Child', parent_name: 'Parent',
      phone: '9000000001', next_follow_up: 'sometime soon', date_is_readable: false,
      days_overdue: 0, last_activity: null,
    }],
    counts: { ...EMPTY.counts, overdue: 1 },
  };
  render(<FollowUpWorklist />);
  expect(await screen.findByText('Odd Child')).toBeInTheDocument();
  expect(screen.getByText(/cannot be read/)).toBeInTheDocument();
});

test('logging a call sends the note and the next date to the one activity route', async () => {
  render(<FollowUpWorklist />);
  fireEvent.click(await screen.findByRole('button', { name: 'Log call' }));
  fireEvent.change(screen.getByLabelText(/What happened/), { target: { value: 'Spoke to mother' } });
  fireEvent.change(screen.getByLabelText(/Call again on/), { target: { value: '2026-08-20' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

  await waitFor(() => expect(mockPosted).toHaveLength(1));
  expect(mockPosted[0].url).toContain('/commercial/crm/leads/enq-1/activities');
  expect(mockPosted[0].body).toMatchObject({
    activity_type: 'call', subject: 'Spoke to mother', next_follow_up: '2026-08-20',
  });
  expect(await screen.findByText(/next call 2026-08-20/)).toBeInTheDocument();
});

test('a refused save says so, because silence looks exactly like a saved note', async () => {
  mockPostOk = false;
  render(<FollowUpWorklist />);
  fireEvent.click(await screen.findByRole('button', { name: 'Log call' }));
  fireEvent.change(screen.getByLabelText(/What happened/), { target: { value: 'Called' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('YYYY-MM-DD');
});

test('saving with no next date says the family drops off the list', async () => {
  render(<FollowUpWorklist />);
  fireEvent.click(await screen.findByRole('button', { name: 'Log call' }));
  fireEvent.change(screen.getByLabelText(/What happened/), { target: { value: 'No answer' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

  expect(await screen.findByText(/drops off the list/)).toBeInTheDocument();
});

test('a desk the follow-up gate refuses sees nothing at all, not an error over a list that works', async () => {
  mockStatus = 403;
  const { container } = render(<FollowUpWorklist />);
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});
