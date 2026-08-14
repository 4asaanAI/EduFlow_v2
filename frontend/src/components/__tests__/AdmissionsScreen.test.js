import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Admissions } from '../tools/AdmissionsScreen';

/**
 * A4: three screens described one admissions funnel and are now one.
 *
 * The two rules this file exists to hold: grouping never grants, and nothing is dropped.
 */

let mockCurrentUser = { id: 'owner-1', role: 'owner', name: 'Owner' };

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: mockCurrentUser }),
}));
jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));
jest.mock('../../lib/api', () => ({
  API: '',
  apiFetch: async (url) => {
    let data = [];
    let meta = {};
    if (url.includes('/commercial/entities')) {
      data = [{ id: 'entity-1', name: 'The Aaryans', is_default: true, is_active: true }];
    } else if (url.includes('/ops/enquiries')) {
      data = [{
        id: 'enq-1', student_name: 'Applicant One', parent_name: 'Guardian One',
        mother_name: 'Mother One', father_name: 'Father One', phone: '9000000000',
        class_applying: 'Class 4', status: 'contacted', source: 'walk_in',
        created_at: '2026-08-01T00:00:00',
        journey: { label: 'In touch', source: 'enquiry', index: 2, total: 8, closed: false },
      }];
      meta = { total: 1, count: 1 };
    }
    return { ok: true, json: async () => ({ success: true, data, meta }) };
  },
}));

beforeEach(() => { mockCurrentUser = { id: 'owner-1', role: 'owner', name: 'Owner' }; });

test('the owner gets enquiries, applications and pipeline value on one screen', async () => {
  render(<Admissions />);
  expect(await screen.findByRole('tab', { name: 'Enquiries' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Applications' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Pipeline value' })).toBeInTheDocument();
});

test('the management head does NOT gain the pipeline by the tabs existing', async () => {
  // Grouping never grants. Lalit held both old admissions screens and neither had the
  // CRM panel on it, so the merged screen must not hand it to him. The gate inside the
  // panel is the same one Legal Entities has always used.
  mockCurrentUser = { id: 'mgmt-1', role: 'admin', sub_category: 'management', name: 'Management' };
  render(<Admissions />);
  expect(await screen.findByRole('tab', { name: 'Enquiries' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Applications' })).toBeInTheDocument();
  expect(screen.queryByRole('tab', { name: 'Pipeline value' })).not.toBeInTheDocument();
});

test('nothing was dropped: the CRM lead form is reachable from the pipeline tab', async () => {
  mockCurrentUser = { id: 'principal-1', role: 'admin', sub_category: 'principal', name: 'Principal' };
  render(<Admissions />);
  fireEvent.click(await screen.findByRole('tab', { name: 'Pipeline value' }));
  expect(await screen.findByTestId('crm-lead-form')).toBeInTheDocument();
  expect(screen.getByLabelText('Estimated value (₹)')).toBeInTheDocument();
});

test('the enquiries tab shows one position per family, and both parents', async () => {
  render(<Admissions />);
  expect(await screen.findByText('Applicant One')).toBeInTheDocument();
  expect(screen.getByText('In touch')).toBeInTheDocument();
  expect(screen.getByText('Mother One and Father One')).toBeInTheDocument();
});

test('the Tests tab is here now, and it opens onto a real screen', async () => {
  // This test asserted the OPPOSITE until 2026-08-15, and the reason it existed still
  // holds: a tab that opens onto nothing is a button that looks like a feature. B1 built
  // entrance tests as real records, so the assertion flips rather than being deleted. If
  // the tab is ever added back before its screen exists, this fails on the empty panel
  // instead of passing on the tab alone.
  render(<Admissions />);
  fireEvent.click(await screen.findByRole('tab', { name: 'Tests' }));
  expect(await screen.findByRole('region', { name: 'Entrance tests' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Test/ })).toBeInTheDocument();
});
