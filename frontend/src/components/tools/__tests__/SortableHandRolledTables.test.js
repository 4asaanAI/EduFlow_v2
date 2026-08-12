/**
 * D-24 - the tables that could not move onto `DataTable` still sort, and sort the same way.
 *
 * The owner asked on 2026-07-22 for column sorting on EVERY table. Most screens got it by
 * moving onto the shared `DataTable`. A handful genuinely could not: a certificate row can
 * expand into a full-width "reason for rejection" row, the exam marks grid holds a live
 * input per subject per student, the fee tables carry their own mobile styling. Those keep
 * their own markup and take their sorting from `useColumnSort` + `SortableHeaderRow`.
 *
 * The risk that makes this test worth having is NOT "sorting is missing" - that is visible.
 * It is that the second implementation drifts: no `aria-sort`, a `<div>` instead of a
 * `<button>`, a comparator that puts "₹9,000" above "₹1,20,000". Those are invisible until
 * someone using a keyboard or a screen reader hits them.
 */

import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useColumnSort, SortableHeaderRow } from '../ToolPage';

// A minimal stand-in for the real screens: same hook, same header component, same shape.
function Harness({ rows }) {
  const accessors = React.useMemo(() => [
    (r) => r.name,
    (r) => r.amount,
    null, // an actions column - must NOT offer sorting
  ], []);
  const sort = useColumnSort(rows, accessors);
  return (
    <table>
      <thead>
        <SortableHeaderRow
          tableId="harness"
          headers={['Name', 'Amount', 'Actions']}
          accessors={accessors}
          sort={sort}
          thStyle={{ padding: 4 }}
        />
      </thead>
      <tbody>
        {sort.items.map((r) => (
          <tr key={r.name}><td>{r.name}</td><td>{r.amount}</td><td>-</td></tr>
        ))}
      </tbody>
    </table>
  );
}

// Deliberately in an order that is neither ascending nor descending, and with money
// formatted the way this platform formats it.
const ROWS = [
  { name: 'Meera', amount: '₹9,000' },
  { name: 'Aarav', amount: '₹1,20,000' },
  { name: 'Zoya', amount: '₹45,500' },
];

const namesInOrder = () =>
  screen.getAllByRole('row').slice(1).map((row) => within(row).getAllByRole('cell')[0].textContent);

test('rows start in the order they were given, before anyone clicks a heading', () => {
  render(<Harness rows={ROWS} />);
  expect(namesInOrder()).toEqual(['Meera', 'Aarav', 'Zoya']);
});

test('clicking a heading sorts ascending, and clicking it again reverses it', () => {
  render(<Harness rows={ROWS} />);
  fireEvent.click(screen.getByTestId('harness-sort-0'));
  expect(namesInOrder()).toEqual(['Aarav', 'Meera', 'Zoya']);
  fireEvent.click(screen.getByTestId('harness-sort-0'));
  expect(namesInOrder()).toEqual(['Zoya', 'Meera', 'Aarav']);
});

test('money sorts by its value, not as text', () => {
  // The bug this pins: as plain strings "₹9,000" sorts ABOVE "₹1,20,000", so the largest
  // pending fee would hide at the bottom of a list someone sorted to find exactly that.
  render(<Harness rows={ROWS} />);
  fireEvent.click(screen.getByTestId('harness-sort-1'));
  expect(namesInOrder()).toEqual(['Meera', 'Zoya', 'Aarav']);
});

test('the sorted column announces itself to a screen reader, and the others say none', () => {
  render(<Harness rows={ROWS} />);
  const headers = screen.getAllByRole('columnheader');
  expect(headers.map((th) => th.getAttribute('aria-sort'))).toEqual(['none', 'none', null]);

  fireEvent.click(screen.getByTestId('harness-sort-1'));
  expect(screen.getAllByRole('columnheader').map((th) => th.getAttribute('aria-sort')))
    .toEqual(['none', 'ascending', null]);

  fireEvent.click(screen.getByTestId('harness-sort-1'));
  expect(screen.getAllByRole('columnheader')[1].getAttribute('aria-sort')).toBe('descending');
});

test('a sortable heading is a real button, so the column is reachable by keyboard', () => {
  render(<Harness rows={ROWS} />);
  expect(screen.getByTestId('harness-sort-0').tagName).toBe('BUTTON');
  expect(screen.getByTestId('harness-sort-1').tagName).toBe('BUTTON');
});

test('a column with no accessor offers no sort control at all', () => {
  // A heading that offers to sort and then does nothing is worse than one that does not.
  render(<Harness rows={ROWS} />);
  expect(screen.queryByTestId('harness-sort-2')).toBeNull();
  const actions = screen.getAllByRole('columnheader')[2];
  expect(within(actions).queryByRole('button')).toBeNull();
});

test('sorting never reorders the caller state array it was handed', () => {
  const original = [...ROWS];
  render(<Harness rows={ROWS} />);
  fireEvent.click(screen.getByTestId('harness-sort-0'));
  expect(ROWS).toEqual(original);
});

test('a missing or non-array list renders as empty rather than throwing', () => {
  render(<Harness rows={undefined} />);
  expect(screen.getAllByRole('row')).toHaveLength(1); // the header row only
});
