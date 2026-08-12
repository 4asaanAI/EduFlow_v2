/**
 * Filters on every tool table - Release 3, item C.
 *
 * Written once, here, because about seventy tables render through one component.
 * Column sorting arrived the same way in July and the download in item 5 of this
 * release; a filter written seventy times by hand would be seventy chances to filter
 * the screen and forget the file.
 *
 * THE TWO THINGS THAT MATTER, and they are the two halves of the same fault:
 *
 *  - THE COUNT IS ALWAYS VISIBLE. A filter is the one control whose entire job is to
 *    return less. "24 of 1,876" is what stops a narrowed screen being read as the
 *    whole list.
 *  - THE FILE FOLLOWS THE FILTER. A download that quietly holds the whole list when
 *    the screen was narrowed is the same fault as a short file, in the other
 *    direction: it gets filed under the wrong name and reconciled against.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DataTable, Badge } from '../tools/ToolPage';
import * as exportTable from '../../lib/exportTable';

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: false }),
}));

const HEADERS = ['Name', 'Class', 'Status'];

/** Twenty children across three classes and two states. */
const ROWS = Array.from({ length: 20 }, (_, i) => [
  `Child ${i}`,
  ['5 A', '5 B', '6 A'][i % 3],
  i % 4 === 0 ? 'Unpaid' : 'Paid',
]);

let downloadTableRows;

beforeEach(() => {
  downloadTableRows = jest.spyOn(exportTable, 'downloadTableRows').mockResolvedValue();
});

afterEach(() => jest.restoreAllMocks());

test('a table long enough to be hard to read by hand gets a filter bar', () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);
  expect(screen.getByTestId('t-filters')).toBeInTheDocument();
  expect(screen.getByTestId('t-search')).toBeInTheDocument();
});

test('a short summary table is left alone', () => {
  render(<DataTable title="Top 3" headers={HEADERS} rows={ROWS.slice(0, 3)} tableId="t" />);
  expect(screen.queryByTestId('t-filters')).toBeNull();
});

test('a screen can turn filtering off', () => {
  render(<DataTable title="Panel" headers={HEADERS} rows={ROWS} tableId="t" filterable={false} />);
  expect(screen.queryByTestId('t-filters')).toBeNull();
});

test('a column whose values repeat gets a picker; a column of names does not', () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);

  // Class (3 values) and Status (2 values) are worth choosing between.
  expect(screen.getByTestId('t-filter-1')).toBeInTheDocument();
  expect(screen.getByTestId('t-filter-2')).toBeInTheDocument();
  // Twenty distinct names are not: a dropdown of twenty names is worse than typing.
  expect(screen.queryByTestId('t-filter-0')).toBeNull();
});

test('picking a value narrows the table and says how much is hidden', () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);

  expect(screen.getByTestId('t-filter-count')).toHaveTextContent('20 rows');

  fireEvent.change(screen.getByTestId('t-filter-2'), { target: { value: 'Unpaid' } });

  expect(screen.getByTestId('t-filter-count')).toHaveTextContent('Showing 5 of 20');
  expect(screen.queryByText('Child 1')).toBeNull();
  expect(screen.getByText('Child 0')).toBeInTheDocument();
});

test('typing searches every column', () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);

  fireEvent.change(screen.getByTestId('t-search'), { target: { value: '6 a' } });

  expect(screen.getByTestId('t-filter-count')).toHaveTextContent('Showing 6 of 20');
});

test('two filters together narrow further, and Clear puts everything back', () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);

  fireEvent.change(screen.getByTestId('t-filter-1'), { target: { value: '5 A' } });
  fireEvent.change(screen.getByTestId('t-filter-2'), { target: { value: 'Unpaid' } });
  // Class 5 A is every third row and unpaid is every fourth, so both is every twelfth.
  expect(screen.getByTestId('t-filter-count')).toHaveTextContent('Showing 2 of 20');

  fireEvent.click(screen.getByTestId('t-filter-clear'));
  expect(screen.getByTestId('t-filter-count')).toHaveTextContent('20 rows');
});

test('a filter matching nothing says so, rather than "no data found"', () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);

  fireEvent.change(screen.getByTestId('t-search'), { target: { value: 'nobody at all' } });

  // "No data found" over a filtered table reads as an empty school.
  expect(screen.getByTestId('t-no-match')).toHaveTextContent('20 rows are hidden');
  expect(screen.queryByText('No data found')).toBeNull();
});

test('THE ONE THAT MATTERS: the download holds the filtered rows, not the whole list', async () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);

  fireEvent.change(screen.getByTestId('t-filter-2'), { target: { value: 'Unpaid' } });
  fireEvent.click(screen.getByTestId('t-export-xlsx'));

  await waitFor(() => expect(downloadTableRows).toHaveBeenCalled());
  const saved = downloadTableRows.mock.calls[0][0];
  expect(saved.rows).toHaveLength(5);
  expect(saved.rows.every((row) => row[2] === 'Unpaid')).toBe(true);
});

test('unfiltered, the download still holds the whole table', async () => {
  render(<DataTable title="Fees" headers={HEADERS} rows={ROWS} tableId="t" />);

  fireEvent.click(screen.getByTestId('t-export-xlsx'));

  await waitFor(() => expect(downloadTableRows).toHaveBeenCalled());
  expect(downloadTableRows.mock.calls[0][0].rows).toHaveLength(20);
});

test('a filter sees through a cell that is drawn rather than written', () => {
  const drawn = ROWS.map((row) => [row[0], row[1], <Badge key="b" text={row[2]} />]);

  render(<DataTable title="Fees" headers={HEADERS} rows={drawn} tableId="t" />);

  // A Badge keeps its only word in a prop. If the filter could not read that, every
  // badge column would offer a dropdown of blanks.
  fireEvent.change(screen.getByTestId('t-filter-2'), { target: { value: 'Unpaid' } });
  expect(screen.getByTestId('t-filter-count')).toHaveTextContent('Showing 5 of 20');
});
