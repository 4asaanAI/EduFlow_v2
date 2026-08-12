/**
 * Working a timetable out, on screen.
 *
 * THE RULE THIS PINS: generating shows you a week, it does not save one. The saved
 * timetable is what the substitution plan reads when a teacher is away, so a week
 * that appeared on its own is a week nobody has checked. Saving is a second,
 * deliberate tap and it goes to a different address.
 *
 * The other thing worth a test is WHO sees the button. Adesh writes the school's
 * timetables, so it is his tool and Aman's. Lalit keeps the screen and can still
 * hand-edit a period, exactly as he does today.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import TimetableBuilder from '../tools/TimetableBuilder';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

// Jest requires a mock-scoped name here; the hoisted factory may not reach an
// ordinary outer variable.
let mockUser;
jest.mock('../../contexts/UserContext', () => ({ useUser: () => ({ currentUser: mockUser }) }));

const CLASSES = [{ id: 'cls-5a', name: '5th', section: 'A' }];
const SUBJECTS = [
  { id: 'sub-maths', name: 'Mathematics', teacher_id: 'stf-1' },
  { id: 'sub-eng', name: 'English', teacher_id: 'stf-2' },
];

const PROPOSAL = {
  solved: true,
  slots: [
    { day: 'Monday', day_of_week: 0, period_number: 1, subject_id: 'sub-maths',
      teacher_id: 'stf-1', subject_name: 'Mathematics', teacher_name: 'Sharma' },
    { day: 'Tuesday', day_of_week: 1, period_number: 1, subject_id: 'sub-eng',
      teacher_id: 'stf-2', subject_name: 'English', teacher_name: 'Patel' },
  ],
  score: {
    total: 88, distribution: 90, teacher_preference: 100,
    morning_preference: 75, consecutive_avoidance: 100,
  },
  problems: [],
};

let posted;

function mockApi({ generate = PROPOSAL, generateOk = true, applyOk = true } = {}) {
  posted = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    const target = String(url);
    if (options.method === 'POST') {
      posted.push({ url: target, body: JSON.parse(options.body) });
      if (target.includes('/timetable/generate')) {
        return {
          ok: generateOk,
          json: async () => (generateOk ? { success: true, data: generate }
            : { detail: 'The timetable could not be worked out.' }),
        };
      }
      if (target.includes('/timetable/apply')) {
        return {
          ok: applyOk,
          json: async () => (applyOk
            ? { success: true, meta: { count: 2, replaced: 3 } }
            : { detail: 'A teacher in this timetable is already teaching another class.' }),
        };
      }
    }
    if (target.includes('/settings/classes')) return { ok: true, json: async () => ({ success: true, data: CLASSES }) };
    if (target.includes('/academics/subjects')) return { ok: true, json: async () => ({ success: true, data: SUBJECTS }) };
    if (target.includes('/academics/timetable/')) return { ok: true, json: async () => ({ success: true, data: [] }) };
    return { ok: true, json: async () => ({ success: true, data: [] }) };
  });
}

async function openClass() {
  render(<TimetableBuilder />);
  // Wait for the class OPTION, not just the select. Changing a select to a value
  // whose option has not rendered yet is silently ignored by React, and the test then
  // fails on the panel being absent rather than on the real reason.
  await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(1));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'cls-5a' } });
  await waitFor(() => expect(screen.getByRole('combobox').value).toBe('cls-5a'));
}

beforeEach(() => {
  mockUser = { role: 'admin', sub_category: 'principal', id: 'adesh-1' };
  mockApi();
});

afterEach(() => jest.restoreAllMocks());

// ── Who sees it ──────────────────────────────────────────────────────────────

test('the principal sees it, because he writes the timetables', async () => {
  await openClass();
  await waitFor(() => expect(screen.getByTestId('timetable-generator')).toBeInTheDocument());
});

test('the owner sees it, because he is never shut out of his own school', async () => {
  mockUser = { role: 'owner', id: 'aman-1' };
  await openClass();
  await waitFor(() => expect(screen.getByTestId('timetable-generator')).toBeInTheDocument());
});

test('the management head does not, but keeps the screen he has today', async () => {
  mockUser = { role: 'admin', sub_category: 'management', id: 'lalit-1' };
  await openClass();
  await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());
  expect(screen.queryByTestId('timetable-generator')).not.toBeInTheDocument();
});

// ── Generating proposes; it never saves ──────────────────────────────────────

test('working it out asks the server and shows the week, saving nothing', async () => {
  await openClass();
  await waitFor(() => expect(screen.getByTestId('generator-count-sub-maths')).toBeInTheDocument());

  fireEvent.change(screen.getByTestId('generator-count-sub-maths'), { target: { value: '6' } });
  fireEvent.click(screen.getByTestId('generator-run'));

  await waitFor(() => expect(screen.getByTestId('generator-proposal')).toBeInTheDocument());
  // One request, to generate. Nothing was saved.
  expect(posted).toHaveLength(1);
  expect(posted[0].url).toContain('/timetable/generate');
  expect(posted[0].body.periods_per_week).toEqual({ 'sub-maths': '6' });
  expect(screen.getByTestId('generator-proposal')).toHaveTextContent('Nothing is saved yet');
});

test('the marks are shown broken down, not just as one number', async () => {
  // So a person can see WHICH part is weak and change that one thing rather than
  // guessing at the whole request again.
  await openClass();
  await waitFor(() => expect(screen.getByTestId('generator-count-sub-maths')).toBeInTheDocument());
  fireEvent.change(screen.getByTestId('generator-count-sub-maths'), { target: { value: '6' } });
  fireEvent.click(screen.getByTestId('generator-run'));

  const panel = await screen.findByTestId('generator-proposal');
  expect(panel).toHaveTextContent('Overall 88/100');
  expect(panel).toHaveTextContent('Spread across the week 90');
  expect(panel).toHaveTextContent('Morning subjects in the morning 75');
});

test('saving is a separate tap that goes to a different address', async () => {
  await openClass();
  await waitFor(() => expect(screen.getByTestId('generator-count-sub-maths')).toBeInTheDocument());
  fireEvent.change(screen.getByTestId('generator-count-sub-maths'), { target: { value: '6' } });
  fireEvent.click(screen.getByTestId('generator-run'));
  await screen.findByTestId('generator-proposal');

  fireEvent.click(screen.getByTestId('generator-apply'));

  await waitFor(() => expect(posted).toHaveLength(2));
  expect(posted[1].url).toContain('/timetable/apply');
  expect(posted[1].body.slots).toHaveLength(2);
  // It says what it did, including what it replaced, because replacing a week is not
  // a small thing to do silently.
  await waitFor(() => expect(screen.getByTestId('generator-note'))
    .toHaveTextContent('replacing 3'));
});

// ── Failures say what to change ──────────────────────────────────────────────

test('an impossible request shows the server\'s own reasons, not "failed"', async () => {
  mockApi({
    generate: {
      solved: false, slots: [], score: null,
      problems: ['Nobody is set up to teach Hindi. Assign a teacher to it first.'],
    },
  });
  await openClass();
  await waitFor(() => expect(screen.getByTestId('generator-count-sub-maths')).toBeInTheDocument());
  fireEvent.change(screen.getByTestId('generator-count-sub-maths'), { target: { value: '6' } });
  fireEvent.click(screen.getByTestId('generator-run'));

  const problems = await screen.findByTestId('generator-problems');
  expect(problems).toHaveTextContent('Nobody is set up to teach Hindi');
  // Nothing to save, so nothing offers to.
  expect(screen.queryByTestId('generator-apply')).not.toBeInTheDocument();
});

test('a refused save says so and leaves the proposal on screen', async () => {
  mockApi({ applyOk: false });
  await openClass();
  await waitFor(() => expect(screen.getByTestId('generator-count-sub-maths')).toBeInTheDocument());
  fireEvent.change(screen.getByTestId('generator-count-sub-maths'), { target: { value: '6' } });
  fireEvent.click(screen.getByTestId('generator-run'));
  await screen.findByTestId('generator-proposal');

  fireEvent.click(screen.getByTestId('generator-apply'));

  await waitFor(() => expect(screen.getByTestId('generator-error'))
    .toHaveTextContent('already teaching another class'));
  // The week the person was looking at is still there, so they can try again rather
  // than start from nothing.
  expect(screen.getByTestId('generator-proposal')).toBeInTheDocument();
});

test('asking for more periods than the week holds is flagged before the request', async () => {
  await openClass();
  await waitFor(() => expect(screen.getByTestId('generator-count-sub-maths')).toBeInTheDocument());

  fireEvent.change(screen.getByTestId('generator-count-sub-maths'), { target: { value: '99' } });

  expect(screen.getByTestId('timetable-generator')).toHaveTextContent('more than the week holds');
});
