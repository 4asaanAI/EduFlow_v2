import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FeeCollection from '../FeeCollection';

jest.mock('../../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'owner-1', role: 'owner', name: 'School Owner' } }),
}));

const classes = [
  { id: 'class-1', name: '1st', section: 'A' },
  { id: 'class-2', name: '2nd', section: 'B' },
];

function makeStudents(count) {
  return Array.from({ length: count }, (_, index) => ({
    id: `student-${index + 1}`,
    name: `Child ${String(index + 1).padStart(4, '0')}`,
    class_id: index === count - 1 ? 'class-2' : 'class-1',
  }));
}

jest.mock('../../../lib/api', () => {
  const actual = jest.requireActual('../../../lib/api');
  const stub = {};
  Object.keys(actual).forEach((key) => {
    stub[key] = typeof actual[key] === 'function'
      ? async () => ({ success: true, data: [] })
      : actual[key];
  });
  stub.subscribeSSE = () => () => {};
  stub.getAllClasses = async () => ({ success: true, data: classes });
  stub.getAllStudents = async () => ({ success: true, data: mockStudents() });
  stub.getDiscountTypes = async () => ({ data: [] });
  stub.getDiscountSummary = async () => ({ success: true, data: {} });
  return stub;
});

const mockStudents = () => makeStudents(1876);

test('the payment student list holds every child, not the first page of them', async () => {
  render(<FeeCollection />);
  await waitFor(() => expect(screen.getByTestId('payment-student-count'))
    .toHaveTextContent('Showing 200 of 1876 matches'));

  fireEvent.change(screen.getByLabelText('Search Payment student'), { target: { value: 'Child 1876' } });
  expect(screen.getByTestId('payment-student-count')).toHaveTextContent('1 of 1876 shown');
  expect(screen.getByRole('option', { name: /Child 1876/ })).toBeInTheDocument();
  fireEvent.change(screen.getByTestId('payment-student'), { target: { value: 'student-1876' } });
  expect(screen.getByTestId('payment-student')).toHaveValue('student-1876');
});
