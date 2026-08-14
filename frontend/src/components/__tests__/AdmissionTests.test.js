import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdmissionTests from '../tools/AdmissionTests';

/**
 * B1 on screen. The tests that matter are the two ways this list could mislead somebody:
 * a register nobody has filled in reading as a test nobody came to, and a mark that the
 * application refused looking like a mark that was saved.
 */

let mockDetail;
let mockPatchOk;
let mockPatched;

jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));
jest.mock('../../lib/api', () => ({
  API: '',
  apiFetch: async (url, options = {}) => {
    const ok = (data, meta = {}) => ({ ok: true, status: 200, json: async () => ({ success: true, data, meta }) });
    if (options.method === 'PATCH') {
      mockPatched.push({ url, body: JSON.parse(options.body) });
      if (!mockPatchOk) {
        return {
          ok: false, status: 409,
          json: async () => ({ detail: 'Application is not ready for assessment' }),
        };
      }
      return ok({});
    }
    if (url.includes('/admissions/tests/')) return ok(mockDetail);
    if (url.includes('/admissions/tests')) {
      return ok([{
        id: 't-1', title: 'Class 5 entrance', scheduled_for: '2026-08-23',
        start_time: '09:30', place: 'Main hall', maximum_marks: 50, status: 'planned',
        counts: mockDetail.counts,
      }]);
    }
    if (url.includes('/admissions/applications')) return ok([]);
    return ok([]);
  },
}));

const TEST = {
  id: 't-1', title: 'Class 5 entrance', scheduled_for: '2026-08-23', start_time: '09:30',
  place: 'Main hall', maximum_marks: 50, status: 'planned',
};

const seat = (over = {}) => ({
  id: 's-1', application_id: 'app-1', applicant_name: 'Aarav Singh',
  guardian_name: 'Neha Singh', guardian_phone: '9000000000',
  attendance: null, score: null, application_found: true, ...over,
});

beforeEach(() => {
  mockPatchOk = true;
  mockPatched = [];
  mockDetail = {
    test: TEST,
    seats: [seat()],
    counts: { seated: 1, present: 0, absent: 0, not_yet_marked: 1, scored: 0, present_but_not_yet_scored: 0 },
  };
});

test('a test shows its date, its time and its place, which is the whole point of B1', async () => {
  render(<AdmissionTests />);
  expect(await screen.findByText(/2026-08-23, 09:30 at Main hall/)).toBeInTheDocument();
});

test('nobody is shown as absent until somebody says so', async () => {
  render(<AdmissionTests />);
  fireEvent.click(await screen.findByText('Class 5 entrance'));
  expect(await screen.findByText('Aarav Singh')).toBeInTheDocument();
  // The row says "not marked yet" rather than sitting on a default.
  expect(screen.getByText('not marked yet')).toBeInTheDocument();
  // And the count line names it as its own number, in bold, separate from present and
  // absent. It reads twice on the page (the collapsed row also summarises it), which is
  // deliberate: the number a person needs is visible before they open the list.
  const bold = screen.getAllByText(/not yet marked/)
    .find(node => node.tagName.toLowerCase() === 'strong');
  expect(bold).toHaveTextContent('1 not yet marked');
});

test('a mark cannot be typed for somebody nobody has marked present', async () => {
  render(<AdmissionTests />);
  fireEvent.click(await screen.findByText('Class 5 entrance'));
  expect(await screen.findByText('mark them present first')).toBeInTheDocument();
  expect(screen.queryByLabelText(/Mark for Aarav Singh/)).not.toBeInTheDocument();
});

test('once present, the mark box appears and is capped at the paper total', async () => {
  mockDetail.seats = [seat({ attendance: 'present' })];
  mockDetail.counts = { ...mockDetail.counts, present: 1, not_yet_marked: 0, present_but_not_yet_scored: 1 };
  render(<AdmissionTests />);
  fireEvent.click(await screen.findByText('Class 5 entrance'));
  const box = await screen.findByLabelText(/Mark for Aarav Singh/);
  expect(box).toHaveAttribute('max', '50');

  fireEvent.blur(box, { target: { value: '38' } });
  await waitFor(() => expect(mockPatched).toHaveLength(1));
  expect(mockPatched[0].body).toEqual({ score: 38 });
});

test('a mark the application refuses is reported, not left looking saved', async () => {
  // The heart of it. If the application would not take the mark, it is not on this list
  // either, and the person entering it has to know that.
  mockPatchOk = false;
  mockDetail.seats = [seat({ attendance: 'present' })];
  render(<AdmissionTests />);
  fireEvent.click(await screen.findByText('Class 5 entrance'));
  fireEvent.blur(await screen.findByLabelText(/Mark for Aarav Singh/), { target: { value: '38' } });

  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('Aarav Singh');
  expect(alert).toHaveTextContent('not ready for assessment');
});

test('an applicant whose application has gone is still shown, not silently dropped', async () => {
  mockDetail.seats = [seat({ applicant_name: null, application_found: false })];
  render(<AdmissionTests />);
  fireEvent.click(await screen.findByText('Class 5 entrance'));
  expect(await screen.findByText('(application not found)')).toBeInTheDocument();
});

test('an empty list says so rather than showing an empty table', async () => {
  mockDetail.seats = [];
  mockDetail.counts = { seated: 0, present: 0, absent: 0, not_yet_marked: 0, scored: 0, present_but_not_yet_scored: 0 };
  render(<AdmissionTests />);
  fireEvent.click(await screen.findByText('Class 5 entrance'));
  expect(await screen.findByText('Nobody is on this list yet.')).toBeInTheDocument();
});
