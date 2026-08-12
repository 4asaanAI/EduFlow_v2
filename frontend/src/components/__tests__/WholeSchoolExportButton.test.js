/**
 * "Download the whole school" - Release 3, item B.
 *
 * Two things are pinned here, and they are the two ways this control could do harm.
 *
 *  1. IT IS THE OWNER'S AND THE PRINCIPAL'S. Abhimanyu, 2026-08-12. The server
 *     refuses everybody else too; this hiding is the courtesy on top of that, so
 *     nobody taps a button that can only tell them no.
 *  2. IT READS BACK WHAT IT SAVED. Nine sheets is exactly the shape where one coming
 *     back empty goes unnoticed, and this is the largest copy of the school's records
 *     the platform can make. A download that says nothing about its size is how a
 *     short one gets filed.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WholeSchoolExportButton from '../ui/WholeSchoolExportButton';
import * as exportTable from '../../lib/exportTable';

const OWNER = { id: 'u1', role: 'owner', name: 'Aman' };
const PRINCIPAL = { id: 'u2', role: 'admin', sub_category: 'principal', name: 'Adesh' };
const ACCOUNTANT = { id: 'u3', role: 'admin', sub_category: 'accountant', name: 'Sonu' };
const MANAGEMENT = { id: 'u4', role: 'admin', sub_category: 'management', name: 'Lalit' };
const TEACHER = { id: 'u5', role: 'teacher', name: 'Teacher' };

let downloadWholeSchool;

beforeEach(() => {
  downloadWholeSchool = jest
    .spyOn(exportTable, 'downloadWholeSchool')
    .mockResolvedValue('Children: 1876; Staff: 62');
});

afterEach(() => jest.restoreAllMocks());

test.each([
  ['the school owner', OWNER],
  ['the principal', PRINCIPAL],
])('%s sees the whole-school download', (_label, user) => {
  render(<WholeSchoolExportButton user={user} />);
  expect(screen.getByTestId('whole-school-export')).toBeInTheDocument();
});

test.each([
  ['the accountant head', ACCOUNTANT],
  ['the management head', MANAGEMENT],
  ['a teacher', TEACHER],
  ['nobody signed in', null],
])('%s does not see it', (_label, user) => {
  render(<WholeSchoolExportButton user={user} />);
  expect(screen.queryByTestId('whole-school-export')).toBeNull();
});

test('says how many rows each sheet holds, so a short one cannot pass unnoticed', async () => {
  render(<WholeSchoolExportButton user={OWNER} />);

  fireEvent.click(screen.getByTestId('whole-school-export'));

  await waitFor(() => {
    expect(screen.getByTestId('whole-school-export-status')).toHaveTextContent('Children: 1876');
  });
  expect(downloadWholeSchool).toHaveBeenCalled();
});

test('a failed download says so out loud rather than looking finished', async () => {
  downloadWholeSchool.mockRejectedValue(
    new Error('There are more than 100,000 rows. No file was produced.'),
  );

  render(<WholeSchoolExportButton user={PRINCIPAL} />);
  fireEvent.click(screen.getByTestId('whole-school-export'));

  await waitFor(() => {
    expect(screen.getByTestId('whole-school-export-status'))
      .toHaveTextContent('No file was produced');
  });
});

test('there is no confirm step, because an export needs no approval', async () => {
  render(<WholeSchoolExportButton user={OWNER} />);

  fireEvent.click(screen.getByTestId('whole-school-export'));

  // One tap and it is downloading. Abhimanyu, 2026-08-12: an export needs no
  // approval window, on screen or through Flo.
  await waitFor(() => expect(downloadWholeSchool).toHaveBeenCalledTimes(1));
});
