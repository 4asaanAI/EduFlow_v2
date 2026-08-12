/**
 * R2-9 - what the two new people actually see when they try to print a document.
 *
 * Decision 6, 2026-08-10: the school's owner (Aman) and the principal (Adesh) issue a
 * certificate or a set of ID cards directly. The admin office (Lalit) asks first.
 *
 * The server is what enforces this - `tests/backend/api/test_certificate_approval_r2_9.py`
 * proves the print is refused. These tests are about the other half: the office must be
 * OFFERED the right button, rather than pressing a Download button that answers no. A
 * button that refuses when pressed reads as a broken platform, which is the exact defect
 * shape this initiative keeps finding.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

let mockCurrentUser = { id: 'u-1', role: 'admin', sub_category: 'management', name: 'Lalit' };

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: mockCurrentUser }),
}));
jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

import { setAuthSession, resetAuthRedirectGuardForTests } from '../../lib/authSession';

const STUDENTS = {
  success: true,
  data: [{ id: 's-1', name: 'Aarav Sharma', class_id: 'c-1', admission_number: 'ADM1', roll_number: '1' }],
};

function jsonOk(payload) {
  return { ok: true, status: 200, json: async () => payload, text: async () => JSON.stringify(payload) };
}

const realFetch = global.fetch;
let posted = [];

function serverThatApproves({ certificates = [] } = {}) {
  posted = [];
  global.fetch = jest.fn((url, opts) => {
    const href = String(url);
    if (opts?.method === 'POST') posted.push({ href, body: JSON.parse(opts.body || '{}') });
    if (href.includes('/ops/certificates/id-card-request')) {
      return Promise.resolve(jsonOk({
        success: true,
        data: { id: 'req-1', status: 'pending_approval', cert_type: 'id_card', student_ids: ['s-1'] },
      }));
    }
    if (href.includes('/ops/certificates')) return Promise.resolve(jsonOk({ success: true, data: certificates }));
    if (href.includes('/students')) return Promise.resolve(jsonOk(STUDENTS));
    return Promise.resolve(jsonOk({ success: true, data: [] }));
  });
}

beforeEach(() => {
  setAuthSession('a-valid-token', mockCurrentUser);
  resetAuthRedirectGuardForTests();
});

afterEach(() => {
  jest.restoreAllMocks();
  global.fetch = realFetch;
  resetAuthRedirectGuardForTests();
  mockCurrentUser = { id: 'u-1', role: 'admin', sub_category: 'management', name: 'Lalit' };
});

test('the admin office is offered "ask for approval", not a download that will be refused', async () => {
  serverThatApproves();
  const { IdCardGenerator } = await import('../tools/AdminTools');

  render(<IdCardGenerator />);
  await screen.findByText('Aarav Sharma');
  fireEvent.click(screen.getByText(/Select All/i));

  expect(await screen.findByText(/Ask for approval for 1 ID Cards/i)).toBeInTheDocument();
  expect(screen.queryByText(/Download 1 ID Cards PDF/i)).not.toBeInTheDocument();
});

test('asking for approval sends one request covering the whole batch', async () => {
  serverThatApproves();
  const { IdCardGenerator } = await import('../tools/AdminTools');

  render(<IdCardGenerator />);
  await screen.findByText('Aarav Sharma');
  fireEvent.click(screen.getByText(/Select All/i));
  fireEvent.click(await screen.findByText(/Ask for approval/i));

  await waitFor(() => expect(screen.getByTestId('id-card-awaiting')).toBeInTheDocument());
  const request = posted.filter(p => p.href.includes('id-card-request'));
  expect(request).toHaveLength(1);
  expect(request[0].body.student_ids).toEqual(['s-1']);
});

test('the owner and the principal still print straight away', async () => {
  for (const user of [
    { id: 'u-o', role: 'owner', sub_category: 'owner', name: 'Aman' },
    { id: 'u-p', role: 'admin', sub_category: 'principal', name: 'Adesh' },
  ]) {
    mockCurrentUser = user;
    setAuthSession('a-valid-token', user);
    serverThatApproves();
    const { IdCardGenerator } = await import('../tools/AdminTools');

    const view = render(<IdCardGenerator />);
    await screen.findByText('Aarav Sharma');
    fireEvent.click(screen.getByText(/Select All/i));

    expect(await screen.findByText(/Download 1 ID Cards PDF/i)).toBeInTheDocument();
    expect(screen.queryByText(/Ask for approval/i)).not.toBeInTheDocument();
    view.unmount();
  }
});

test('a batch already approved can be printed later, after a reload', async () => {
  serverThatApproves({
    certificates: [
      { id: 'req-old', cert_type: 'id_card', status: 'generated', serial_number: 'IDC1', student_ids: ['s-1'] },
    ],
  });
  const { IdCardGenerator } = await import('../tools/AdminTools');

  render(<IdCardGenerator />);
  await screen.findByText('Aarav Sharma');

  // Without this list the approval survives only as long as the browser tab, so a
  // request approved an hour later could never be printed at all.
  expect(await screen.findByText(/Approved and ready to print/i)).toBeInTheDocument();
  expect(screen.getByText('IDC1')).toBeInTheDocument();
});

test('a certificate still waiting for approval cannot be downloaded from the list', async () => {
  serverThatApproves();
  global.fetch = jest.fn((url) => {
    const href = String(url);
    if (href.includes('/ops/certificates')) {
      return Promise.resolve(jsonOk({
        success: true,
        data: [{
          id: 'c-1', student_id: 's-1', student_name: 'Aarav Sharma',
          cert_type: 'transfer_certificate', serial_number: 'CERT1',
          status: 'pending_approval', issued_date: null,
        }],
      }));
    }
    if (href.includes('/students')) return Promise.resolve(jsonOk(STUDENTS));
    return Promise.resolve(jsonOk({ success: true, data: [] }));
  });

  const { CertificateGenerator } = await import('../tools/AdminTools');
  render(<CertificateGenerator />);

  expect(await screen.findByText(/Awaiting approval/i)).toBeInTheDocument();
  expect(screen.getByText('PDF').closest('button')).toBeDisabled();
});

test('an issued certificate reads as issued, not as a failure', async () => {
  // The status an approved certificate carries is 'generated'. The screen looked for
  // 'approved', which nothing ever writes, so every certificate the school had ever
  // issued was shown in red as though it had been refused.
  global.fetch = jest.fn((url) => {
    const href = String(url);
    if (href.includes('/ops/certificates')) {
      return Promise.resolve(jsonOk({
        success: true,
        data: [{
          id: 'c-2', student_id: 's-1', student_name: 'Aarav Sharma',
          cert_type: 'bonafide', serial_number: 'CERT2',
          status: 'generated', issued_date: '2026-08-10',
        }],
      }));
    }
    if (href.includes('/students')) return Promise.resolve(jsonOk(STUDENTS));
    return Promise.resolve(jsonOk({ success: true, data: [] }));
  });

  const { CertificateGenerator } = await import('../tools/AdminTools');
  render(<CertificateGenerator />);

  expect(await screen.findByText('Issued')).toBeInTheDocument();
  expect(screen.getByText('PDF').closest('button')).not.toBeDisabled();
});
