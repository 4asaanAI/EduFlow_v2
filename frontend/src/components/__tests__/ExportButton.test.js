/**
 * The download control on a table - Release 3, item 4.
 *
 * THE ONE THAT MATTERS is the first test: a download must hold the WHOLE filtered
 * set, never the page on screen. Someone on page 3 of the unpaid fees who presses
 * Download means "the unpaid fees". A file holding fifteen rows, with nothing on it
 * to say so, is this release's defining fault in its worst form - a file leaves the
 * building and is filed as a record.
 *
 * The second thing these pin is that a failed download SAYS SO. A browser that
 * silently saves nothing looks exactly like one that saved an empty file.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DataTable from '../ui/DataTable';
import ExportButton from '../ui/ExportButton';
import * as exportTable from '../../lib/exportTable';

const COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'due', label: 'Due' },
];

/** The fifteen rows a person can see: a small slice of a much longer list. */
const PAGE_ON_SCREEN = Array.from({ length: 15 }, (_, i) => ({
  id: `p${i}`, name: `On screen ${i}`, due: 100,
}));

/** Every row matching the filters in force. */
const WHOLE_FILTERED_SET = Array.from({ length: 640 }, (_, i) => ({
  id: `r${i}`, name: `Child ${i}`, due: 100,
}));

let downloadTableRows;
let downloadServerExport;

beforeEach(() => {
  downloadTableRows = jest.spyOn(exportTable, 'downloadTableRows').mockResolvedValue();
  downloadServerExport = jest.spyOn(exportTable, 'downloadServerExport').mockResolvedValue();
});

afterEach(() => jest.restoreAllMocks());

test('downloads the whole filtered set, not the page on screen', async () => {
  render(
    <DataTable
      tableId="fees"
      columns={COLUMNS}
      rows={PAGE_ON_SCREEN}
      page={3}
      total={640}
      pageSize={15}
      exportTable={{ title: 'Unpaid fees', getRows: async () => WHOLE_FILTERED_SET }}
    />,
  );

  fireEvent.click(screen.getByTestId('fees-export-xlsx'));

  await waitFor(() => expect(downloadTableRows).toHaveBeenCalled());
  const sent = downloadTableRows.mock.calls[0][0];
  expect(sent.rows).toHaveLength(640);
  expect(sent.rows[0]).toEqual(['Child 0', 100]);
  // The page on screen must not be what went into the file.
  expect(JSON.stringify(sent.rows)).not.toContain('On screen');
});

test('says how many rows it saved', async () => {
  // The count is the only way a person can notice a short file. Every "all" view and
  // every export in this release shows one for that reason.
  render(
    <ExportButton title="Children" columns={COLUMNS} getRows={async () => WHOLE_FILTERED_SET} />,
  );

  fireEvent.click(screen.getByTestId('export-csv'));

  await waitFor(() => expect(screen.getByTestId('export-status')).toHaveTextContent('640 rows'));
});

test('a failed download says nothing was saved, rather than failing quietly', async () => {
  downloadTableRows.mockRejectedValue(new Error('The download failed. Nothing was saved.'));

  render(<ExportButton title="Children" columns={COLUMNS} getRows={async () => [{}]} />);
  fireEvent.click(screen.getByTestId('export-xlsx'));

  await waitFor(() => expect(screen.getByTestId('export-status'))
    .toHaveTextContent(/nothing was saved/i));
});

test('a failure while COLLECTING the rows is reported too, and saves nothing', async () => {
  // `fetchAllRows` throws on a mid-walk error rather than returning a short list.
  // That refusal is only worth having if the screen above it does not swallow it.
  render(
    <ExportButton
      title="Children"
      columns={COLUMNS}
      getRows={async () => { throw new Error('Could not load every row. Nothing was saved.'); }}
    />,
  );

  fireEvent.click(screen.getByTestId('export-xlsx'));

  await waitFor(() => expect(screen.getByTestId('export-status'))
    .toHaveTextContent(/could not load every row/i));
  expect(downloadTableRows).not.toHaveBeenCalled();
});

test('a screen with a real server export uses it, filters and all', async () => {
  render(
    <ExportButton
      title="Fee transactions"
      serverExport={{ path: 'fee-transactions', params: { status: 'unpaid' } }}
    />,
  );

  fireEvent.click(screen.getByTestId('export-xlsx'));

  await waitFor(() => expect(downloadServerExport)
    .toHaveBeenCalledWith('fee-transactions', { status: 'unpaid' }, 'xlsx', 'Fee transactions'));
  // It does not claim a row count it has no way of knowing: the server did the
  // reading. A wrong count is worse than none, because someone reconciles against it.
  expect(screen.getByTestId('export-status')).not.toHaveTextContent(/rows/);
});

test('both buttons are disabled while one download is being prepared', async () => {
  let release;
  render(
    <ExportButton
      title="Children"
      columns={COLUMNS}
      getRows={() => new Promise((resolve) => { release = () => resolve(WHOLE_FILTERED_SET); })}
    />,
  );

  fireEvent.click(screen.getByTestId('export-xlsx'));

  expect(screen.getByTestId('export-csv')).toBeDisabled();
  expect(screen.getByTestId('export-xlsx')).toBeDisabled();

  release();
  await waitFor(() => expect(screen.getByTestId('export-xlsx')).not.toBeDisabled());
});

test('a table without an export prop shows no download control', () => {
  render(
    <DataTable
      tableId="plain"
      columns={COLUMNS}
      rows={PAGE_ON_SCREEN}
      page={1}
      total={15}
      pageSize={15}
    />,
  );
  expect(screen.queryByTestId('plain-export-xlsx')).toBeNull();
});

test('refuses to save a file that is short of the count the table is showing', async () => {
  // The mistake that wiring seventy tables by hand invites: handing over the rows on
  // screen instead of every row that matches. It produces a file that looks entirely
  // normal and is missing almost everything, so it is caught centrally rather than
  // left to whoever wires each screen having remembered.
  render(
    <DataTable
      tableId="fees"
      columns={COLUMNS}
      rows={PAGE_ON_SCREEN}
      page={1}
      total={640}
      pageSize={15}
      exportTable={{ title: 'Fees', getRows: async () => PAGE_ON_SCREEN }}
    />,
  );

  fireEvent.click(screen.getByTestId('fees-export-xlsx'));

  await waitFor(() => expect(screen.getByTestId('fees-export-status'))
    .toHaveTextContent(/only 15 of 640 rows, so nothing was saved/i));
  expect(downloadTableRows).not.toHaveBeenCalled();
});
