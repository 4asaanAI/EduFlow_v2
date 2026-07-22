/**
 * UI Sweep Epic 4 — column sorting on the tool-screen table.
 *
 * Asked for directly by the owner on 2026-07-22: "make sure that the sorting per
 * column is available in every table that is present over the platform".
 *
 * Added to the SHARED component rather than screen by screen — 33 tool screens
 * render through it, so this satisfies FR82 for all of them at once. That is the
 * lesson from the previous retrospective: when a defect is in a shared component,
 * the fix goes in the shared component.
 */
import { render, screen, fireEvent, within } from '@testing-library/react';
import { DataTable, sortableCellText } from '../tools/ToolPage';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

const bodyRows = () => {
  const table = screen.getByRole('table');
  return within(table).getAllByRole('row').slice(1); // drop the header row
};
const firstCells = () => bodyRows().map(r => within(r).getAllByRole('cell')[0].textContent);

test('every column heading is a real button, reachable by keyboard', () => {
  render(<DataTable headers={['Name', 'Class']} rows={[['Asha', '5-A'], ['Bipin', '3-B']]} />);
  expect(screen.getByRole('button', { name: /name/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /class/i })).toBeInTheDocument();
});

test('clicking a heading sorts, and clicking again reverses', () => {
  render(<DataTable headers={['Name']} rows={[['Chetan'], ['Asha'], ['Bipin']]} />);
  expect(firstCells()).toEqual(['Chetan', 'Asha', 'Bipin']);

  fireEvent.click(screen.getByRole('button', { name: /name/i }));
  expect(firstCells()).toEqual(['Asha', 'Bipin', 'Chetan']);

  fireEvent.click(screen.getByRole('button', { name: /name/i }));
  expect(firstCells()).toEqual(['Chetan', 'Bipin', 'Asha']);
});

test('the current order is announced to a screen reader', () => {
  render(<DataTable headers={['Name']} rows={[['B'], ['A']]} />);
  const th = screen.getAllByRole('columnheader')[0];
  expect(th).toHaveAttribute('aria-sort', 'none');

  fireEvent.click(screen.getByRole('button', { name: /name/i }));
  expect(screen.getAllByRole('columnheader')[0]).toHaveAttribute('aria-sort', 'ascending');

  fireEvent.click(screen.getByRole('button', { name: /name/i }));
  expect(screen.getAllByRole('columnheader')[0]).toHaveAttribute('aria-sort', 'descending');
});

test('money sorts by value, not by the look of the string', () => {
  // The trap: as text, "₹1,20,000" sorts BELOW "₹9,000" because "1" < "9". On a fee
  // defaulters list that puts the largest debt at the bottom.
  render(<DataTable headers={['Owed']} rows={[['₹9,000'], ['₹1,20,000'], ['₹450']]} />);
  fireEvent.click(screen.getByRole('button', { name: /owed/i }));
  expect(firstCells()).toEqual(['₹450', '₹9,000', '₹1,20,000']);
});

test('percentages and day counts sort numerically', () => {
  render(<DataTable headers={['Rate']} rows={[['100%'], ['9%'], ['85%']]} />);
  fireEvent.click(screen.getByRole('button', { name: /rate/i }));
  expect(firstCells()).toEqual(['9%', '85%', '100%']);
});

test('sorting sees through a styled cell to the text a person reads', () => {
  // Most tool screens wrap values in a coloured <span>. Without this the column
  // would sort by "[object Object]" and appear to do nothing.
  render(
    <DataTable
      headers={['Amount']}
      rows={[
        [<span key="a" style={{ color: 'red' }}>₹900</span>],
        [<span key="b" style={{ color: 'red' }}>₹120</span>],
      ]}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: /amount/i }));
  expect(firstCells()).toEqual(['₹120', '₹900']);
});

test('blank and never-recorded values sort last, not first', () => {
  // Otherwise the 1,802 students with no recorded date of birth fill page one and
  // push everyone who HAS one off the screen.
  render(<DataTable headers={['DOB']} rows={[['2011-04-02'], ['not recorded'], ['2009-01-15']]} />);
  fireEvent.click(screen.getByRole('button', { name: /dob/i }));
  expect(firstCells()).toEqual(['2009-01-15', '2011-04-02', 'not recorded']);
});

test('sorting never mutates the array the screen passed in', () => {
  const rows = [['C'], ['A'], ['B']];
  render(<DataTable headers={['X']} rows={rows} />);
  fireEvent.click(screen.getByRole('button', { name: /x/i }));
  expect(rows).toEqual([['C'], ['A'], ['B']]);
});

test('a table whose order is itself the information can opt out', () => {
  render(<DataTable headers={['Period']} rows={[['3'], ['1'], ['2']]} sortable={false} />);
  expect(screen.queryByRole('button', { name: /period/i })).not.toBeInTheDocument();
  expect(firstCells()).toEqual(['3', '1', '2']);
});

test('sortableCellText digs text out of nested elements', () => {
  expect(sortableCellText('plain')).toBe('plain');
  expect(sortableCellText(42)).toBe('42');
  expect(sortableCellText(null)).toBe('');
  expect(sortableCellText(<span><b>12</b> days</span>)).toContain('12');
});
