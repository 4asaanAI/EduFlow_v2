/**
 * The shared sortable table — Epic 3, Stories 3.1 and 3.2.
 *
 * These trace the acceptance criteria that automated tests can actually decide.
 * The one that matters most is the FIRST block: sorting must be delegated to the
 * server. On a 20-row page a client-side sort and a server-side sort look
 * identical, and on a 1,802-row table only one of them is telling the truth.
 */

import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import DataTable, { cellValue } from '../ui/DataTable';

const COLUMNS = [
  { key: 'name', label: 'Name', sortKey: 'name' },
  { key: 'class', label: 'Class', sortKey: 'class' },
  { key: 'phone', label: 'Phone' },                 // deliberately NOT sortable
];

const ROWS = [
  { id: '1', name: 'Zara', class: '5th-A', phone: '900' },
  { id: '2', name: 'Aarav', class: '1st-B', phone: '901' },
];

function setup(overrides = {}) {
  const props = {
    tableId: 'students',
    columns: COLUMNS,
    rows: ROWS,
    sort: 'name',
    page: 1,
    total: 1802,
    pageSize: 15,
    onSortChange: jest.fn(),
    onPageChange: jest.fn(),
    onPageSizeChange: jest.fn(),
    ...overrides,
  };
  return { ...render(<DataTable {...props} />), props };
}

describe('sorting is delegated to the server', () => {
  it('asks the caller to re-sort rather than reordering the rows itself', () => {
    const { props } = setup();
    fireEvent.click(screen.getByTestId('students-sort-class'));
    expect(props.onSortChange).toHaveBeenCalledWith('class');
  });

  it('renders rows in the order given, never re-sorted locally', () => {
    // Zara before Aarav — alphabetically "wrong", which is the point: the
    // server decided this order and the table must not second-guess it.
    setup();
    const names = screen.getAllByRole('row').slice(1).map(r => within(r).getAllByRole('cell')[0].textContent);
    expect(names).toEqual(['Zara', 'Aarav']);
  });

  it('does not offer to sort a column the server cannot sort', () => {
    setup();
    expect(screen.queryByTestId('students-sort-phone')).not.toBeInTheDocument();
  });
});

describe('screen readers can tell what the order is', () => {
  it('marks the active column with aria-sort and the others none', () => {
    setup({ sort: 'name', sortDirection: 'ascending' });
    const headers = screen.getAllByRole('columnheader');
    expect(headers[0]).toHaveAttribute('aria-sort', 'ascending');
    expect(headers[1]).toHaveAttribute('aria-sort', 'none');
  });

  it('reflects a descending sort', () => {
    setup({ sort: 'name', sortDirection: 'descending' });
    expect(screen.getAllByRole('columnheader')[0]).toHaveAttribute('aria-sort', 'descending');
  });

  it('leaves aria-sort off a column that is not sortable at all', () => {
    setup();
    expect(screen.getAllByRole('columnheader')[2]).not.toHaveAttribute('aria-sort');
  });

  it('makes each sortable heading a real, keyboard-reachable button', () => {
    setup();
    expect(screen.getByTestId('students-sort-name').tagName).toBe('BUTTON');
  });
});

describe('paging', () => {
  it('disables Prev on the first page', () => {
    setup({ page: 1 });
    expect(screen.getByTestId('students-prev')).toBeDisabled();
  });

  it('disables Next on the last page', () => {
    // 30 rows at 15 per page = 2 pages.
    setup({ page: 2, total: 30, pageSize: 15 });
    expect(screen.getByTestId('students-next')).toBeDisabled();
  });

  it('computes the page count from the CHOSEN page size, not a fixed 20', () => {
    setup({ page: 1, total: 30, pageSize: 5 });
    expect(screen.getByTestId('students-page-indicator')).toHaveTextContent('Page 1 of 6');
  });

  it('announces the page change politely rather than stealing focus', () => {
    setup();
    expect(screen.getByTestId('students-page-indicator')).toHaveAttribute('aria-live', 'polite');
  });
});

describe('rows-per-page selector (UX-DR10)', () => {
  it('offers exactly the sizes the owner asked for', () => {
    setup();
    const options = within(screen.getByTestId('students-page-size')).getAllByRole('option');
    expect(options.map(o => o.value)).toEqual(['5', '10', '15', '20', '25', '30']);
  });

  it('shows the active value', () => {
    setup({ pageSize: 25 });
    expect(screen.getByTestId('students-page-size')).toHaveValue('25');
  });

  it('reports the chosen size as a number, not the string a select emits', () => {
    const { props } = setup();
    fireEvent.change(screen.getByTestId('students-page-size'), { target: { value: '30' } });
    expect(props.onPageSizeChange).toHaveBeenCalledWith(30);
  });

  it('has a real associated label, not a placeholder', () => {
    setup();
    expect(screen.getByLabelText('Rows')).toBe(screen.getByTestId('students-page-size'));
  });
});

describe('empty and failed are not the same thing', () => {
  it('shows a failure as a failure, never as an empty list', () => {
    // Owner item 7: a load failure was being displayed as a zero.
    setup({ rows: [], error: 'Could not reach the server' });
    expect(screen.getByTestId('students-error')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Could not reach the server');
    expect(screen.queryByTestId('students-empty')).not.toBeInTheDocument();
  });

  it('shows an empty result as empty, with no alert', () => {
    setup({ rows: [], total: 0 });
    expect(screen.getByTestId('students-empty')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('does not claim "no records" while it is still loading', () => {
    setup({ rows: [], loading: true });
    expect(screen.queryByTestId('students-empty')).not.toBeInTheDocument();
  });
});

describe('values that were never captured', () => {
  it.each([[null], [undefined], ['']])('renders %p as "not recorded"', (v) => {
    // dob, gender, house and admission_date are empty for all 1,802 students
    // because they were never collected. A blank would read as a fault.
    render(<span>{cellValue(v)}</span>);
    expect(screen.getByText('not recorded')).toBeInTheDocument();
  });

  it('leaves a real value alone, including a legitimate zero', () => {
    render(<span data-testid="v">{cellValue(0)}</span>);
    expect(screen.getByTestId('v')).toHaveTextContent('0');
    expect(screen.queryByText('not recorded')).not.toBeInTheDocument();
  });
});

describe('the table stays one element (D-01 must not return)', () => {
  it('keeps a single table with its head and body intact', () => {
    // The 2026-07-22 regression split tables into two independently-sized
    // pieces so headings stopped aligning with their columns. One <table>
    // containing one <thead> and one <tbody> is what prevents that.
    setup();
    const tables = screen.getAllByRole('table');
    expect(tables).toHaveLength(1);
    expect(tables[0].querySelectorAll('thead')).toHaveLength(1);
    expect(tables[0].querySelectorAll('tbody')).toHaveLength(1);
  });

  it('scrolls the wrapper, not the table', () => {
    setup();
    const wrapper = screen.getByRole('table').parentElement;
    expect(wrapper).toHaveStyle({ overflowX: 'auto' });
  });
});
