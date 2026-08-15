/**
 * The searchable drop-down, 2026-08-15.
 *
 * This one control replaces ~50 bare selects across the tool screens, so a fault in it
 * is a fault on fifty screens at once. These tests read what a person would see rather
 * than checking a variable.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import SearchableSelect, { SEARCH_FROM } from '../SearchableSelect';

function options(n, prefix = 'Child') {
  return Array.from({ length: n }, (_, i) => (
    <option key={i} value={`id-${i}`}>{`${prefix} ${i}`}</option>
  ));
}

test('a short list stays exactly as it was, with no search box', () => {
  // A box asking you to type over six choices is slower than six choices. Every screen
  // must be free to adopt this without anybody first checking how long its list is.
  render(
    <SearchableSelect aria-label="House" data-testid="house">
      <option value="">Select...</option>
      {options(4, 'House')}
    </SearchableSelect>,
  );
  expect(screen.queryByTestId('house-search')).not.toBeInTheDocument();
  expect(screen.getByTestId('house')).toBeInTheDocument();
});

test('a long list gets a search box', () => {
  render(
    <SearchableSelect aria-label="Student" data-testid="student">
      <option value="">Select...</option>
      {options(SEARCH_FROM + 5)}
    </SearchableSelect>,
  );
  expect(screen.getByTestId('student-search')).toBeInTheDocument();
});

test('typing narrows the list and the count says how much is being shown', () => {
  // Standing rule from the tables release: a partial answer must be impossible to
  // mistake for a complete one.
  render(
    <SearchableSelect aria-label="Student" data-testid="student">
      <option value="">Select...</option>
      {options(20)}
    </SearchableSelect>,
  );
  expect(screen.getByTestId('student-count')).toHaveTextContent('20 to choose from');

  fireEvent.change(screen.getByTestId('student-search'), { target: { value: 'Child 1' } });
  // Child 1 and Child 10 to 19.
  expect(screen.getByTestId('student-count')).toHaveTextContent('11 of 20 shown');
  expect(screen.getByRole('option', { name: 'Child 1' })).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Child 2' })).not.toBeInTheDocument();
});

test('the prompt entry is never filtered away', () => {
  // Without this a person who has typed cannot clear their selection any more.
  render(
    <SearchableSelect aria-label="Student" data-testid="student">
      <option value="">Every class</option>
      {options(20)}
    </SearchableSelect>,
  );
  fireEvent.change(screen.getByTestId('student-search'), { target: { value: 'zzz' } });
  expect(screen.getByRole('option', { name: 'Every class' })).toBeInTheDocument();
  expect(screen.getByTestId('student-count')).toHaveTextContent('Nothing matches');
});

test('the chosen option survives typing that would have filtered it out', () => {
  // The worst kind of fault otherwise: the form looks filled in and is not.
  render(
    <SearchableSelect aria-label="Student" data-testid="student" value="id-3" onChange={() => {}}>
      <option value="">Select...</option>
      {options(20)}
    </SearchableSelect>,
  );
  fireEvent.change(screen.getByTestId('student-search'), { target: { value: 'Child 11' } });
  expect(screen.getByTestId('student')).toHaveValue('id-3');
  expect(screen.getByRole('option', { name: 'Child 3' })).toBeInTheDocument();
});

test('choosing still reports the value the screen expects', () => {
  // Driven through a real piece of state rather than by reading the event object, which
  // React reuses after the re-render and which therefore reads back empty whatever the
  // control did. That would have been a test artifact reported as a fault.
  const seen = [];
  function Harness() {
    const [value, setValue] = React.useState('');
    seen.push(value);
    return (
      <SearchableSelect
        aria-label="Student"
        data-testid="student"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      >
        <option value="">Select...</option>
        {options(20)}
      </SearchableSelect>
    );
  }
  render(<Harness />);
  fireEvent.change(screen.getByTestId('student'), { target: { value: 'id-7' } });
  expect(seen[seen.length - 1]).toBe('id-7');
  expect(screen.getByTestId('student')).toHaveValue('id-7');
});

test('choosing after searching reports the right value, not the one at that position', () => {
  // The trap this control could most easily introduce: the list a person sees is not the
  // list the screen holds, so an index-based answer would return the wrong person.
  const seen = [];
  function Harness() {
    const [value, setValue] = React.useState('');
    seen.push(value);
    return (
      <SearchableSelect
        aria-label="Student"
        data-testid="student"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      >
        <option value="">Select...</option>
        {options(20)}
      </SearchableSelect>
    );
  }
  render(<Harness />);
  fireEvent.change(screen.getByTestId('student-search'), { target: { value: 'Child 15' } });
  fireEvent.change(screen.getByTestId('student'), { target: { value: 'id-15' } });
  expect(seen[seen.length - 1]).toBe('id-15');
});

test('a label written as a prop is searchable too', () => {
  // Several screens write `<option label={...} />` with no children, which a search that
  // only read children would be blind to.
  render(
    <SearchableSelect aria-label="Ward" data-testid="ward">
      <option value="">Select...</option>
      {Array.from({ length: 12 }, (_, i) => (
        <option key={i} value={`w-${i}`} label={`Ward ${i}`} />
      ))}
    </SearchableSelect>,
  );
  fireEvent.change(screen.getByTestId('ward-search'), { target: { value: 'Ward 4' } });
  expect(screen.getByTestId('ward-count')).toHaveTextContent('1 of 12 shown');
});

test('searching is case-insensitive and matches anywhere in the name', () => {
  // Somebody looking for a child called Sharma types "sharma", not the first letter of
  // their given name, which is all a plain drop-down would have matched.
  render(
    <SearchableSelect aria-label="Student" data-testid="student">
      <option value="">Select...</option>
      {options(9)}
      <option value="x">Anika Sharma</option>
      <option value="y">Rohit Verma</option>
    </SearchableSelect>,
  );
  fireEvent.change(screen.getByTestId('student-search'), { target: { value: 'SHARMA' } });
  expect(screen.getByRole('option', { name: 'Anika Sharma' })).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Rohit Verma' })).not.toBeInTheDocument();
});
