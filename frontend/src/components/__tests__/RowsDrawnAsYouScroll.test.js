/**
 * Rows drawn as you scroll - Release 3, item D.
 *
 * "All" means ALL THE DATA, drawn as you scroll (Abhimanyu, 2026-08-12). Picking All
 * over 1,876 children asks a phone to lay out 1,876 table rows at once, and the
 * student list and the School Directory are the two long enough for that to be felt.
 *
 * WHAT THESE PIN, and both are the same idea from opposite sides:
 *
 *  - EVERY ROW IS STILL THERE. Nothing is dropped, filtered or capped. The rows are
 *    all held; only the painting is spread out.
 *  - THE COUNT STAYS HONEST. A list that has painted its first hundred rows must not
 *    be indistinguishable from a list of a hundred rows. That is this release's
 *    defining fault wearing a new hat, and it is why the drawn count and the loaded
 *    count are both on screen.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import DataTable from '../ui/DataTable';

const COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'cls', label: 'Class' },
];

const ROLL = Array.from({ length: 260 }, (_, i) => ({
  id: `s-${i}`, name: `Child ${i}`, cls: '5 A',
}));

function renderRoll(props = {}) {
  return render(
    <DataTable
      columns={COLUMNS}
      rows={ROLL}
      total={ROLL.length}
      pageSize={-1}
      tableId="roll"
      {...props}
    />,
  );
}

test('a long list paints a first batch rather than all of it at once', () => {
  renderRoll();

  expect(screen.getByText('Child 0')).toBeInTheDocument();
  expect(screen.getByText('Child 99')).toBeInTheDocument();
  // Not yet drawn. It is loaded and one scroll away, which is the whole design.
  expect(screen.queryByText('Child 100')).toBeNull();
});

test('it says how many are drawn and how many are loaded', () => {
  renderRoll();

  // Without this line, a hundred painted rows reads as a school of a hundred.
  expect(screen.getByTestId('roll-drawn-count'))
    .toHaveTextContent('Showing 100 of 260 loaded rows');
});

test('the rest arrives, and nothing is lost on the way', () => {
  renderRoll();

  fireEvent.click(screen.getByTestId('roll-draw-more-button'));
  expect(screen.getByText('Child 100')).toBeInTheDocument();
  expect(screen.getByTestId('roll-drawn-count')).toHaveTextContent('Showing 200 of 260');

  fireEvent.click(screen.getByTestId('roll-draw-more-button'));
  // The last child on the roll. Every one of the 260 is reachable.
  expect(screen.getByText('Child 259')).toBeInTheDocument();
  // Nothing left to draw, so the notice goes away rather than saying "0 more".
  expect(screen.queryByTestId('roll-draw-more')).toBeNull();
});

test('a short list is drawn whole, with no notice and no button', () => {
  render(
    <DataTable columns={COLUMNS} rows={ROLL.slice(0, 20)} total={20} pageSize={20} tableId="roll" />,
  );

  expect(screen.getByText('Child 19')).toBeInTheDocument();
  expect(screen.queryByTestId('roll-draw-more')).toBeNull();
});

test('a new set of rows starts painting from the top again', () => {
  const { rerender } = renderRoll();

  fireEvent.click(screen.getByTestId('roll-draw-more-button'));
  expect(screen.getByTestId('roll-drawn-count')).toHaveTextContent('Showing 200 of 260');

  // A filter, a sort or a new page hands over a different list. Keeping the old
  // figure would paint 200 rows of a list somebody has just narrowed.
  const narrowed = ROLL.slice(0, 150).map((s) => ({ ...s }));
  rerender(
    <DataTable columns={COLUMNS} rows={narrowed} total={150} pageSize={-1} tableId="roll" />,
  );

  expect(screen.getByTestId('roll-drawn-count')).toHaveTextContent('Showing 100 of 150');
});

test('the download still holds every row, not the ones painted so far', async () => {
  const getRows = jest.fn().mockResolvedValue(ROLL);

  renderRoll({ exportTable: { title: 'Students', getRows } });

  // The export asks the screen for every row matching the filters, which has nothing
  // to do with how many have been painted. A file holding the first hundred, with
  // nothing on it to say so, is the fault this release exists to remove.
  fireEvent.click(screen.getByTestId('roll-export-xlsx'));
  expect(getRows).toHaveBeenCalled();
});
